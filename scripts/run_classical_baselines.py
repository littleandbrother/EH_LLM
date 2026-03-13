#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from vehbench.eval import load_tasks, run_benchmark
from vehbench.solvers import CLASSICAL_SOLVERS


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run VEHBench classical baseline harness.")
    parser.add_argument(
        "--tasks-file",
        default="data_registry/benchmark/tasks_paper_grounded.jsonl",
        help="Benchmark task file to execute.",
    )
    parser.add_argument(
        "--solver",
        default="all",
        choices=("all",) + CLASSICAL_SOLVERS,
        help="Single solver to run or 'all'.",
    )
    parser.add_argument("--task-type", default=None, help="Optional task type filter.")
    parser.add_argument("--split", default=None, help="Optional split filter.")
    parser.add_argument("--limit", type=int, default=None, help="Optional task count limit after filtering.")
    parser.add_argument("--seed", type=int, default=7, help="Base random seed.")
    parser.add_argument(
        "--output-root",
        default="artifacts/runs/classical_baselines",
        help="Directory that will hold run outputs.",
    )
    parser.add_argument(
        "--disable-frequency-calibration",
        action="store_true",
        help="Disable calibrated frequency evaluation.",
    )
    parser.add_argument(
        "--disable-task-anchors",
        action="store_true",
        help="Disable task-local anchors during runtime evaluation.",
    )
    parser.add_argument(
        "--frequency-profile-path",
        default=None,
        help="Optional calibration profile path. If set, use this profile instead of the default verifier-v1 profile.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    tasks = load_tasks(
        args.tasks_file,
        task_type=args.task_type,
        split=args.split,
        limit=args.limit,
    )
    if not tasks:
        raise SystemExit("no tasks selected")

    solvers = list(CLASSICAL_SOLVERS) if args.solver == "all" else [args.solver]
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    task_slug = args.task_type or "all_tasks"
    split_slug = args.split or "all_splits"
    solver_slug = args.solver
    run_id = f"vehbench_classical_{task_slug}_{split_slug}_{solver_slug}_{stamp}"
    output_dir = Path(args.output_root) / run_id
    result = run_benchmark(
        tasks=tasks,
        solver_names=solvers,
        seed=args.seed,
        output_dir=output_dir,
        apply_frequency_calibration=not args.disable_frequency_calibration,
        use_task_anchors=not args.disable_task_anchors,
        calibration_profile_path=args.frequency_profile_path,
    )
    print(json.dumps(
        {
            "run_id": run_id,
            "task_count": len(tasks),
            "solvers": solvers,
            "output_dir": str(output_dir),
            "use_task_anchors": not args.disable_task_anchors,
            "frequency_profile_path": args.frequency_profile_path,
            "summary": result["summary"],
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
