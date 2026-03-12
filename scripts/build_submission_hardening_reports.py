#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REPORT_DIR = REPO_ROOT / "artifacts" / "reports"

RUNS = {
    "zero_shot_repair_test_id": REPO_ROOT
    / "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-id_20260312_062010_734271",
    "zero_shot_repair_test_ood": REPO_ROOT
    / "artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_062010_734255",
    "scalar_reward_repair_test_id": REPO_ROOT
    / "artifacts/runs/scalar_reward_llm/vehbench_scalar_reward_llm_feasibility_repair_test-id_20260312_153146_446662",
    "scalar_reward_repair_test_ood": REPO_ROOT
    / "artifacts/runs/scalar_reward_llm/vehbench_scalar_reward_llm_feasibility_repair_test-ood_20260312_153342_333513",
    "verifier_guided_repair_test_id": REPO_ROOT
    / "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-id_20260312_140513_536411",
    "verifier_guided_repair_test_ood": REPO_ROOT
    / "artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_140611_768999",
    "repeat_frequency_ood": REPO_ROOT
    / "artifacts/runs/repeated_benchmarks/vehbench_repeat_frequency_matching_test-ood_random_search-genetic_algorithm-cma_es-bayesian_optimization-zero_shot_llm-verifier_guided_llm_20260312_154817_064923",
    "repeat_repair_ood": REPO_ROOT
    / "artifacts/runs/repeated_benchmarks/vehbench_repeat_feasibility_repair_test-ood_random_search-genetic_algorithm-cma_es-bayesian_optimization-zero_shot_llm-scalar_reward_llm-verifier_guided_llm_20260312_155503_234461",
}

FEM_SUMMARY = REPO_ROOT / "data_registry/benchmark/fem_frequency_transfer_summary.json"


def read_json(path: Path) -> dict:
    with path.open() as handle:
        return json.load(handle)


def fmt(value: float | None) -> str:
    if value is None:
        return "-"
    return f"{float(value):.3f}"


def fmt_pm(metric: dict[str, float | None]) -> str:
    mean = metric.get("mean")
    std = metric.get("std")
    if mean is None:
        return "-"
    return f"{fmt(mean)}±{fmt(std)}"


def load_solver_row(run_dir: Path, solver_name: str) -> dict:
    summary = read_json(run_dir / "summary.json")
    return dict(summary["solvers"][solver_name])


def load_repeat_solver_row(run_root: Path, solver_name: str) -> dict:
    summary = read_json(run_root / "aggregate_summary.json")
    return dict(summary[solver_name])


def build_ablation_payload() -> dict:
    return {
        "repair_test_id_single_run": {
            "zero_shot_llm": load_solver_row(RUNS["zero_shot_repair_test_id"], "zero_shot_llm"),
            "scalar_reward_llm": load_solver_row(RUNS["scalar_reward_repair_test_id"], "scalar_reward_llm"),
            "verifier_guided_llm": load_solver_row(RUNS["verifier_guided_repair_test_id"], "verifier_guided_llm"),
        },
        "repair_test_ood_single_run": {
            "zero_shot_llm": load_solver_row(RUNS["zero_shot_repair_test_ood"], "zero_shot_llm"),
            "scalar_reward_llm": load_solver_row(RUNS["scalar_reward_repair_test_ood"], "scalar_reward_llm"),
            "verifier_guided_llm": load_solver_row(RUNS["verifier_guided_repair_test_ood"], "verifier_guided_llm"),
        },
        "repair_test_ood_repeated": {
            "zero_shot_llm": load_repeat_solver_row(RUNS["repeat_repair_ood"], "zero_shot_llm"),
            "scalar_reward_llm": load_repeat_solver_row(RUNS["repeat_repair_ood"], "scalar_reward_llm"),
            "verifier_guided_llm": load_repeat_solver_row(RUNS["repeat_repair_ood"], "verifier_guided_llm"),
        },
    }


def build_repeated_payload() -> dict:
    return {
        "frequency_test_ood": read_json(RUNS["repeat_frequency_ood"] / "aggregate_summary.json"),
        "repair_test_ood": read_json(RUNS["repeat_repair_ood"] / "aggregate_summary.json"),
    }


def render_ablation_md(payload: dict) -> str:
    lines = [
        "# Structured Feedback Ablation",
        "",
        "This report isolates whether the gain in repair performance comes from iterative LLM calls alone or from structured verifier feedback with local sensitivity probes and directional search.",
        "",
        "## Single-Run Repair Comparison",
        "",
        "### test-id",
        "",
        "| Solver | Success Rate | Avg Queries Used | Avg Best Objective | Avg Wall Clock (s) |",
        "|---|---:|---:|---:|---:|",
    ]
    for solver in ("zero_shot_llm", "scalar_reward_llm", "verifier_guided_llm"):
        row = payload["repair_test_id_single_run"][solver]
        lines.append(
            f"| {solver} | {fmt(row['success_rate'])} | {fmt(row['avg_queries_used'])} | {fmt(row['avg_best_normalized_objective'])} | {fmt(row['avg_wall_clock_s'])} |"
        )
    lines.extend(
        [
            "",
            "### test-ood",
            "",
            "| Solver | Success Rate | Avg Queries Used | Avg Best Objective | Avg Wall Clock (s) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for solver in ("zero_shot_llm", "scalar_reward_llm", "verifier_guided_llm"):
        row = payload["repair_test_ood_single_run"][solver]
        lines.append(
            f"| {solver} | {fmt(row['success_rate'])} | {fmt(row['avg_queries_used'])} | {fmt(row['avg_best_normalized_objective'])} | {fmt(row['avg_wall_clock_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Repeated OOD Stability (3 seeds)",
            "",
            "| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for solver in ("zero_shot_llm", "scalar_reward_llm", "verifier_guided_llm"):
        row = payload["repair_test_ood_repeated"][solver]
        lines.append(
            f"| {solver} | {fmt_pm(row['success_rate'])} | {fmt_pm(row['avg_queries_to_success'])} | {fmt_pm(row['avg_best_normalized_objective'])} | {fmt_pm(row['avg_wall_clock_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Conclusion",
            "",
            "- Zero-shot Kimi is weak on repair and collapses completely on OOD.",
            "- Scalar-reward-only multi-step LLM remains ineffective: it improves neither success rate nor best objective in a meaningful way.",
            "- Structured verifier feedback changes the outcome: the verifier-guided agent reaches `0.708±0.072` success on repair OOD repeats, far above zero-shot (`0.000±0.000`) and scalar-reward-only (`0.042±0.072`).",
            "",
        ]
    )
    return "\n".join(lines)


def render_repeated_md(payload: dict) -> str:
    order_frequency = [
        "random_search",
        "genetic_algorithm",
        "cma_es",
        "bayesian_optimization",
        "zero_shot_llm",
        "verifier_guided_llm",
    ]
    order_repair = [
        "random_search",
        "genetic_algorithm",
        "cma_es",
        "bayesian_optimization",
        "zero_shot_llm",
        "scalar_reward_llm",
        "verifier_guided_llm",
    ]
    lines = [
        "# Repeated OOD Benchmark Summary",
        "",
        "We repeat the most discriminative OOD evaluations over seeds `7, 17, 27` to estimate result stability.",
        "",
        "## Frequency Matching / test-ood",
        "",
        "| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |",
        "|---|---:|---:|---:|---:|",
    ]
    for solver in order_frequency:
        row = payload["frequency_test_ood"][solver]
        lines.append(
            f"| {solver} | {fmt_pm(row['success_rate'])} | {fmt_pm(row['avg_queries_to_success'])} | {fmt_pm(row['avg_best_normalized_objective'])} | {fmt_pm(row['avg_wall_clock_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Feasibility Repair / test-ood",
            "",
            "| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for solver in order_repair:
        row = payload["repair_test_ood"][solver]
        lines.append(
            f"| {solver} | {fmt_pm(row['success_rate'])} | {fmt_pm(row['avg_queries_to_success'])} | {fmt_pm(row['avg_best_normalized_objective'])} | {fmt_pm(row['avg_wall_clock_s'])} |"
        )
    lines.extend(
        [
            "",
            "## Takeaways",
            "",
            "- BO remains the strongest classical OOD baseline.",
            "- Verifier-guided Kimi matches BO on frequency OOD (`0.600±0.000`) and slightly exceeds it on repair OOD (`0.708±0.072` vs `0.667±0.072`).",
            "- Zero-shot Kimi remains unstable and weak on OOD, especially on repair.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ablation = build_ablation_payload()
    repeated = build_repeated_payload()
    fem = read_json(FEM_SUMMARY)
    payload = {
        "structured_feedback_ablation": ablation,
        "repeated_ood": repeated,
        "fem_frequency_transfer": fem,
        "sources": {name: str(path) for name, path in RUNS.items()},
    }

    (REPORT_DIR / "submission_hardening_summary.json").write_text(json.dumps(payload, indent=2))
    (REPORT_DIR / "structured_feedback_ablation.md").write_text(render_ablation_md(ablation))
    (REPORT_DIR / "repeated_ood_summary.md").write_text(render_repeated_md(repeated))
    print(
        json.dumps(
            {
                "json": str(REPORT_DIR / "submission_hardening_summary.json"),
                "ablation_report": str(REPORT_DIR / "structured_feedback_ablation.md"),
                "repeated_report": str(REPORT_DIR / "repeated_ood_summary.md"),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
