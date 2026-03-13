#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.synthetic import load_jsonl, write_jsonl


CONFIG_PATH = PROJECT_ROOT / "configs" / "synthetic_v4_generation_spec.json"
SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "synthetic_v4_pilot_1k_seeds.jsonl"
BENCH_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
TASKS_PATH = BENCH_DIR / "synthetic_v4_pilot_1k_tasks.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_v4_pilot_1k_tasks.md"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


def load_task_generator_module():
    path = PROJECT_ROOT / "scripts" / "generate_benchmark_tasks.py"
    spec = importlib.util.spec_from_file_location("vehbench_generate_benchmark_tasks", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def adapt_seed(seed: dict) -> dict:
    return {
        "seed_id": seed["synthetic_seed_id"],
        "source_paper_id": seed["synthetic_seed_id"],
        "source_doi": seed.get("parent_doi"),
        "verifier_mapping": seed["verifier_mapping"],
        "task_blueprints": seed["task_blueprints"],
    }


def postprocess_task(task: dict, seed: dict) -> dict:
    split = seed["assigned_split"]
    task_type = task["task_type"]
    synthetic_seed_id = seed["synthetic_seed_id"]
    parent_anchor_id = seed["parent_anchor_id"]
    parent_paper_id = seed["parent_paper_id"]
    excitation = (seed.get("verifier_mapping") or {}).get("excitation_settings") or {}
    observed = (seed.get("verifier_mapping") or {}).get("observed_outputs") or {}

    task["task_id"] = f"{synthetic_seed_id}::{task_type}"
    task["source_type"] = "synthetic"
    task["source_refs"] = {
        "source_paper_uid": parent_paper_id,
        "source_record_id": synthetic_seed_id,
        "parent_anchor_id": parent_anchor_id,
        "generator_name": "generate_synthetic_v4_tasks",
        "generator_seed": None,
    }
    task["split"] = split
    task["fixed_conditions"] = {
        **(task.get("fixed_conditions") or {}),
        "excitation_frequency_hz": excitation.get("frequency_hz"),
        "acceleration_g": excitation.get("acceleration_g"),
    }
    task["objective"]["normalization_reference"] = parent_anchor_id
    task["notes"] = f"synthetic_v4::{parent_anchor_id}::{seed['sample_policy']}"
    if task_type == "constrained_power_maximization":
        task["fixed_conditions"]["matched_load_resistance_ohm"] = observed.get("matched_load_resistance_ohm")
    return task


def harden_seed(seed: dict, config: dict) -> dict:
    split_name = seed["assigned_split"]["name"]
    outputs = (seed.get("verifier_mapping") or {}).get("observed_outputs") or {}
    hardened = {**seed, "task_blueprints": []}

    for blueprint in seed["task_blueprints"]:
        task_type = blueprint["task_type"]
        hard_constraints = dict(blueprint.get("hard_constraints") or {})
        objective = dict(blueprint.get("objective") or {})
        fixed_conditions = dict(blueprint.get("fixed_conditions") or {})
        profile = config["task_profiles"][task_type][split_name]

        if task_type == "frequency_matching":
            target = float(objective["target_value"])
            shift_pct = float(profile["target_shift_pct"])
            direction = -1.0 if split_name == "test-ood" else 1.0
            shifted = target * (1.0 + direction * shift_pct / 100.0)
            objective["target_value"] = round(shifted, 6)
            fixed_conditions["target_resonant_frequency_hz"] = round(shifted, 6)
            hard_constraints["frequency_error_tolerance_pct"] = float(profile["tolerance_pct"])
            budget_hint = int(profile["budget"])
        elif task_type == "feasibility_repair":
            hard_constraints["frequency_error_tolerance_pct"] = 1.0 if split_name in {"test-id", "test-ood"} else 1.2
            hard_constraints["stress_limit_mpa"] = outputs.get("root_stress_mpa")
            hard_constraints["displacement_limit_mm"] = outputs.get("tip_displacement_mm")
            budget_hint = int(profile["budget"])
        else:
            power_scale = float(profile["power_target_scale"])
            if objective.get("target_value") is not None:
                objective["target_value"] = round(float(objective["target_value"]) * power_scale, 6)
            if hard_constraints.get("power_target_uw") is not None:
                hard_constraints["power_target_uw"] = round(float(hard_constraints["power_target_uw"]) * power_scale, 6)
            hard_constraints["stress_limit_mpa"] = outputs.get("root_stress_mpa")
            hard_constraints["displacement_limit_mm"] = outputs.get("tip_displacement_mm")
            budget_hint = int(profile["budget"])

        hardened["task_blueprints"].append(
            {
                **blueprint,
                "fixed_conditions": fixed_conditions,
                "hard_constraints": hard_constraints,
                "objective": objective,
                "budget_hint": budget_hint,
            }
        )
    return hardened


def main() -> None:
    config = load_config()
    module = load_task_generator_module()
    seeds = load_jsonl(SEEDS_PATH)
    tasks = []
    by_type = {"frequency_matching": [], "constrained_power_maximization": [], "feasibility_repair": []}
    by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}

    for raw_seed in seeds:
        split = raw_seed["assigned_split"]
        hardened_raw_seed = harden_seed(raw_seed, config)
        tuned_seed = module.tune_seed_blueprints(adapt_seed(hardened_raw_seed), split)
        for blueprint in tuned_seed["task_blueprints"]:
            task = module.build_task(tuned_seed, blueprint, split)
            task = postprocess_task(task, hardened_raw_seed)
            tasks.append(task)
            by_type[task["task_type"]].append(task)
            by_split[task["split"]["name"]].append(task)

    write_jsonl(TASKS_PATH, tasks)
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_frequency_matching.jsonl", by_type["frequency_matching"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_constrained_power_maximization.jsonl", by_type["constrained_power_maximization"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_feasibility_repair.jsonl", by_type["feasibility_repair"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_train.jsonl", by_split["train"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_val.jsonl", by_split["val"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_test_id.jsonl", by_split["test-id"])
    write_jsonl(BENCH_DIR / "synthetic_v4_pilot_1k_tasks_test_ood.jsonl", by_split["test-ood"])

    counts = {
        "total": len(tasks),
        "frequency_matching": len(by_type["frequency_matching"]),
        "constrained_power_maximization": len(by_type["constrained_power_maximization"]),
        "feasibility_repair": len(by_type["feasibility_repair"]),
    }
    split_counts = Counter(task["split"]["name"] for task in tasks)
    lines = [
        "# Synthetic v4 Pilot 1k Tasks",
        "",
        f"- synthetic seeds input: `{len(seeds)}`",
        f"- total tasks: `{counts['total']}`",
        f"- frequency_matching: `{counts['frequency_matching']}`",
        f"- constrained_power_maximization: `{counts['constrained_power_maximization']}`",
        f"- feasibility_repair: `{counts['feasibility_repair']}`",
        "",
        "## Split Counts",
        "",
    ]
    for split_name in ("train", "val", "test-id", "test-ood"):
        lines.append(f"- {split_name}: `{split_counts.get(split_name, 0)}`")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({"counts": counts, "split_counts": split_counts, "output": str(TASKS_PATH)}, indent=2, default=dict))


if __name__ == "__main__":
    main()
