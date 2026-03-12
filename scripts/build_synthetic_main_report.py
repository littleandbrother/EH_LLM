#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REPORT_MD = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_main_comparison_v3.md"
REPORT_JSON = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_main_comparison_v3.json"

FULL_CLASSICAL = {
    "frequency_matching": PROJECT_ROOT / "artifacts" / "runs" / "classical_baselines" / "vehbench_classical_frequency_matching_test-ood_all_20260312_232301_859696" / "summary.json",
    "feasibility_repair": PROJECT_ROOT / "artifacts" / "runs" / "classical_baselines" / "vehbench_classical_feasibility_repair_test-ood_all_20260312_232301_925792" / "summary.json",
}

MATCHED_SUBSET = {
    "frequency_matching": {
        "classical": PROJECT_ROOT / "artifacts" / "runs" / "classical_baselines" / "vehbench_classical_all_tasks_all_splits_all_20260313_002147_799045" / "summary.json",
        "zero_shot_llm": PROJECT_ROOT / "artifacts" / "runs" / "zero_shot_llm" / "vehbench_zero_shot_llm_all_tasks_all_splits_20260313_002445_184354" / "summary.json",
        "verifier_guided_llm": PROJECT_ROOT / "artifacts" / "runs" / "verifier_guided_llm" / "vehbench_verifier_guided_llm_all_tasks_all_splits_20260313_002802_989985" / "summary.json",
    },
    "feasibility_repair": {
        "classical": PROJECT_ROOT / "artifacts" / "runs" / "classical_baselines" / "vehbench_classical_all_tasks_all_splits_all_20260313_002147_799079" / "summary.json",
        "zero_shot_llm": PROJECT_ROOT / "artifacts" / "runs" / "zero_shot_llm" / "vehbench_zero_shot_llm_all_tasks_all_splits_20260313_002557_983721" / "summary.json",
        "verifier_guided_llm": PROJECT_ROOT / "artifacts" / "runs" / "verifier_guided_llm" / "vehbench_verifier_guided_llm_all_tasks_all_splits_20260313_002703_713810" / "summary.json",
    },
}


def load_summary(path: Path) -> dict:
    return json.loads(path.read_text())


def fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{value:.3f}"


def main() -> None:
    full_rows: list[dict] = []
    subset_rows: list[dict] = []

    for task_type, path in FULL_CLASSICAL.items():
        data = load_summary(path)
        for solver_name, summary in data["solvers"].items():
            full_rows.append(
                {
                    "evaluation_set": "full_test_ood",
                    "task_type": task_type,
                    "solver": solver_name,
                    **summary,
                }
            )

    for task_type, bundle in MATCHED_SUBSET.items():
        classical = load_summary(bundle["classical"])
        for solver_name, summary in classical["solvers"].items():
            subset_rows.append(
                {
                    "evaluation_set": "matched_subset_24",
                    "task_type": task_type,
                    "solver": solver_name,
                    **summary,
                }
            )
        for solver_label in ("zero_shot_llm", "verifier_guided_llm"):
            summary = load_summary(bundle[solver_label])["solvers"][solver_label]
            subset_rows.append(
                {
                    "evaluation_set": "matched_subset_24",
                    "task_type": task_type,
                    "solver": solver_label,
                    **summary,
                }
            )

    payload = {
        "full_test_ood": full_rows,
        "matched_subset_24": subset_rows,
    }
    REPORT_JSON.write_text(json.dumps(payload, indent=2))

    lines = [
        "# Synthetic Main Comparison v3",
        "",
        "- synthetic benchmark: `synthetic_pilot_v3_tasks.jsonl`",
        "- matched subset: `24` tasks per family, stratified across `8` OOD anchors (`3` synthetic seeds per anchor)",
        "- runtime setting: calibrated frequency on, task anchors off",
        "- zero-shot / verifier-guided model: `kimi-k2.5` via DashScope coding endpoint",
        "",
        "## Full Test-OOD Classical Baselines",
        "",
        "| Task | Solver | Success | Avg Queries To Success | Avg Wall Clock (s) |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for task_type in ("frequency_matching", "feasibility_repair"):
        task_rows = [row for row in full_rows if row["task_type"] == task_type]
        for row in task_rows:
            lines.append(
                f"| `{task_type}` | `{row['solver']}` | `{fmt(row['success_rate'])}` | `{fmt(row['avg_queries_to_success'])}` | `{fmt(row['avg_wall_clock_s'])}` |"
            )
    lines.extend(
        [
            "",
            "## Matched OOD Subset (24 Tasks Per Family)",
            "",
            "| Task | Solver | Success | Avg Queries Used | Avg Queries To Success | Avg Wall Clock (s) |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for task_type in ("frequency_matching", "feasibility_repair"):
        task_rows = [row for row in subset_rows if row["task_type"] == task_type]
        solver_order = [
            "random_search",
            "genetic_algorithm",
            "cma_es",
            "bayesian_optimization",
            "zero_shot_llm",
            "verifier_guided_llm",
        ]
        task_rows = sorted(task_rows, key=lambda row: solver_order.index(row["solver"]))
        for row in task_rows:
            lines.append(
                f"| `{task_type}` | `{row['solver']}` | `{fmt(row['success_rate'])}` | `{fmt(row['avg_queries_used'])}` | `{fmt(row['avg_queries_to_success'])}` | `{fmt(row['avg_wall_clock_s'])}` |"
            )

    lines.extend(
        [
            "",
            "## Takeaways",
            "",
            "- `synthetic v3` no longer collapses on OOD: full classical `test-ood` now separates solvers instead of pushing them all to near-zero or near-one.",
            "- On the stratified matched subset, `verifier_guided_llm` now clearly beats `zero_shot_llm` on both families.",
            "- The biggest gain is on `feasibility_repair`: after the low-budget policy fix, verifier-guided repair rises to `0.708`, well above zero-shot (`0.083`) and the strongest matched-subset classical baseline (`random_search = 0.375`).",
            "- On `frequency_matching`, verifier-guided improves over zero-shot (`0.458` vs `0.292`) but still trails the strongest classical baselines on the matched subset.",
        ]
    )
    REPORT_MD.write_text("\n".join(lines) + "\n")
    print(json.dumps({"markdown": str(REPORT_MD), "json": str(REPORT_JSON)}, indent=2))


if __name__ == "__main__":
    main()
