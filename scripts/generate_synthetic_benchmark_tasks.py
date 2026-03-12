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


SOURCE_SEED_VERSION = "v2"
SYNTHETIC_VERSION = "v3"
SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / f"synthetic_pilot_{SOURCE_SEED_VERSION}_seeds.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
TASKS_PATH = BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks.md"
SYNTHETIC_FREQUENCY_SHIFT_PROFILES = {
    "train": {"min_shift_pct": 1.2, "max_shift_pct": 2.8, "target_shift_pct": 2.0},
    "val": {"min_shift_pct": 1.6, "max_shift_pct": 3.2, "target_shift_pct": 2.4},
    "test-id": {"min_shift_pct": 2.0, "max_shift_pct": 3.8, "target_shift_pct": 2.9},
    "test-ood": {"min_shift_pct": 2.6, "max_shift_pct": 4.0, "target_shift_pct": 3.3},
}
SYNTHETIC_REPAIR_DIFFICULTY_PROFILES = {
    "train": {"min_error_pct": 2.4, "max_error_pct": 4.2, "target_error_pct": 3.0},
    "val": {"min_error_pct": 3.0, "max_error_pct": 5.0, "target_error_pct": 3.8},
    "test-id": {"min_error_pct": 3.8, "max_error_pct": 6.0, "target_error_pct": 4.8},
    "test-ood": {"min_error_pct": 4.6, "max_error_pct": 7.5, "target_error_pct": 5.8},
}
SYNTHETIC_REPAIR_TOLERANCE_BY_SPLIT = {
    "train": 1.8,
    "val": 1.5,
    "test-id": 1.2,
    "test-ood": 1.0,
}
SYNTHETIC_FREQUENCY_TOLERANCE_BY_SPLIT = {
    "train": 1.5,
    "val": 1.25,
    "test-id": 1.0,
    "test-ood": 0.8,
}
SYNTHETIC_BOUND_WIDENING = {
    "train": {"geometry": 1.25, "tip_mass": 1.35, "load": 1.0},
    "val": {"geometry": 1.35, "tip_mass": 1.5, "load": 1.0},
    "test-id": {"geometry": 1.6, "tip_mass": 1.8, "load": 1.0},
    "test-ood": {"geometry": 1.9, "tip_mass": 2.1, "load": 1.0},
}
SYNTHETIC_BUDGETS = {
    "frequency_matching": {"train": 16, "val": 14, "test-id": 10, "test-ood": 8},
    "feasibility_repair": {"train": 12, "val": 10, "test-id": 8, "test-ood": 6},
    "constrained_power_maximization": {"train": 24, "val": 20, "test-id": 16, "test-ood": 12},
}


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


def widen_bounds(variable_bounds: dict, split_name: str) -> dict:
    profile = SYNTHETIC_BOUND_WIDENING.get(split_name, SYNTHETIC_BOUND_WIDENING["train"])
    widened = {}
    for key, bounds in variable_bounds.items():
        low = float(bounds["min"])
        high = float(bounds["max"])
        center = (low + high) / 2.0
        half_span = (high - low) / 2.0
        if key == "load_resistance_ohm":
            scale = profile["load"]
        elif key == "tip_mass_g":
            scale = profile["tip_mass"]
        else:
            scale = profile["geometry"]
        new_half_span = half_span * scale
        new_low = center - new_half_span
        new_high = center + new_half_span
        if low > 0:
            new_low = max(low * 0.25, new_low)
        widened[key] = {
            **bounds,
            "min": round(new_low, 8),
            "max": round(new_high, 8),
        }
    return widened


def maybe_scaled_limit(value: float | None, multiplier: float) -> float | None:
    if value is None:
        return None
    return round(float(value) * multiplier, 12)


def harden_seed(seed: dict, split_name: str) -> dict:
    hardened = {
        **seed,
        "task_blueprints": [],
    }
    outputs = (seed.get("verifier_mapping") or {}).get("observed_outputs") or {}
    stress_ref = outputs.get("root_stress_mpa")
    displacement_ref = outputs.get("tip_displacement_mm")
    limit_multiplier = {
        "train": 1.15,
        "val": 1.12,
        "test-id": 1.08,
        "test-ood": 1.05,
    }[split_name]

    for blueprint in seed["task_blueprints"]:
        task_type = blueprint["task_type"]
        hard_constraints = dict(blueprint.get("hard_constraints") or {})
        hardening_options = dict(blueprint.get("hardening_options") or {})
        budget_hint = SYNTHETIC_BUDGETS.get(task_type, {}).get(split_name, blueprint.get("budget_hint"))

        if task_type in {"frequency_matching", "feasibility_repair"}:
            hard_constraints["stress_limit_mpa"] = maybe_scaled_limit(stress_ref, limit_multiplier)
            hard_constraints["displacement_limit_mm"] = maybe_scaled_limit(displacement_ref, limit_multiplier)

        if task_type == "frequency_matching":
            hardening_options.update(
                {
                    "min_bound_touches": 1,
                    "prefer_edge_reference": split_name in {"test-id", "test-ood"},
                }
            )
        elif task_type == "feasibility_repair":
            hardening_options.update(
                {
                    "min_changed_dims": 2 if split_name in {"train", "val"} else 3,
                    "prefer_multi_violation": True,
                    "prefer_nonfrequency_violation": split_name in {"test-id", "test-ood"},
                }
            )

        hardened["task_blueprints"].append(
            {
                **blueprint,
                "variable_bounds": widen_bounds(blueprint["variable_bounds"], split_name),
                "hard_constraints": hard_constraints,
                "hardening_options": hardening_options,
                "budget_hint": budget_hint,
            }
        )

    return hardened


def postprocess_task(task: dict, seed: dict) -> dict:
    split = seed["assigned_split"]
    task_type = task["task_type"]
    synthetic_seed_id = seed["synthetic_seed_id"]
    parent_anchor_id = seed["parent_anchor_id"]
    parent_paper_id = seed["parent_paper_id"]
    excitation = (seed.get("verifier_mapping") or {}).get("excitation_settings") or {}

    task["task_id"] = f"{synthetic_seed_id}::{task_type}"
    task["source_type"] = "synthetic"
    task["source_refs"] = {
        "source_paper_uid": parent_paper_id,
        "source_record_id": synthetic_seed_id,
        "parent_anchor_id": parent_anchor_id,
        "generator_name": "generate_synthetic_benchmark_tasks_v1",
        "generator_seed": None,
    }
    task["split"] = split
    task["fixed_conditions"] = {
        **(task.get("fixed_conditions") or {}),
        "excitation_frequency_hz": excitation.get("frequency_hz"),
        "acceleration_g": excitation.get("acceleration_g"),
    }
    task["objective"]["normalization_reference"] = parent_anchor_id
    task["notes"] = f"synthetic_from_anchor::{parent_anchor_id}::{seed['sample_policy']}"
    return task


def main() -> None:
    module = load_task_generator_module()
    module.FREQUENCY_SHIFT_PROFILES = SYNTHETIC_FREQUENCY_SHIFT_PROFILES
    module.REPAIR_DIFFICULTY_PROFILES = SYNTHETIC_REPAIR_DIFFICULTY_PROFILES
    module.REPAIR_FREQUENCY_TOLERANCE_BY_SPLIT = SYNTHETIC_REPAIR_TOLERANCE_BY_SPLIT
    module.FREQUENCY_TOLERANCE_BY_SPLIT = SYNTHETIC_FREQUENCY_TOLERANCE_BY_SPLIT
    raw_seeds = load_jsonl(SEEDS_PATH)
    tasks = []
    by_type = {"frequency_matching": [], "constrained_power_maximization": [], "feasibility_repair": []}
    by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}

    for raw_seed in raw_seeds:
        split = raw_seed["assigned_split"]
        tuned_seed = module.tune_seed_blueprints(harden_seed(adapt_seed(raw_seed), split["name"]), split)
        for blueprint in tuned_seed["task_blueprints"]:
            task = module.build_task(tuned_seed, blueprint, split)
            task = postprocess_task(task, raw_seed)
            tasks.append(task)
            by_type[task["task_type"]].append(task)
            by_split[task["split"]["name"]].append(task)

    write_jsonl(TASKS_PATH, tasks)
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_frequency_matching.jsonl", by_type["frequency_matching"])
    write_jsonl(
        BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_constrained_power_maximization.jsonl",
        by_type["constrained_power_maximization"],
    )
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_feasibility_repair.jsonl", by_type["feasibility_repair"])
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_train.jsonl", by_split["train"])
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_val.jsonl", by_split["val"])
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_test_id.jsonl", by_split["test-id"])
    write_jsonl(BENCHMARK_DIR / f"synthetic_pilot_{SYNTHETIC_VERSION}_tasks_test_ood.jsonl", by_split["test-ood"])

    counts = {
        "total": len(tasks),
        "frequency_matching": len(by_type["frequency_matching"]),
        "constrained_power_maximization": len(by_type["constrained_power_maximization"]),
        "feasibility_repair": len(by_type["feasibility_repair"]),
    }
    split_counts = Counter(task["split"]["name"] for task in tasks)
    lines = [
        f"# Synthetic Pilot {SYNTHETIC_VERSION.upper()} Tasks",
        "",
        f"- synthetic seeds input: `{len(raw_seeds)}`",
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
