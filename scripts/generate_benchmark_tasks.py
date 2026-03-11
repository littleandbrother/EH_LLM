#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.verifier.v1.adapter import (
    VERIFIER_MODEL_FAMILY,
    VERIFIER_VERSION,
    VIOLATION_LABELS,
)

SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "paper_grounded_task_seeds.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "benchmark_task_generation.md"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def hash_key(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def compute_ood_tags(seeds: list[dict]) -> dict[str, list[str]]:
    freq_values = [
        seed["verifier_mapping"]["excitation_settings"]["frequency_hz"]
        for seed in seeds
        if seed["verifier_mapping"]["excitation_settings"]["frequency_hz"] is not None
    ]
    accel_values = [
        seed["verifier_mapping"]["excitation_settings"]["acceleration_g"]
        for seed in seeds
        if seed["verifier_mapping"]["excitation_settings"]["acceleration_g"] is not None
    ]
    load_values = [
        seed["verifier_mapping"]["load_settings"]["load_resistance_ohm"]
        for seed in seeds
        if seed["verifier_mapping"]["load_settings"]["load_resistance_ohm"] is not None
    ]
    length_values = [
        seed["verifier_mapping"]["design_parameters"]["beam_length_mm"]
        for seed in seeds
        if seed["verifier_mapping"]["design_parameters"]["beam_length_mm"] is not None
    ]
    material_counter = Counter(
        (
            seed["verifier_mapping"]["material_parameters"]["structure_class"],
            seed["verifier_mapping"]["material_parameters"]["piezo_material"],
        )
        for seed in seeds
    )

    def percentile_bounds(values: list[float]) -> tuple[float | None, float | None]:
        if len(values) < 4:
            return None, None
        ordered = sorted(values)
        low_idx = max(0, int(round(0.1 * (len(ordered) - 1))))
        high_idx = min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))
        return ordered[low_idx], ordered[high_idx]

    freq_lo, freq_hi = percentile_bounds(freq_values)
    accel_lo, accel_hi = percentile_bounds(accel_values)
    load_lo, load_hi = percentile_bounds(load_values)
    len_lo, len_hi = percentile_bounds(length_values)

    out = {}
    for seed in seeds:
        tags = []
        paper_id = seed["source_paper_id"]
        mapping = seed["verifier_mapping"]
        design = mapping["design_parameters"]
        excitation = mapping["excitation_settings"]
        load = mapping["load_settings"]
        material_key = (
            mapping["material_parameters"]["structure_class"],
            mapping["material_parameters"]["piezo_material"],
        )

        length = design.get("beam_length_mm")
        if length is not None and len_lo is not None and (length <= len_lo or length >= len_hi):
            tags.append("unseen_geometry_regime")

        freq = excitation.get("frequency_hz")
        accel = excitation.get("acceleration_g")
        if (
            (freq is not None and freq_lo is not None and (freq <= freq_lo or freq >= freq_hi))
            or (accel is not None and accel_lo is not None and (accel <= accel_lo or accel >= accel_hi))
        ):
            tags.append("unseen_excitation_range")

        if material_counter[material_key] <= 2:
            tags.append("unseen_material_combination")

        load_value = load.get("load_resistance_ohm")
        if load_value is not None and load_lo is not None and (load_value <= load_lo or load_value >= load_hi):
            tags.append("unseen_load_regime")

        out[paper_id] = sorted(set(tags))
    return out


def assign_seed_splits(seeds: list[dict]) -> dict[str, dict]:
    ood_tags = compute_ood_tags(seeds)
    total = len(seeds)
    ood_candidates = sorted(
        [seed for seed in seeds if ood_tags[seed["source_paper_id"]]],
        key=lambda seed: (-len(ood_tags[seed["source_paper_id"]]), seed["source_paper_id"]),
    )
    ood_target = min(len(ood_candidates), max(1, round(total * 0.18)))
    ood_ids = {seed["source_paper_id"] for seed in ood_candidates[:ood_target]}

    remaining = [seed for seed in seeds if seed["source_paper_id"] not in ood_ids]
    remaining = sorted(remaining, key=lambda seed: hash_key(seed["source_paper_id"]))
    val_target = max(1, round(total * 0.15))
    test_id_target = max(1, round(total * 0.15))

    split_map = {}
    for seed in seeds:
        paper_id = seed["source_paper_id"]
        if paper_id in ood_ids:
            split_map[paper_id] = {
                "name": "test-ood",
                "ood_tags": ood_tags[paper_id],
            }

    for idx, seed in enumerate(remaining):
        paper_id = seed["source_paper_id"]
        if idx < val_target:
            split_map[paper_id] = {"name": "val", "ood_tags": []}
        elif idx < val_target + test_id_target:
            split_map[paper_id] = {"name": "test-id", "ood_tags": []}
        else:
            split_map[paper_id] = {"name": "train", "ood_tags": []}
    return split_map


def metric_spec(task_type: str) -> dict:
    if task_type == "frequency_matching":
        return {
            "primary_metric": "constraint_satisfaction_rate",
            "secondary_metrics": [
                "frequency_error_hz",
                "frequency_error_pct",
                "invalid_proposal_rate",
                "wall_clock_s",
                "dollar_cost",
            ],
        }
    if task_type == "constrained_power_maximization":
        return {
            "primary_metric": "normalized_objective",
            "secondary_metrics": [
                "feasible_power_uw",
                "invalid_proposal_rate",
                "wall_clock_s",
                "dollar_cost",
            ],
        }
    return {
        "primary_metric": "repair_success_rate",
        "secondary_metrics": [
            "invalid_proposal_rate",
            "wall_clock_s",
            "dollar_cost",
        ],
    }


def degraded_initial_candidate(seed: dict) -> dict:
    base = seed["verifier_mapping"]["design_parameters"]
    candidate = dict(base)
    if candidate.get("beam_length_mm") is not None:
        candidate["beam_length_mm"] = round(candidate["beam_length_mm"] * 0.7, 8)
    elif candidate.get("beam_width_mm") is not None:
        candidate["beam_width_mm"] = round(candidate["beam_width_mm"] * 1.3, 8)
    elif candidate.get("load_resistance_ohm") is not None:
        candidate["load_resistance_ohm"] = round(candidate["load_resistance_ohm"] * 0.1, 8)
    return candidate


def best_known_score(seed: dict, task_type: str, objective: dict) -> float | None:
    outputs = seed["verifier_mapping"]["observed_outputs"]
    if task_type == "constrained_power_maximization":
        power = outputs.get("load_power_w")
        return None if power is None else round(power * 1e6, 6)
    if task_type == "frequency_matching":
        return objective.get("target_value")
    return None


def build_task(seed: dict, blueprint: dict, split: dict) -> dict:
    paper_id = seed["source_paper_id"]
    task_type = blueprint["task_type"]
    task_id = f"{paper_id}::{task_type}"
    reference_solution = dict(seed["verifier_mapping"]["design_parameters"])
    reference_solution["best_known_score"] = best_known_score(seed, task_type, blueprint["objective"])

    task = {
        "schema_version": "vehbench_task_v1",
        "record_type": "benchmark_task",
        "task_id": task_id,
        "source_type": "paper_grounded",
        "task_type": task_type,
        "source_refs": {
            "source_paper_uid": paper_id,
            "source_record_id": seed["seed_id"],
            "generator_name": "generate_benchmark_tasks_v1",
            "generator_seed": None,
        },
        "variable_bounds": blueprint["variable_bounds"],
        "fixed_conditions": blueprint["fixed_conditions"],
        "hard_constraints": blueprint["hard_constraints"],
        "objective": {
            **blueprint["objective"],
            "normalization_reference": paper_id,
        },
        "verifier": {
            "verifier_version": VERIFIER_VERSION,
            "model_family": VERIFIER_MODEL_FAMILY,
            "deterministic": True,
            "violation_labels": VIOLATION_LABELS,
        },
        "budget": {
            "max_queries": blueprint["budget_hint"],
            "max_wall_clock_s": 900,
            "max_tokens": 120000 if task_type == "feasibility_repair" else 60000,
        },
        "metric_spec": metric_spec(task_type),
        "split": split,
        "initial_candidate": degraded_initial_candidate(seed) if task_type == "feasibility_repair" else None,
        "reference_solution": reference_solution,
        "notes": f"paper_grounded_from_curated_gold::{paper_id}",
    }
    return task


def main() -> None:
    seeds = load_jsonl(SEEDS_PATH)
    split_map = assign_seed_splits(seeds)

    tasks = []
    by_type = {"frequency_matching": [], "constrained_power_maximization": [], "feasibility_repair": []}
    by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}

    for seed in seeds:
        split = split_map[seed["source_paper_id"]]
        for blueprint in seed["task_blueprints"]:
            task = build_task(seed, blueprint, split)
            tasks.append(task)
            by_type[task["task_type"]].append(task)
            by_split[task["split"]["name"]].append(task)

    write_jsonl(BENCHMARK_DIR / "tasks_paper_grounded.jsonl", tasks)
    write_jsonl(BENCHMARK_DIR / "tasks_frequency_matching.jsonl", by_type["frequency_matching"])
    write_jsonl(BENCHMARK_DIR / "tasks_constrained_power_maximization.jsonl", by_type["constrained_power_maximization"])
    write_jsonl(BENCHMARK_DIR / "tasks_feasibility_repair.jsonl", by_type["feasibility_repair"])
    write_jsonl(BENCHMARK_DIR / "tasks_train.jsonl", by_split["train"])
    write_jsonl(BENCHMARK_DIR / "tasks_val.jsonl", by_split["val"])
    write_jsonl(BENCHMARK_DIR / "tasks_test_id.jsonl", by_split["test-id"])
    write_jsonl(BENCHMARK_DIR / "tasks_test_ood.jsonl", by_split["test-ood"])

    lines = [
        "# Benchmark Task Generation",
        "",
        f"- seeds input: `{len(seeds)}`",
        f"- total paper-grounded tasks: `{len(tasks)}`",
        f"- frequency_matching: `{len(by_type['frequency_matching'])}`",
        f"- constrained_power_maximization: `{len(by_type['constrained_power_maximization'])}`",
        f"- feasibility_repair: `{len(by_type['feasibility_repair'])}`",
        "",
        "## Split Counts",
        "",
        f"- train: `{len(by_split['train'])}`",
        f"- val: `{len(by_split['val'])}`",
        f"- test-id: `{len(by_split['test-id'])}`",
        f"- test-ood: `{len(by_split['test-ood'])}`",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "seeds": len(seeds),
        "tasks": len(tasks),
        "frequency_matching": len(by_type["frequency_matching"]),
        "constrained_power_maximization": len(by_type["constrained_power_maximization"]),
        "feasibility_repair": len(by_type["feasibility_repair"]),
    }, indent=2))


if __name__ == "__main__":
    main()
