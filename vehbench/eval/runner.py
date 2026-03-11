from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from .runtime import TaskSession, summarize_task_session
from ..solvers.registry import build_solver


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=True) + "\n")


def summarize_run(task_summaries: list[dict]) -> dict:
    grouped: dict[str, list[dict]] = defaultdict(list)
    by_solver_task: dict[str, list[dict]] = defaultdict(list)
    for summary in task_summaries:
        grouped[summary["solver_name"]].append(summary)
        by_solver_task[f"{summary['solver_name']}::{summary['task_type']}"].append(summary)

    aggregate = {}
    for key, rows in grouped.items():
        success_rows = [row for row in rows if row["success"]]
        aggregate[key] = {
            "task_count": len(rows),
            "success_rate": 0.0 if not rows else len(success_rows) / len(rows),
            "avg_queries_used": 0.0 if not rows else sum(row["queries_used"] for row in rows) / len(rows),
            "avg_queries_to_success": None
            if not success_rows
            else sum(row["queries_to_success"] for row in success_rows) / len(success_rows),
            "avg_invalid_proposal_rate": 0.0
            if not rows
            else sum(row["invalid_proposal_rate"] for row in rows) / len(rows),
            "avg_best_normalized_objective": 0.0
            if not rows
            else sum((row["best_normalized_objective"] or 0.0) for row in rows) / len(rows),
            "avg_wall_clock_s": 0.0 if not rows else sum(row["total_wall_clock_s"] for row in rows) / len(rows),
        }

    per_task_type = {}
    for key, rows in by_solver_task.items():
        success_rows = [row for row in rows if row["success"]]
        per_task_type[key] = {
            "task_count": len(rows),
            "success_rate": 0.0 if not rows else len(success_rows) / len(rows),
            "avg_best_normalized_objective": 0.0
            if not rows
            else sum((row["best_normalized_objective"] or 0.0) for row in rows) / len(rows),
        }

    return {
        "solvers": aggregate,
        "per_solver_task_type": per_task_type,
    }


def run_benchmark(
    tasks: list[dict],
    solver_names: list[str],
    seed: int,
    output_dir: str | Path,
    apply_frequency_calibration: bool = True,
    use_task_anchors: bool = True,
) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    interaction_rows: list[dict] = []
    task_summaries: list[dict] = []
    for solver_index, solver_name in enumerate(solver_names):
        solver = build_solver(solver_name, seed=seed + solver_index * 1000)
        for task_index, task in enumerate(tasks):
            session = TaskSession(
                task=task,
                solver_name=solver.name,
                apply_frequency_calibration=apply_frequency_calibration,
                use_task_anchors=use_task_anchors,
            )
            solver.solve(session, task_seed=seed + solver_index * 1000 + task_index)
            interaction_rows.extend(session.records)
            task_summaries.append(summarize_task_session(session))

    summary = summarize_run(task_summaries)
    _write_jsonl(output_path / "interactions.jsonl", interaction_rows)
    _write_jsonl(output_path / "task_summaries.jsonl", task_summaries)
    with (output_path / "summary.json").open("w") as handle:
        json.dump(summary, handle, indent=2)
    return {
        "interaction_rows": interaction_rows,
        "task_summaries": task_summaries,
        "summary": summary,
    }
