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

from vehbench.verifier.v1.calibration import build_frequency_feature_map

BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
CANONICAL_PATH = BENCHMARK_DIR / "verifier_v1_literature_backsub_predictions.jsonl"
REQUESTS_PATH = BENCHMARK_DIR / "verifier_v1_requests.jsonl"
PROFILE_PATH = BENCHMARK_DIR / "verifier_v1_frequency_calibration_profile.json"
CV_ROWS_PATH = BENCHMARK_DIR / "verifier_v1_frequency_calibration_cv.jsonl"
SUMMARY_PATH = BENCHMARK_DIR / "verifier_v1_frequency_calibration_summary.json"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "verifier_v1_frequency_calibration.md"
RIDGE_LAMBDA = 1e-3


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


def pct_error(pred: float, obs: float) -> float:
    return abs(pred - obs) / max(abs(obs), 1e-12) * 100.0


def build_dataset() -> tuple[list[dict], list[str]]:
    canonical_rows = load_jsonl(CANONICAL_PATH)
    requests = {
        row["task_id"]: row
        for row in load_jsonl(REQUESTS_PATH)
    }

    dataset = []
    feature_names: set[str] = set()
    for row in canonical_rows:
        request = requests[row["task_id"]]["request"]
        feature_map = build_frequency_feature_map(request, row["predicted"])
        feature_names.update(feature_map.keys())
        dataset.append(
            {
                "source_paper_id": row["source_paper_id"],
                "task_id": row["task_id"],
                "request": request,
                "raw_frequency_hz": row["predicted"]["resonant_frequency_hz"],
                "observed_frequency_hz": row["observed"]["resonant_frequency_hz"],
                "feature_map": feature_map,
            }
        )
    ordered_features = ["bias"] + sorted(name for name in feature_names if name != "bias")
    return dataset, ordered_features


def vectorize(dataset: list[dict], feature_names: list[str]) -> tuple[np.ndarray, np.ndarray]:
    x_rows = []
    y_rows = []
    for row in dataset:
        x_rows.append([row["feature_map"].get(name, 0.0) for name in feature_names])
        y_rows.append(math.log10(row["observed_frequency_hz"]))
    return np.asarray(x_rows, dtype=float), np.asarray(y_rows, dtype=float)


def fit_coefficients(x: np.ndarray, y: np.ndarray) -> np.ndarray:
    reg = RIDGE_LAMBDA * np.eye(x.shape[1])
    return np.linalg.solve(x.T @ x + reg, x.T @ y)


def predict_frequency(feature_map: dict[str, float], feature_names: list[str], coefficients: np.ndarray) -> float:
    vector = np.asarray([feature_map.get(name, 0.0) for name in feature_names], dtype=float)
    return float(10 ** (vector @ coefficients))


def main() -> None:
    dataset, feature_names = build_dataset()
    x_all, y_all = vectorize(dataset, feature_names)
    full_coefficients = fit_coefficients(x_all, y_all)

    cv_rows = []
    ape_values = []
    for idx, row in enumerate(dataset):
        train = dataset[:idx] + dataset[idx + 1 :]
        x_train, y_train = vectorize(train, feature_names)
        coefficients = fit_coefficients(x_train, y_train)
        predicted = predict_frequency(row["feature_map"], feature_names, coefficients)
        ape = pct_error(predicted, row["observed_frequency_hz"])
        ape_values.append(ape)
        cv_rows.append(
            {
                "source_paper_id": row["source_paper_id"],
                "task_id": row["task_id"],
                "raw_frequency_hz": row["raw_frequency_hz"],
                "predicted_frequency_hz": predicted,
                "observed_frequency_hz": row["observed_frequency_hz"],
                "absolute_percentage_error": ape,
            }
        )

    profile = {
        "profile_name": "vehbench_verifier_v1_frequency_log_ridge",
        "target": "resonant_frequency_hz",
        "model_type": "log10_ridge_regression",
        "ridge_lambda": RIDGE_LAMBDA,
        "feature_names": feature_names,
        "coefficients": [float(value) for value in full_coefficients.tolist()],
        "cross_validation": {
            "scheme": "leave_one_out",
            "count": len(cv_rows),
            "mape_pct": mean(ape_values),
            "median_ape_pct": median(ape_values),
        },
    }
    PROFILE_PATH.write_text(json.dumps(profile, indent=2))
    write_jsonl(CV_ROWS_PATH, cv_rows)

    summary = profile["cross_validation"]
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))
    lines = [
        "# Verifier v1 Frequency Calibration",
        "",
        "This profile calibrates raw verifier resonant frequency predictions using a log-domain ridge regression over paper-grounded literature back-substitution records.",
        "",
        f"- calibration rows: `{summary['count']}`",
        f"- leave-one-out frequency MAPE (%): `{summary['mape_pct']:.3f}`",
        f"- leave-one-out median APE (%): `{summary['median_ape_pct']:.3f}`",
        "",
        "Feature groups:",
        "- raw verifier frequency",
        "- excitation / load / geometry scalars",
        "- structure class one-hot terms",
        "- piezo material one-hot terms",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps(profile["cross_validation"], indent=2))


if __name__ == "__main__":
    main()
