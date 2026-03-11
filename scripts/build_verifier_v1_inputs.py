#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.verifier.v1.adapter import build_request_record

SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "paper_grounded_task_seeds.jsonl"
TASKS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "tasks_paper_grounded.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "verifier_v1_input_adapter.md"


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


def main() -> None:
    seeds = {row["seed_id"]: row for row in load_jsonl(SEEDS_PATH)}
    tasks = load_jsonl(TASKS_PATH)

    request_rows = []
    skipped = []
    for task in tasks:
        seed = seeds[task["source_refs"]["source_record_id"]]
        if seed["mapping_status"] != "ready":
            skipped.append(task["task_id"])
            continue
        request_rows.append(build_request_record(task, seed))

    write_jsonl(BENCHMARK_DIR / "verifier_v1_requests.jsonl", request_rows)
    (BENCHMARK_DIR / "verifier_v1_skipped_tasks.json").write_text(
        json.dumps({"skipped_tasks": skipped}, indent=2)
    )

    lines = [
        "# Verifier v1 Input Adapter",
        "",
        f"- total paper-grounded tasks: `{len(tasks)}`",
        f"- ready verifier requests: `{len(request_rows)}`",
        f"- skipped due to partial mapping: `{len(skipped)}`",
        "",
        "The request payloads are derived from:",
        "- task record fields",
        "- seed verifier mappings",
        "- reference solution for frequency/power tasks",
        "- synthetic invalid initial candidate for repair tasks",
    ]
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "tasks": len(tasks),
        "ready_requests": len(request_rows),
        "skipped": len(skipped),
    }, indent=2))


if __name__ == "__main__":
    main()
