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


SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "synthetic_pilot_v1_seeds.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
TASKS_PATH = BENCHMARK_DIR / "synthetic_pilot_v1_tasks.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_pilot_v1_tasks.md"


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
    task["objective"]["normalization_reference"] = parent_anchor_id
    task["notes"] = f"synthetic_from_anchor::{parent_anchor_id}::{seed['sample_policy']}"
    return task


def main() -> None:
    module = load_task_generator_module()
    raw_seeds = load_jsonl(SEEDS_PATH)
    tasks = []
    by_type = {"frequency_matching": [], "constrained_power_maximization": [], "feasibility_repair": []}
    by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}

    for raw_seed in raw_seeds:
        split = raw_seed["assigned_split"]
        tuned_seed = module.tune_seed_blueprints(adapt_seed(raw_seed), split)
        for blueprint in tuned_seed["task_blueprints"]:
            task = module.build_task(tuned_seed, blueprint, split)
            task = postprocess_task(task, raw_seed)
            tasks.append(task)
            by_type[task["task_type"]].append(task)
            by_split[task["split"]["name"]].append(task)

    write_jsonl(TASKS_PATH, tasks)
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_frequency_matching.jsonl", by_type["frequency_matching"])
    write_jsonl(
        BENCHMARK_DIR / "synthetic_pilot_v1_tasks_constrained_power_maximization.jsonl",
        by_type["constrained_power_maximization"],
    )
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_feasibility_repair.jsonl", by_type["feasibility_repair"])
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_train.jsonl", by_split["train"])
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_val.jsonl", by_split["val"])
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_test_id.jsonl", by_split["test-id"])
    write_jsonl(BENCHMARK_DIR / "synthetic_pilot_v1_tasks_test_ood.jsonl", by_split["test-ood"])

    counts = {
        "total": len(tasks),
        "frequency_matching": len(by_type["frequency_matching"]),
        "constrained_power_maximization": len(by_type["constrained_power_maximization"]),
        "feasibility_repair": len(by_type["feasibility_repair"]),
    }
    split_counts = Counter(task["split"]["name"] for task in tasks)
    lines = [
        "# Synthetic Pilot v1 Tasks",
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
