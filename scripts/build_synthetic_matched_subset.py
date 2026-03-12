#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TASKS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "synthetic_pilot_v3_tasks.jsonl"
OUT_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_matched_subset_v3.md"

SUBSET_BASENAME = "synthetic_pilot_v3_matched_ood_subset"
TASK_TYPES = ("frequency_matching", "feasibility_repair")
PER_ANCHOR = 3


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def main() -> None:
    tasks = load_jsonl(TASKS_PATH)
    subset_by_type: dict[str, list[dict]] = {}
    chosen_seed_ids: set[str] | None = None

    for task_type in TASK_TYPES:
        rows = [
            task
            for task in tasks
            if task["task_type"] == task_type and (task.get("split") or {}).get("name") == "test-ood"
        ]
        grouped: dict[str, list[dict]] = defaultdict(list)
        for task in rows:
            grouped[task["source_refs"]["parent_anchor_id"]].append(task)
        for anchor_rows in grouped.values():
            anchor_rows.sort(key=lambda task: task["source_refs"]["source_record_id"])

        selected_ids: list[str] = []
        anchors = sorted(grouped)
        for anchor in anchors:
            selected_ids.extend(
                task["source_refs"]["source_record_id"]
                for task in grouped[anchor][:PER_ANCHOR]
            )

        if chosen_seed_ids is None:
            chosen_seed_ids = set(selected_ids)
        else:
            chosen_seed_ids &= set(selected_ids)

    assert chosen_seed_ids is not None
    chosen_seed_ids = set(sorted(chosen_seed_ids))

    all_subset_rows: list[dict] = []
    for task_type in TASK_TYPES:
        rows = [
            task
            for task in tasks
            if task["task_type"] == task_type
            and (task.get("split") or {}).get("name") == "test-ood"
            and task["source_refs"]["source_record_id"] in chosen_seed_ids
        ]
        rows.sort(key=lambda task: (task["source_refs"]["parent_anchor_id"], task["source_refs"]["source_record_id"]))
        subset_by_type[task_type] = rows
        all_subset_rows.extend(rows)

    combined_path = OUT_DIR / f"{SUBSET_BASENAME}.jsonl"
    write_jsonl(combined_path, all_subset_rows)
    for task_type, rows in subset_by_type.items():
        write_jsonl(OUT_DIR / f"{SUBSET_BASENAME}_{task_type}.jsonl", rows)

    anchor_counter = Counter(
        row["source_refs"]["parent_anchor_id"]
        for row in subset_by_type["frequency_matching"]
    )
    lines = [
        "# Synthetic Matched OOD Subset v3",
        "",
        f"- source tasks: `{TASKS_PATH.name}`",
        f"- chosen synthetic seeds: `{len(chosen_seed_ids)}`",
        f"- per-anchor quota: `{PER_ANCHOR}`",
        f"- frequency tasks: `{len(subset_by_type['frequency_matching'])}`",
        f"- repair tasks: `{len(subset_by_type['feasibility_repair'])}`",
        "",
        "## Anchor Coverage",
        "",
    ]
    for anchor, count in sorted(anchor_counter.items()):
        lines.append(f"- `{anchor}`: `{count}`")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({"subset_size_per_type": len(chosen_seed_ids), "combined_path": str(combined_path)}, indent=2))


if __name__ == "__main__":
    main()
