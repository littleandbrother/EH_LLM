#!/usr/bin/env python3
from __future__ import annotations

import json
import math
import statistics
import sys
from pathlib import Path
import argparse

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.verifier.v1.evaluator import _evaluate_raw_outputs

BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REQUESTS_PATH = BENCHMARK_DIR / "verifier_v1_requests.jsonl"
SEEDS_PATH = BENCHMARK_DIR / "paper_grounded_task_seeds.jsonl"
SUMMARY_PATH = BENCHMARK_DIR / "verifier_v1_power_surrogate_summary.json"
PROFILE_PATH = BENCHMARK_DIR / "verifier_v1_power_surrogate_profile.json"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "verifier_v1_power_surrogate.md"


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


def pct_error(pred: float, obs: float) -> float:
    return abs(pred - obs) / max(abs(obs), 1e-18) * 100.0


def abs_log10_ratio(pred: float, obs: float) -> float:
    return abs(math.log10(max(pred, 1e-18) / max(obs, 1e-18)))


def lv(value: float | None, fallback: float) -> float:
    return math.log10(max(value if value is not None else fallback, 1e-18))


def build_rows(allowed_papers: set[str] | None = None) -> list[dict]:
    requests = load_jsonl(REQUESTS_PATH)
    seeds = {
        row["source_paper_id"]: row
        for row in load_jsonl(SEEDS_PATH)
    }
    rows = []
    for request_row in requests:
        if request_row["candidate_role"] != "reference_solution":
            continue
        if not request_row["task_id"].endswith("frequency_matching"):
            continue
        if allowed_papers is not None and request_row["source_paper_id"] not in allowed_papers:
            continue
        seed = seeds[request_row["source_paper_id"]]
        outputs, _, valid = _evaluate_raw_outputs(request_row["request"])
        if not valid:
            continue
        mapping = seed["verifier_mapping"]
        design = mapping["design_parameters"]
        excitation = mapping["excitation_settings"]
        material = mapping["material_parameters"]
        observed = mapping["observed_outputs"]
        rows.append(
            {
                "source_paper_id": request_row["source_paper_id"],
                "raw_power_uw": outputs["load_power_uw"],
                "raw_open_circuit_voltage_v": outputs["open_circuit_voltage_v"],
                "raw_resonant_frequency_hz": outputs["resonant_frequency_hz"],
                "raw_tip_displacement_mm": outputs["tip_displacement_mm"],
                "raw_root_stress_mpa": outputs["root_stress_mpa"],
                "observed_power_uw": observed["load_power_w"] * 1e6,
                "load_resistance_ohm": mapping["load_settings"].get("load_resistance_ohm")
                or design.get("load_resistance_ohm")
                or 1e6,
                "excitation_frequency_hz": excitation.get("frequency_hz") or 1.0,
                "acceleration_g": excitation.get("acceleration_g") or 1.0,
                "beam_length_mm": design.get("beam_length_mm") or 10.0,
                "beam_width_mm": design.get("beam_width_mm") or 1.0,
                "substrate_thickness_um": design.get("substrate_thickness_um") or 100.0,
                "piezo_thickness_um": design.get("piezo_thickness_um") or 100.0,
                "tip_mass_g": design.get("tip_mass_g") or 0.01,
                "structure_class": material.get("structure_class") or "other_piezo_cantilever",
                "piezo_material": material.get("piezo_material") or "unknown",
            }
        )
    return rows


def summarize_predictions(rows: list[dict], predictions: list[float]) -> dict:
    ape = []
    log_ratio = []
    for row, prediction in zip(rows, predictions):
        observed = row["observed_power_uw"]
        ape.append(pct_error(prediction, observed))
        log_ratio.append(abs_log10_ratio(prediction, observed))
    return {
        "count": len(rows),
        "mape_pct": mean(ape),
        "median_ape_pct": median(ape),
        "median_abs_log10_ratio": median(log_ratio),
    }


def predict_raw_identity(rows: list[dict]) -> list[float]:
    return [max(row["raw_power_uw"], 1e-18) for row in rows]


def predict_global_log_bias(rows: list[dict]) -> list[float]:
    predictions = []
    for idx, row in enumerate(rows):
        train = rows[:idx] + rows[idx + 1 :]
        deltas = [
            math.log10(max(item["observed_power_uw"], 1e-18) / max(item["raw_power_uw"], 1e-18))
            for item in train
        ]
        bias = statistics.median(deltas)
        predictions.append(max(row["raw_power_uw"], 1e-18) * (10 ** bias))
    return predictions


def _ridge_predict(rows: list[dict], target_field: str) -> list[float]:
    structures = sorted({row["structure_class"] for row in rows})
    piezos = sorted({row["piezo_material"] for row in rows})

    def features(row: dict) -> np.ndarray:
        values = [
            1.0,
            lv(row["raw_power_uw"], 1e-18),
            lv(row["raw_open_circuit_voltage_v"], 1e-18),
            lv(row["raw_resonant_frequency_hz"], 1e-9),
            lv(row["raw_tip_displacement_mm"], 1e-18),
            lv(row["raw_root_stress_mpa"], 1e-18),
            lv(row["excitation_frequency_hz"], 1.0),
            lv(row["acceleration_g"], 1.0),
            lv(row["load_resistance_ohm"], 1e6),
            lv(row["beam_length_mm"], 10.0),
            lv(row["beam_width_mm"], 1.0),
            lv(row["substrate_thickness_um"], 100.0),
            lv(row["piezo_thickness_um"], 100.0),
            lv(row["tip_mass_g"], 0.01),
        ]
        values.extend(1.0 if row["structure_class"] == value else 0.0 for value in structures[1:])
        values.extend(1.0 if row["piezo_material"] == value else 0.0 for value in piezos[1:])
        return np.asarray(values, dtype=float)

    predictions = []
    for idx, row in enumerate(rows):
        train = rows[:idx] + rows[idx + 1 :]
        x_train = np.stack([features(item) for item in train])
        y_train = np.asarray([lv(item[target_field], 1e-18) for item in train], dtype=float)
        ridge = np.linalg.solve(
            x_train.T @ x_train + 1e-3 * np.eye(x_train.shape[1]),
            x_train.T @ y_train,
        )
        prediction = 10 ** (features(row) @ ridge)
        predictions.append(prediction)
    return predictions


def predict_log_ridge_power(rows: list[dict]) -> list[float]:
    return _ridge_predict(rows, "observed_power_uw")


def predict_log_ridge_vload(rows: list[dict]) -> list[float]:
    augmented = []
    for row in rows:
        augmented.append(
            {
                **row,
                "observed_vload": math.sqrt(row["observed_power_uw"] * row["load_resistance_ohm"]),
            }
        )
    predicted_vload = _ridge_predict(augmented, "observed_vload")
    return [
        (voltage**2) / row["load_resistance_ohm"]
        for voltage, row in zip(predicted_vload, augmented)
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers-file", type=Path)
    parser.add_argument("--output-suffix", default="")
    return parser.parse_args()


def with_suffix(path: Path, suffix: str) -> Path:
    if not suffix:
        return path
    if path.suffix:
        return path.with_name(f"{path.stem}_{suffix}{path.suffix}")
    return path.with_name(f"{path.name}_{suffix}")


def main() -> None:
    args = parse_args()
    allowed_papers = None
    if args.papers_file:
        payload = json.loads(args.papers_file.read_text())
        allowed_papers = set(payload["papers"])

    rows = build_rows(allowed_papers=allowed_papers)
    candidate_predictions = {
        "raw_physics_identity": predict_raw_identity(rows),
        "global_log_bias": predict_global_log_bias(rows),
        "log_ridge_power": predict_log_ridge_power(rows),
        "log_ridge_vload": predict_log_ridge_vload(rows),
    }

    candidates = {
        name: summarize_predictions(rows, predictions)
        for name, predictions in candidate_predictions.items()
    }
    ranked = sorted(
        candidates.items(),
        key=lambda item: (
            item[1]["mape_pct"] if item[1]["mape_pct"] is not None else float("inf"),
            item[1]["median_ape_pct"] if item[1]["median_ape_pct"] is not None else float("inf"),
        ),
    )
    best_name, best_metrics = ranked[0]

    recommended_runtime_mode = None
    enable_runtime = False
    if best_metrics["mape_pct"] is not None and best_metrics["mape_pct"] <= 50.0:
        recommended_runtime_mode = best_name
        enable_runtime = True

    summary = {
        "count": len(rows),
        "papers_file": None if args.papers_file is None else str(args.papers_file),
        "best_candidate": best_name,
        "recommended_runtime_mode": recommended_runtime_mode,
        "enable_runtime": enable_runtime,
        "candidates": candidates,
    }
    with_suffix(SUMMARY_PATH, args.output_suffix).write_text(json.dumps(summary, indent=2))

    profile = {
        "profile_name": "vehbench_verifier_v1_power_surrogate",
        "output_suffix": args.output_suffix or None,
        "status": "enabled" if enable_runtime else "experimental_not_enabled",
        "recommended_runtime_mode": recommended_runtime_mode,
        "selection_metric": "leave_one_out_mape_pct",
        "candidates": candidates,
    }
    with_suffix(PROFILE_PATH, args.output_suffix).write_text(json.dumps(profile, indent=2))

    lines = [
        "# Verifier v1 Power Surrogate",
        "",
        "This experiment compares several paper-grounded power surrogate candidates under leave-one-out evaluation.",
        "",
        f"- literature rows: `{len(rows)}`",
        f"- papers filter: `{args.papers_file.name if args.papers_file else 'all_ready_mappings'}`",
        f"- best candidate: `{best_name}`",
        f"- runtime enabled: `{enable_runtime}`",
        "",
        "## Candidate Metrics",
        "",
    ]
    for name, metrics in ranked:
        lines.append(
            f"- `{name}`: MAPE=`{metrics['mape_pct']:.3f}%`, median APE=`{metrics['median_ape_pct']:.3f}%`, median |log10(pred/obs)|=`{metrics['median_abs_log10_ratio']:.3f}`"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- `raw_physics_identity` uses the current raw verifier load power directly.",
            "- `global_log_bias` applies a single leave-one-out global bias to raw power.",
            "- `log_ridge_power` fits a log-domain ridge regressor over raw outputs, excitation, load, and geometry features.",
            "- `log_ridge_vload` first predicts effective load voltage and then converts it back to power via `V^2 / R`.",
            "",
            "If the best candidate still has very high leave-one-out error, the current power literature labels are too heterogeneous to justify a runtime calibration profile.",
        ]
    )
    with_suffix(REPORT_PATH, args.output_suffix).write_text("\n".join(lines) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
