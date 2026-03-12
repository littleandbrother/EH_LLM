#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vehbench.eval import load_tasks, run_benchmark
from vehbench.solvers.registry import AVAILABLE_SOLVERS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run repeated VEHBench evaluations over multiple seeds.")
    parser.add_argument("--tasks-file", default="data_registry/benchmark/tasks_paper_grounded.jsonl")
    parser.add_argument("--task-type", default=None)
    parser.add_argument("--split", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--solver",
        action="append",
        dest="solvers",
        required=True,
        choices=AVAILABLE_SOLVERS,
        help="Solver to evaluate. Repeat flag for multiple solvers.",
    )
    parser.add_argument(
        "--seed",
        action="append",
        dest="seeds",
        type=int,
        required=True,
        help="Seed to include. Repeat flag for multiple seeds.",
    )
    parser.add_argument("--output-root", default="artifacts/runs/repeated_benchmarks")
    parser.add_argument("--disable-frequency-calibration", action="store_true")
    parser.add_argument("--disable-task-anchors", action="store_true")
    return parser.parse_args()


def mean_std(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"mean": None, "std": None}
    if len(values) == 1:
        return {"mean": values[0], "std": 0.0}
    return {"mean": statistics.mean(values), "std": statistics.stdev(values)}


def fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def summarize_seed_runs(seed_runs: list[dict]) -> dict:
    per_solver: dict[str, dict[str, list[float]]] = {}
    for run in seed_runs:
        for solver_name, metrics in run["summary"]["solvers"].items():
            bucket = per_solver.setdefault(
                solver_name,
                {
                    "success_rate": [],
                    "avg_queries_to_success": [],
                    "avg_best_normalized_objective": [],
                    "avg_invalid_proposal_rate": [],
                    "avg_wall_clock_s": [],
                },
            )
            for key in bucket:
                value = metrics.get(key)
                if value is not None:
                    bucket[key].append(float(value))

    summary = {}
    for solver_name, metrics in per_solver.items():
        summary[solver_name] = {metric: mean_std(values) for metric, values in metrics.items()}
    return summary


def build_markdown(
    task_type: str | None,
    split: str | None,
    solvers: list[str],
    seeds: list[int],
    aggregate: dict,
    seed_runs: list[dict],
) -> str:
    lines = [
        "# Repeated Benchmark Summary",
        "",
        f"- task_type: `{task_type}`",
        f"- split: `{split}`",
        f"- solvers: `{', '.join(solvers)}`",
        f"- seeds: `{', '.join(str(seed) for seed in seeds)}`",
        "",
        "| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Invalid Rate (mean±std) | Wall Clock (mean±std) |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for solver_name in solvers:
        row = aggregate.get(solver_name)
        if row is None:
            continue
        lines.append(
            "| "
            + solver_name
            + " | "
            + f"{fmt(row['success_rate']['mean'])}±{fmt(row['success_rate']['std'])}"
            + " | "
            + f"{fmt(row['avg_queries_to_success']['mean'])}±{fmt(row['avg_queries_to_success']['std'])}"
            + " | "
            + f"{fmt(row['avg_best_normalized_objective']['mean'])}±{fmt(row['avg_best_normalized_objective']['std'])}"
            + " | "
            + f"{fmt(row['avg_invalid_proposal_rate']['mean'])}±{fmt(row['avg_invalid_proposal_rate']['std'])}"
            + " | "
            + f"{fmt(row['avg_wall_clock_s']['mean'])}±{fmt(row['avg_wall_clock_s']['std'])}"
            + " |"
        )
    lines.extend(["", "## Seed Runs", ""])
    for run in seed_runs:
        lines.append(f"- seed `{run['seed']}`: `{run['output_dir']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    args = parse_args()
    tasks = load_tasks(args.tasks_file, task_type=args.task_type, split=args.split, limit=args.limit)
    if not tasks:
        raise SystemExit("no tasks selected")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    task_slug = args.task_type or "all_tasks"
    split_slug = args.split or "all_splits"
    solver_slug = "-".join(args.solvers)
    run_root = Path(args.output_root) / f"vehbench_repeat_{task_slug}_{split_slug}_{solver_slug}_{stamp}"
    run_root.mkdir(parents=True, exist_ok=True)

    seed_runs = []
    for seed in args.seeds:
        output_dir = run_root / f"seed_{seed}"
        result = run_benchmark(
            tasks=tasks,
            solver_names=args.solvers,
            seed=seed,
            output_dir=output_dir,
            apply_frequency_calibration=not args.disable_frequency_calibration,
            use_task_anchors=not args.disable_task_anchors,
        )
        seed_runs.append(
            {
                "seed": seed,
                "output_dir": str(output_dir),
                "summary": result["summary"],
            }
        )

    aggregate = summarize_seed_runs(seed_runs)
    (run_root / "seed_runs.json").write_text(json.dumps(seed_runs, indent=2))
    (run_root / "aggregate_summary.json").write_text(json.dumps(aggregate, indent=2))
    (run_root / "aggregate_summary.md").write_text(
        build_markdown(args.task_type, args.split, args.solvers, args.seeds, aggregate, seed_runs)
    )
    print(
        json.dumps(
            {
                "run_root": str(run_root),
                "aggregate": aggregate,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
