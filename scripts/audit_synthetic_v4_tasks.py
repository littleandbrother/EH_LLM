#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.eval.runtime import build_request_from_task, initial_candidate, load_tasks, midpoint_candidate
from vehbench.verifier.v1.evaluator import evaluate_request


TASKS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "synthetic_v4_pilot_1k_tasks.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_v4_pilot_1k_task_audit.md"


def audit_frequency(tasks: list[dict]) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for task in tasks:
        if task["task_type"] != "frequency_matching":
            continue
        split = (task.get("split") or {}).get("name") or "unknown"
        candidate = midpoint_candidate(task)
        request = build_request_from_task(task, candidate, f"{task['task_id']}::midpoint")
        interaction = evaluate_request(
            request,
            task=task,
            apply_frequency_calibration=True,
            use_task_anchors=False,
        )
        counts[split][0] += 1
        counts[split][1] += int(bool(interaction["response"]["is_feasible"]))
    return {key: (value[0], value[1]) for key, value in counts.items()}


def audit_repair(tasks: list[dict]) -> dict[str, tuple[int, int]]:
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for task in tasks:
        if task["task_type"] != "feasibility_repair":
            continue
        split = (task.get("split") or {}).get("name") or "unknown"
        candidate = initial_candidate(task)
        if candidate is None:
            continue
        request = build_request_from_task(task, candidate, f"{task['task_id']}::initial")
        interaction = evaluate_request(
            request,
            task=task,
            apply_frequency_calibration=True,
            use_task_anchors=False,
        )
        counts[split][0] += 1
        counts[split][1] += int(bool(interaction["response"]["is_feasible"]))
    return {key: (value[0], value[1]) for key, value in counts.items()}


def main() -> None:
    tasks = load_tasks(TASKS_PATH)
    type_counts = Counter(task["task_type"] for task in tasks)
    split_counts = Counter((task.get("split") or {}).get("name") for task in tasks)
    frequency_audit = audit_frequency(tasks)
    repair_audit = audit_repair(tasks)

    lines = [
        "# Synthetic v4 Pilot 1k Task Audit",
        "",
        "## Inventory",
        "",
    ]
    for key in ("frequency_matching", "constrained_power_maximization", "feasibility_repair"):
        lines.append(f"- {key}: `{type_counts.get(key, 0)}`")
    lines.extend(["", "## Split Counts", ""])
    for key in ("train", "val", "test-id", "test-ood"):
        lines.append(f"- {key}: `{split_counts.get(key, 0)}`")
    lines.extend(["", "## Midpoint Feasibility (Frequency)", ""])
    for key in ("train", "val", "test-id", "test-ood"):
        total, feasible = frequency_audit.get(key, (0, 0))
        rate = None if total == 0 else feasible / total
        lines.append(f"- {key}: `{feasible}/{total}` feasible (`{rate}`)")
    lines.extend(["", "## Initial Candidate Feasibility (Repair)", ""])
    for key in ("train", "val", "test-id", "test-ood"):
        total, feasible = repair_audit.get(key, (0, 0))
        rate = None if total == 0 else feasible / total
        lines.append(f"- {key}: `{feasible}/{total}` feasible (`{rate}`)")

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "type_counts": type_counts,
                "split_counts": split_counts,
                "frequency_midpoint": frequency_audit,
                "repair_initial": repair_audit,
                "report": str(REPORT_PATH),
            },
            indent=2,
            default=dict,
        )
    )


if __name__ == "__main__":
    main()
