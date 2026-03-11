#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.verifier.v1 import evaluate_request_record, load_frequency_profile

BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REQUESTS_PATH = BENCHMARK_DIR / "verifier_v1_requests.jsonl"
TASKS_PATH = BENCHMARK_DIR / "tasks_paper_grounded.jsonl"
SEEDS_PATH = BENCHMARK_DIR / "paper_grounded_task_seeds.jsonl"
INTERACTIONS_PATH = BENCHMARK_DIR / "verifier_v1_interactions.jsonl"
SUMMARY_PATH = BENCHMARK_DIR / "verifier_v1_backsub_summary.json"
CANONICAL_PATH = BENCHMARK_DIR / "verifier_v1_literature_backsub_predictions.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "verifier_v1_literature_backsub.md"


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


def mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def median(values: list[float]) -> float | None:
    return None if not values else statistics.median(values)


def safe_pct_error(pred: float | None, obs: float | None) -> float | None:
    if pred is None or obs is None or obs == 0:
        return None
    return abs(pred - obs) / abs(obs) * 100.0


def summarize_canonical(rows: list[dict], predicted_key: str = "predicted") -> dict:
    freq_abs = []
    freq_pct = []
    power_pct = []
    power_log_ratio_abs = []
    decision_matches = []

    for row in rows:
        predicted = row[predicted_key]
        observed = row["observed"]
        task = row["task"]
        pred_freq = predicted.get("resonant_frequency_hz")
        obs_freq = observed.get("resonant_frequency_hz")
        pred_power = predicted.get("load_power_uw")
        obs_power = observed.get("load_power_uw")
        if pred_freq is not None and obs_freq is not None:
            freq_abs.append(abs(pred_freq - obs_freq))
            pct = safe_pct_error(pred_freq, obs_freq)
            if pct is not None:
                freq_pct.append(pct)
            target = task["fixed_conditions"].get("target_resonant_frequency_hz")
            tol = (task.get("hard_constraints") or {}).get("frequency_error_tolerance_pct") or 5.0
            if target is not None:
                pred_ok = abs(pred_freq - target) / max(abs(target), 1e-9) * 100.0 <= tol
                obs_ok = abs(obs_freq - target) / max(abs(target), 1e-9) * 100.0 <= tol
                decision_matches.append(pred_ok == obs_ok)
        if pred_power is not None and obs_power is not None and pred_power > 0 and obs_power > 0:
            pct = safe_pct_error(pred_power, obs_power)
            if pct is not None:
                power_pct.append(pct)
            power_log_ratio_abs.append(abs(math.log10(pred_power / obs_power)))

    return {
        "count": len(rows),
        "frequency_mae_hz": mean(freq_abs),
        "frequency_mape_pct": mean(freq_pct),
        "frequency_median_ape_pct": median(freq_pct),
        "power_mape_pct": mean(power_pct),
        "power_median_ape_pct": median(power_pct),
        "power_median_abs_log10_ratio": median(power_log_ratio_abs),
        "frequency_decision_consistency": None if not decision_matches else sum(decision_matches) / len(decision_matches),
    }


def fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def main() -> None:
    requests = load_jsonl(REQUESTS_PATH)
    tasks = {row["task_id"]: row for row in load_jsonl(TASKS_PATH)}
    seeds = {row["seed_id"]: row for row in load_jsonl(SEEDS_PATH)}

    calibration_profile = load_frequency_profile()
    interactions = []
    coverage_by_type: dict[str, dict[str, int]] = {}
    canonical_rows = []
    task_aware_power_rows = []

    for request_row in requests:
        task = tasks[request_row["task_id"]]
        interaction = evaluate_request_record(request_row, task=task)
        interactions.append(interaction)

        task_type = task["task_type"]
        bucket = coverage_by_type.setdefault(
            task_type,
            {"count": 0, "valid": 0, "feasible": 0},
        )
        bucket["count"] += 1
        bucket["valid"] += int(interaction["response"]["is_valid_request"])
        bucket["feasible"] += int(interaction["response"]["is_feasible"])

        if request_row["candidate_role"] == "reference_solution" and task_type == "frequency_matching":
            seed = seeds[request_row["source_seed_id"]]
            observed = seed["verifier_mapping"]["observed_outputs"]
            raw_interaction = evaluate_request_record(request_row)
            calibrated_interaction = evaluate_request_record(
                request_row,
                apply_frequency_calibration=True,
                calibration_profile=calibration_profile,
            )
            canonical_rows.append(
                {
                    "source_paper_id": request_row["source_paper_id"],
                    "source_seed_id": request_row["source_seed_id"],
                    "task_id": request_row["task_id"],
                    "task": task,
                    "predicted": raw_interaction["response"]["outputs"],
                    "calibrated_predicted": calibrated_interaction["response"]["outputs"],
                    "task_aware_predicted": interaction["response"]["outputs"],
                    "observed": {
                        "resonant_frequency_hz": observed.get("resonant_frequency_hz"),
                        "load_power_uw": None
                        if observed.get("load_power_w") is None
                        else observed["load_power_w"] * 1e6,
                        "open_circuit_voltage_v": observed.get("open_circuit_voltage_v"),
                        "bandwidth_hz": observed.get("bandwidth_hz"),
                    },
                    "diagnostics": raw_interaction["response"]["diagnostics"],
                }
            )
        if request_row["candidate_role"] == "reference_solution" and task_type == "constrained_power_maximization":
            seed = seeds[request_row["source_seed_id"]]
            observed = seed["verifier_mapping"]["observed_outputs"]
            task_aware_power_rows.append(
                {
                    "source_paper_id": request_row["source_paper_id"],
                    "source_seed_id": request_row["source_seed_id"],
                    "task_id": request_row["task_id"],
                    "task": task,
                    "predicted": interaction["response"]["outputs"],
                    "observed": {
                        "resonant_frequency_hz": observed.get("resonant_frequency_hz"),
                        "load_power_uw": None
                        if observed.get("load_power_w") is None
                        else observed["load_power_w"] * 1e6,
                        "open_circuit_voltage_v": observed.get("open_circuit_voltage_v"),
                        "bandwidth_hz": observed.get("bandwidth_hz"),
                    },
                    "diagnostics": interaction["response"]["diagnostics"],
                }
            )

    write_jsonl(INTERACTIONS_PATH, interactions)
    write_jsonl(CANONICAL_PATH, canonical_rows)

    coverage = {
        "total_requests": len(interactions),
        "valid_requests": sum(item["response"]["is_valid_request"] for item in interactions),
        "feasible_requests": sum(item["response"]["is_feasible"] for item in interactions),
        "by_task_type": coverage_by_type,
    }
    canonical_metrics_raw = summarize_canonical(canonical_rows, predicted_key="predicted")
    canonical_metrics_calibrated = summarize_canonical(canonical_rows, predicted_key="calibrated_predicted")
    canonical_metrics_task_aware_freq = summarize_canonical(canonical_rows, predicted_key="task_aware_predicted")
    canonical_metrics_task_aware_power = summarize_canonical(task_aware_power_rows, predicted_key="predicted")
    summary = {
        "coverage": coverage,
        "literature_backsub_raw": canonical_metrics_raw,
        "literature_backsub_calibrated_frequency": canonical_metrics_calibrated,
        "literature_backsub_task_aware_frequency": canonical_metrics_task_aware_freq,
        "literature_backsub_task_aware_power": canonical_metrics_task_aware_power,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))

    lines = [
        "# Verifier v1 Literature Back-Substitution",
        "",
        "This report evaluates the executable `vehbench/verifier/v1` evaluator on the ready paper-grounded verifier requests.",
        "",
        "## Batch Coverage",
        "",
        f"- total requests executed: `{coverage['total_requests']}`",
        f"- valid requests: `{coverage['valid_requests']}`",
        f"- feasible requests: `{coverage['feasible_requests']}`",
        "",
        "### By Task Type",
        "",
    ]
    for task_type, bucket in coverage_by_type.items():
        lines.append(
            f"- `{task_type}`: count=`{bucket['count']}`, valid=`{bucket['valid']}`, feasible=`{bucket['feasible']}`"
        )
    lines.extend(
        [
            "",
            "## Canonical Literature Back-Substitution",
            "",
            "Canonical rows use the `reference_solution` / `frequency_matching` design for each ready seed so synthetic repair candidates do not contaminate the literature comparison.",
            "The benchmark evaluator itself is task-aware; the metrics below are computed from the raw physics path without task-local anchoring.",
            "",
            f"- canonical papers evaluated: `{canonical_metrics_raw['count']}`",
            f"- raw frequency MAE (Hz): `{fmt(canonical_metrics_raw['frequency_mae_hz'])}`",
            f"- raw frequency MAPE (%): `{fmt(canonical_metrics_raw['frequency_mape_pct'])}`",
            f"- raw frequency median APE (%): `{fmt(canonical_metrics_raw['frequency_median_ape_pct'])}`",
            f"- raw power MAPE (%): `{fmt(canonical_metrics_raw['power_mape_pct'])}`",
            f"- raw power median APE (%): `{fmt(canonical_metrics_raw['power_median_ape_pct'])}`",
            f"- raw power median |log10(pred/obs)|: `{fmt(canonical_metrics_raw['power_median_abs_log10_ratio'])}`",
            f"- raw frequency decision consistency: `{fmt(canonical_metrics_raw['frequency_decision_consistency'])}`",
            "",
            "### Calibrated Raw Frequency",
            "",
            f"- calibrated frequency MAPE (%): `{fmt(canonical_metrics_calibrated['frequency_mape_pct'])}`",
            f"- calibrated frequency median APE (%): `{fmt(canonical_metrics_calibrated['frequency_median_ape_pct'])}`",
            f"- calibrated frequency decision consistency: `{fmt(canonical_metrics_calibrated['frequency_decision_consistency'])}`",
            "",
            "### Task-Aware Benchmark Evaluator",
            "",
            f"- task-aware frequency MAPE (%): `{fmt(canonical_metrics_task_aware_freq['frequency_mape_pct'])}`",
            f"- task-aware frequency decision consistency: `{fmt(canonical_metrics_task_aware_freq['frequency_decision_consistency'])}`",
            f"- task-aware power MAPE (%): `{fmt(canonical_metrics_task_aware_power['power_mape_pct'])}`",
            f"- task-aware power median APE (%): `{fmt(canonical_metrics_task_aware_power['power_median_ape_pct'])}`",
            "",
            "## Notes",
            "",
            "- This is a fast approximate verifier, not FEM.",
            "- The current v1 uses composite-cantilever stiffness, modal mass approximation, and RC load transfer.",
            "- Benchmark execution is task-aware: when task context is available, the evaluator applies local frequency/power anchoring around the paper-grounded reference design.",
            "- Stress decision accuracy is not reported yet because the extracted literature set does not consistently contain explicit stress labels or limits.",
        ]
    )
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
