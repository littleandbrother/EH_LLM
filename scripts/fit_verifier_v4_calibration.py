#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.synthetic import write_jsonl
from vehbench.verifier.v1.calibration import build_frequency_feature_map
from vehbench.verifier.v1.evaluator import evaluate_request


BENCH_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
SEEDS_PATH = BENCH_DIR / "synthetic_v4_pilot_1k_seeds.jsonl"
ROWS_PATH = BENCH_DIR / "verifier_v4_calibration_rows.jsonl"
PROFILE_PATH = BENCH_DIR / "verifier_v4_frequency_calibration_profile.json"
CV_PATH = BENCH_DIR / "verifier_v4_frequency_calibration_cv.jsonl"
SUMMARY_PATH = BENCH_DIR / "verifier_v4_calibration_summary.json"
CORRECTION_AUDIT_PATH = BENCH_DIR / "verifier_v4_output_correction_audit.json"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "verifier_v4_calibration.md"
RIDGE_LAMBDA = 1e-3


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def mean(values: list[float]) -> float | None:
    return None if not values else sum(values) / len(values)


def median(values: list[float]) -> float | None:
    return None if not values else statistics.median(values)


def pct_error(pred: float | None, obs: float | None, eps: float = 1e-12) -> float | None:
    if pred is None or obs is None:
        return None
    return abs(float(pred) - float(obs)) / max(abs(float(obs)), eps) * 100.0


def safe_log10(value: float | None, fallback: float = 1e-12) -> float:
    resolved = fallback if value is None else float(value)
    return math.log10(max(abs(resolved), fallback))


def build_request_from_seed(seed: dict) -> dict:
    mapping = seed["verifier_mapping"]
    candidate = dict(mapping["design_parameters"])
    return {
        "task_id": seed["synthetic_seed_id"],
        "candidate_id": f"{seed['synthetic_seed_id']}::reference_solution",
        "design_parameters": candidate,
        "material_parameters": dict(mapping["material_parameters"]),
        "excitation_settings": dict(mapping["excitation_settings"]),
        "load_settings": dict(mapping["load_settings"]),
        "constraint_context": {
            "target_resonant_frequency_hz": None,
            "stress_limit_mpa": None,
            "displacement_limit_mm": None,
            "power_target_uw": None,
        },
    }


def build_rows() -> list[dict]:
    rows = []
    for seed in load_jsonl(SEEDS_PATH):
        request = build_request_from_seed(seed)
        interaction = evaluate_request(
            request,
            task=None,
            apply_frequency_calibration=False,
            calibration_profile=None,
            use_task_anchors=False,
        )
        raw = interaction["response"]["outputs"]
        raw_normalized = dict(raw)
        raw_normalized["load_power_w"] = None if raw.get("load_power_uw") is None else float(raw["load_power_uw"]) * 1e-6
        observed = seed["verifier_mapping"]["observed_outputs"]
        rows.append(
            {
                "synthetic_seed_id": seed["synthetic_seed_id"],
                "parent_anchor_id": seed["parent_anchor_id"],
                "split": (seed.get("assigned_split") or {}).get("name"),
                "request": request,
                "raw_outputs": raw_normalized,
                "observed_outputs": observed,
                "feature_map": build_frequency_feature_map(request, raw),
            }
        )
    return rows


def fit_ridge(feature_rows: list[dict], target_getter) -> tuple[list[str], np.ndarray]:
    feature_names = {"bias"}
    for row in feature_rows:
        feature_names.update(row["feature_map"].keys())
    ordered = ["bias"] + sorted(name for name in feature_names if name != "bias")
    x = np.asarray(
        [[row["feature_map"].get(name, 0.0) for name in ordered] for row in feature_rows],
        dtype=float,
    )
    y = np.asarray([target_getter(row) for row in feature_rows], dtype=float)
    coeffs = np.linalg.solve(x.T @ x + RIDGE_LAMBDA * np.eye(x.shape[1]), x.T @ y)
    return ordered, coeffs


def predict_frequency(row: dict, feature_names: list[str], coeffs: np.ndarray) -> float:
    vector = np.asarray([row["feature_map"].get(name, 0.0) for name in feature_names], dtype=float)
    return float(10 ** (vector @ coeffs))


def leave_one_out_frequency(rows: list[dict], feature_names: list[str]) -> tuple[list[dict], dict]:
    cv_rows = []
    raw_ape = []
    cal_ape = []
    for idx, row in enumerate(rows):
        train = rows[:idx] + rows[idx + 1 :]
        ordered, coeffs = fit_ridge(train, lambda item: safe_log10(item["observed_outputs"]["resonant_frequency_hz"], 1e-9))
        assert ordered == feature_names
        predicted = predict_frequency(row, feature_names, coeffs)
        observed = row["observed_outputs"]["resonant_frequency_hz"]
        raw_freq = row["raw_outputs"]["resonant_frequency_hz"]
        raw_err = pct_error(raw_freq, observed, eps=1e-9)
        cal_err = pct_error(predicted, observed, eps=1e-9)
        if raw_err is not None:
            raw_ape.append(raw_err)
        if cal_err is not None:
            cal_ape.append(cal_err)
        cv_rows.append(
            {
                "synthetic_seed_id": row["synthetic_seed_id"],
                "split": row["split"],
                "raw_frequency_hz": raw_freq,
                "predicted_frequency_hz": predicted,
                "observed_frequency_hz": observed,
                "raw_ape_pct": raw_err,
                "calibrated_ape_pct": cal_err,
            }
        )
    summary = {
        "count": len(cv_rows),
        "raw_frequency_mape_pct": mean(raw_ape),
        "raw_frequency_median_ape_pct": median(raw_ape),
        "calibrated_frequency_mape_pct": mean(cal_ape),
        "calibrated_frequency_median_ape_pct": median(cal_ape),
    }
    return cv_rows, summary


def correction_candidates(rows: list[dict], raw_key: str, observed_key: str, eps: float = 1e-12) -> dict:
    paired = [
        (float(row["raw_outputs"][raw_key]), float(row["observed_outputs"][observed_key]))
        for row in rows
        if row["raw_outputs"].get(raw_key) is not None and row["observed_outputs"].get(observed_key) is not None
    ]
    raw_errors = [pct_error(raw, obs, eps=eps) for raw, obs in paired]
    raw_errors = [value for value in raw_errors if value is not None]
    if not paired:
        return {
            "count": 0,
            "raw_mape_pct": None,
            "log_bias_mape_pct": None,
            "scale_ratio_median": None,
            "recommend_runtime_correction": False,
        }

    log_bias_errors = []
    for idx, (raw, obs) in enumerate(paired):
        train = paired[:idx] + paired[idx + 1 :]
        bias = statistics.median([safe_log10(t_obs, eps) - safe_log10(t_raw, eps) for t_raw, t_obs in train])
        pred = raw * (10 ** bias)
        err = pct_error(pred, obs, eps=eps)
        if err is not None:
            log_bias_errors.append(err)

    scales = [obs / max(abs(raw), eps) for raw, obs in paired]
    raw_mape = mean(raw_errors)
    log_bias_mape = mean(log_bias_errors)
    recommend = (
        raw_mape is not None
        and log_bias_mape is not None
        and log_bias_mape <= raw_mape * 0.7
        and log_bias_mape <= 35.0
    )
    return {
        "count": len(paired),
        "raw_mape_pct": raw_mape,
        "log_bias_mape_pct": log_bias_mape,
        "scale_ratio_median": median(scales),
        "recommend_runtime_correction": recommend,
    }


def main() -> None:
    rows = build_rows()
    write_jsonl(ROWS_PATH, rows)
    feature_names, coeffs = fit_ridge(rows, lambda item: safe_log10(item["observed_outputs"]["resonant_frequency_hz"], 1e-9))
    cv_rows, frequency_summary = leave_one_out_frequency(rows, feature_names)
    write_jsonl(CV_PATH, cv_rows)

    profile = {
        "profile_name": "vehbench_verifier_v4_frequency_log_ridge",
        "target": "resonant_frequency_hz",
        "model_type": "log10_ridge_regression",
        "ridge_lambda": RIDGE_LAMBDA,
        "feature_names": feature_names,
        "coefficients": [float(value) for value in coeffs.tolist()],
        "cross_validation": frequency_summary,
    }
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))

    correction_audit = {
        "stress": correction_candidates(rows, "root_stress_mpa", "root_stress_mpa", eps=1e-9),
        "displacement": correction_candidates(rows, "tip_displacement_mm", "tip_displacement_mm", eps=1e-12),
        "power": correction_candidates(rows, "load_power_w", "load_power_w", eps=1e-18),
    }
    CORRECTION_AUDIT_PATH.write_text(json.dumps(correction_audit, indent=2))

    summary = {
        "frequency": frequency_summary,
        "correction_audit": correction_audit,
    }
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))

    lines = [
        "# Verifier v4 Calibration",
        "",
        f"- rows: `{frequency_summary['count']}`",
        f"- raw frequency MAPE (%): `{frequency_summary['raw_frequency_mape_pct']:.3f}`",
        f"- calibrated frequency MAPE (%): `{frequency_summary['calibrated_frequency_mape_pct']:.3f}`",
        f"- raw frequency median APE (%): `{frequency_summary['raw_frequency_median_ape_pct']:.3f}`",
        f"- calibrated frequency median APE (%): `{frequency_summary['calibrated_frequency_median_ape_pct']:.3f}`",
        "",
        "## Output Correction Audit",
        "",
        f"- stress: raw `{correction_audit['stress']['raw_mape_pct']}`, log-bias `{correction_audit['stress']['log_bias_mape_pct']}`, recommend `{correction_audit['stress']['recommend_runtime_correction']}`",
        f"- displacement: raw `{correction_audit['displacement']['raw_mape_pct']}`, log-bias `{correction_audit['displacement']['log_bias_mape_pct']}`, recommend `{correction_audit['displacement']['recommend_runtime_correction']}`",
        f"- power: raw `{correction_audit['power']['raw_mape_pct']}`, log-bias `{correction_audit['power']['log_bias_mape_pct']}`, recommend `{correction_audit['power']['recommend_runtime_correction']}`",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
