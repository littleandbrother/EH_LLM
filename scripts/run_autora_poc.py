from __future__ import annotations

import argparse
import json
from pathlib import Path

from vehbench.autora_poc import load_demo_task, run_closed_loop_frequency_task
from vehbench.autora_poc.loop import write_poc_outputs
from vehbench.eval.runtime import load_tasks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal AutoRA x VEHBench closed-loop POC.")
    parser.add_argument(
        "--tasks-file",
        default="data_registry/benchmark/synthetic_pilot_v3_tasks_frequency_matching.jsonl",
        help="Path to the synthetic frequency task file.",
    )
    parser.add_argument("--split", default="test-ood", help="Task split to sample from.")
    parser.add_argument("--task-index", type=int, default=0, help="Index within the filtered task list.")
    parser.add_argument("--num-tasks", type=int, default=1, help="How many matching tasks to run sequentially.")
    parser.add_argument("--initial-samples", type=int, default=6, help="Initial random batch size.")
    parser.add_argument("--guided-rounds", type=int, default=3, help="Number of surrogate-guided rounds.")
    parser.add_argument("--proposal-batch", type=int, default=3, help="Candidates per guided round.")
    parser.add_argument("--candidate-pool-size", type=int, default=128, help="Pool size for surrogate ranking.")
    parser.add_argument("--seed", type=int, default=7, help="Random seed.")
    parser.add_argument(
        "--output-dir",
        default="artifacts/reports/autora_poc",
        help="Directory for summary/traces/report outputs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.num_tasks <= 1:
        task = load_demo_task(args.tasks_file, split=args.split, index=args.task_index)
        state, summary = run_closed_loop_frequency_task(
            task,
            initial_samples=args.initial_samples,
            guided_rounds=args.guided_rounds,
            proposal_batch=args.proposal_batch,
            candidate_pool_size=args.candidate_pool_size,
            random_state=args.seed,
        )
        outputs = write_poc_outputs(state, summary, args.output_dir)
        print(json.dumps({"summary": summary, "outputs": {k: str(v) for k, v in outputs.items()}}, indent=2))
        return 0

    tasks = load_tasks(args.tasks_file, task_type="frequency_matching", split=args.split)
    selected = tasks[args.task_index : args.task_index + args.num_tasks]
    if not selected:
        raise IndexError("No tasks matched the requested split/range")

    root = Path(args.output_dir)
    root.mkdir(parents=True, exist_ok=True)
    batch_records = []
    for local_idx, task in enumerate(selected):
        state, summary = run_closed_loop_frequency_task(
            task,
            initial_samples=args.initial_samples,
            guided_rounds=args.guided_rounds,
            proposal_batch=args.proposal_batch,
            candidate_pool_size=args.candidate_pool_size,
            random_state=args.seed + local_idx,
        )
        task_dir = root / f"task_{args.task_index + local_idx:03d}"
        outputs = write_poc_outputs(state, summary, task_dir)
        batch_records.append(
            {
                "task_index": args.task_index + local_idx,
                "task_id": summary["task_id"],
                "summary": summary,
                "outputs": {k: str(v) for k, v in outputs.items()},
            }
        )

    feasible = sum(1 for item in batch_records if item["summary"]["feasible_found"])
    best_errors = [
        item["summary"]["best_frequency_error_pct"]
        for item in batch_records
        if item["summary"]["best_frequency_error_pct"] is not None
    ]
    aggregate = {
        "task_count": len(batch_records),
        "feasible_rate": 0.0 if not batch_records else round(feasible / len(batch_records), 6),
        "mean_best_frequency_error_pct": None
        if not best_errors
        else round(sum(best_errors) / len(best_errors), 6),
        "tasks": batch_records,
    }
    summary_path = root / "autora_poc_frequency_batch_summary.json"
    report_path = root / "autora_poc_frequency_batch_report.md"
    summary_path.write_text(json.dumps(aggregate, indent=2, ensure_ascii=False) + "\n")
    lines = [
        "# AutoRA POC Frequency Batch",
        "",
        f"- task_count: `{aggregate['task_count']}`",
        f"- feasible_rate: `{aggregate['feasible_rate']}`",
        f"- mean_best_frequency_error_pct: `{aggregate['mean_best_frequency_error_pct']}`",
        "",
        "## Task Results",
    ]
    for item in batch_records:
        s = item["summary"]
        lines.append(
            f"- `{item['task_index']}` `{s['task_id']}`: feasible={s['feasible_found']}, "
            f"best_error_pct={s['best_frequency_error_pct']}, queries={s['queries']}"
        )
    report_path.write_text("\n".join(lines) + "\n")
    print(json.dumps({"summary": aggregate, "outputs": {"summary": str(summary_path), "report": str(report_path)}}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
