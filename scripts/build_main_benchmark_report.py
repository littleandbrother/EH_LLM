#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_RUNS = {
    ("frequency_matching", "test-id"): {
        "classical": "artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-id_all_20260311_155132_113319",
        "zero_shot_llm": "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-id_20260312_061601_216713",
        "verifier_guided_llm": "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-id_20260312_144951_168102",
    },
    ("frequency_matching", "test-ood"): {
        "classical": "artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-ood_all_20260311_155132_227910",
        "zero_shot_llm": "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_061601_216649",
        "verifier_guided_llm": "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_145028_529382",
    },
    ("feasibility_repair", "test-id"): {
        "classical": "artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-id_all_20260311_170126_997067",
        "zero_shot_llm": "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-id_20260312_062010_734271",
        "verifier_guided_llm": "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-id_20260312_140513_536411",
    },
    ("feasibility_repair", "test-ood"): {
        "classical": "artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-ood_all_20260311_170126_995736",
        "zero_shot_llm": "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_062010_734255",
        "verifier_guided_llm": "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_140611_768999",
    },
}

SOLVER_ORDER = (
    "random_search",
    "genetic_algorithm",
    "cma_es",
    "bayesian_optimization",
    "zero_shot_llm",
    "verifier_guided_llm",
)

SOLVER_LABELS = {
    "random_search": "Random Search",
    "genetic_algorithm": "GA",
    "cma_es": "CMA-ES",
    "bayesian_optimization": "BO",
    "zero_shot_llm": "Kimi Zero-Shot",
    "verifier_guided_llm": "Kimi Verifier-Guided",
}


def load_summary(run_dir: Path) -> dict:
    with (run_dir / "summary.json").open() as handle:
        return json.load(handle)


def round_metric(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def build_combined_table() -> dict:
    tables: dict[str, dict] = {}
    for (task_type, split), run_map in DEFAULT_RUNS.items():
        rows: dict[str, dict] = {}
        source_runs: dict[str, str] = {}
        for family, relative_run in run_map.items():
            run_dir = REPO_ROOT / relative_run
            source_runs[family] = str(run_dir)
            summary = load_summary(run_dir)
            for solver_name, metrics in summary["solvers"].items():
                rows[solver_name] = {
                    "task_count": metrics["task_count"],
                    "success_rate": metrics["success_rate"],
                    "avg_queries_to_success": metrics["avg_queries_to_success"],
                    "avg_best_normalized_objective": metrics["avg_best_normalized_objective"],
                    "avg_invalid_proposal_rate": metrics["avg_invalid_proposal_rate"],
                    "avg_wall_clock_s": metrics["avg_wall_clock_s"],
                }
        tables[f"{task_type}::{split}"] = {
            "task_type": task_type,
            "split": split,
            "source_runs": source_runs,
            "rows": rows,
        }
    return tables


def render_markdown(tables: dict[str, dict]) -> str:
    lines: list[str] = []
    lines.append("# Main Benchmark Comparison (v1)")
    lines.append("")
    lines.append("Runtime policy:")
    lines.append("")
    lines.append("- calibrated frequency: `on`")
    lines.append("- task-local anchors: `off`")
    lines.append("- zero-shot / verifier-guided model: `kimi-k2.5` via DashScope coding endpoint")
    lines.append("")
    for key in (
        "frequency_matching::test-id",
        "frequency_matching::test-ood",
        "feasibility_repair::test-id",
        "feasibility_repair::test-ood",
    ):
        block = tables[key]
        lines.append(f"## {block['task_type']} / {block['split']}")
        lines.append("")
        for family, run_dir in block["source_runs"].items():
            lines.append(f"- {family} run: `{run_dir}`")
        lines.append("")
        lines.append("| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate | Avg Wall Clock (s) |")
        lines.append("|---|---:|---:|---:|---:|---:|")
        for solver_name in SOLVER_ORDER:
            row = block["rows"].get(solver_name)
            if row is None:
                continue
            lines.append(
                "| "
                + SOLVER_LABELS[solver_name]
                + " | "
                + round_metric(row["success_rate"])
                + " | "
                + round_metric(row["avg_queries_to_success"])
                + " | "
                + round_metric(row["avg_best_normalized_objective"])
                + " | "
                + round_metric(row["avg_invalid_proposal_rate"])
                + " | "
                + round_metric(row["avg_wall_clock_s"])
                + " |"
            )
        lines.append("")

    lines.append("## Decision")
    lines.append("")
    lines.append("- keep verifier-guided repair in the primary result table; it is now competitive rather than exploratory")
    lines.append("- extend the same local sensitivity + directional search policy to `frequency_matching` in the main benchmark view")
    lines.append("- reason: verifier-guided frequency reaches `1.000` on `test-id` and `0.600` on `test-ood`, matching the current best OOD classical success rate (`BO = 0.600`) while clearly beating Kimi zero-shot (`0.500 / 0.200`)")
    lines.append("- reason: verifier-guided repair reaches `1.000` on `test-id` and `0.750` on `test-ood`, matching or exceeding the strongest classical baseline and decisively beating zero-shot repair")
    lines.append("")
    lines.append("## Supplementary Hardening Reports")
    lines.append("")
    lines.append("- structured-feedback ablation: `artifacts/reports/structured_feedback_ablation.md`")
    lines.append("- repeated OOD stability: `artifacts/reports/repeated_ood_summary.md`")
    lines.append("- independent FEM transfer: `artifacts/reports/fem_frequency_transfer.md`")
    lines.append("")
    return "\n".join(lines) + "\n"


def main() -> None:
    tables = build_combined_table()
    report_path = REPO_ROOT / "artifacts/reports/main_benchmark_comparison_v1.md"
    json_path = REPO_ROOT / "artifacts/reports/main_benchmark_comparison_v1.json"
    report_path.write_text(render_markdown(tables))
    json_path.write_text(json.dumps(tables, indent=2))
    print(json.dumps({"report": str(report_path), "json": str(json_path)}, indent=2))


if __name__ == "__main__":
    main()
