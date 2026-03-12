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

from vehbench.eval.runtime import build_request_from_task, candidate_to_unit, load_tasks, unit_to_candidate
from vehbench.verifier.v1.calibration import load_frequency_profile
from vehbench.verifier.v1.evaluator import (
    _build_layers,
    _composite_section,
    _resolved_geometry,
    _resolved_material_profile,
    evaluate_request_record,
)


BENCH_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
SEEDS_PATH = BENCH_DIR / "paper_grounded_task_seeds.jsonl"
REQUESTS_PATH = BENCH_DIR / "verifier_v1_requests.jsonl"
SUMMARY_PATH = BENCH_DIR / "fem_frequency_transfer_summary.json"
DETAIL_PATH = BENCH_DIR / "fem_frequency_transfer_records.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "fem_frequency_transfer.md"


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def fmt(value: float | None, digits: int = 3) -> str:
    if value is None:
        return "n/a"
    return f"{value:.{digits}f}"


def safe_pct_error(pred: float | None, obs: float | None) -> float | None:
    if pred is None or obs is None or obs == 0:
        return None
    return abs(pred - obs) / abs(obs) * 100.0


def generalized_positive_eigenvalues(stiffness: np.ndarray, mass: np.ndarray) -> list[float]:
    try:
        transformed = np.linalg.solve(mass, stiffness)
    except np.linalg.LinAlgError:
        return []
    eigvals = np.linalg.eigvals(transformed)
    real = [float(value.real) for value in eigvals if abs(value.imag) <= 1e-7 and value.real > 1e-9]
    return sorted(real)


def rankdata(values: list[float]) -> list[float]:
    pairs = sorted((value, idx) for idx, value in enumerate(values))
    ranks = [0.0] * len(values)
    i = 0
    while i < len(pairs):
        j = i + 1
        while j < len(pairs) and pairs[j][0] == pairs[i][0]:
            j += 1
        avg_rank = (i + j - 1) / 2.0 + 1.0
        for _, idx in pairs[i:j]:
            ranks[idx] = avg_rank
        i = j
    return ranks


def spearman_correlation(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) != len(ys) or len(xs) < 2:
        return None
    xr = np.array(rankdata(xs), dtype=float)
    yr = np.array(rankdata(ys), dtype=float)
    x_std = float(np.std(xr))
    y_std = float(np.std(yr))
    if x_std <= 1e-12 or y_std <= 1e-12:
        return None
    return float(np.corrcoef(xr, yr)[0, 1])


def build_beam_fem_frequency(request: dict, element_count: int = 12) -> tuple[float | None, list[str]]:
    assumptions: list[str] = []
    geometry = _resolved_geometry(request, assumptions)
    if not geometry["is_valid"]:
        return None, assumptions + ["invalid_geometry"]
    material = _resolved_material_profile(request, geometry, assumptions)
    section = _composite_section(_build_layers(geometry, material))

    length_m = geometry["beam_length_mm"] * 1e-3
    if length_m <= 0:
        return None, assumptions + ["invalid_length"]
    ei = section["bending_stiffness_n_m2"]
    rho_a = section["mass_per_length_kg_m"]
    if ei <= 0 or rho_a <= 0:
        return None, assumptions + ["nonpositive_section_property"]

    node_count = element_count + 1
    dof = 2 * node_count
    k_global = np.zeros((dof, dof))
    m_global = np.zeros((dof, dof))
    le = length_m / element_count

    k_local = (ei / le**3) * np.array(
        [
            [12, 6 * le, -12, 6 * le],
            [6 * le, 4 * le**2, -6 * le, 2 * le**2],
            [-12, -6 * le, 12, -6 * le],
            [6 * le, 2 * le**2, -6 * le, 4 * le**2],
        ],
        dtype=float,
    )
    m_local = (rho_a * le / 420.0) * np.array(
        [
            [156, 22 * le, 54, -13 * le],
            [22 * le, 4 * le**2, 13 * le, -3 * le**2],
            [54, 13 * le, 156, -22 * le],
            [-13 * le, -3 * le**2, -22 * le, 4 * le**2],
        ],
        dtype=float,
    )

    for elem in range(element_count):
        i = 2 * elem
        idx = np.array([i, i + 1, i + 2, i + 3])
        k_global[np.ix_(idx, idx)] += k_local
        m_global[np.ix_(idx, idx)] += m_local

    tip_mass = geometry.get("tip_mass_g")
    if tip_mass is not None and tip_mass > 0:
        m_global[-2, -2] += float(tip_mass) * 1e-3
        assumptions.append("included_tip_mass_point_load")

    free = np.arange(2, dof)
    k_reduced = k_global[np.ix_(free, free)]
    m_reduced = m_global[np.ix_(free, free)]
    positive = generalized_positive_eigenvalues(k_reduced, m_reduced)
    if not positive:
        return None, assumptions + ["no_positive_eigenvalue"]
    return math.sqrt(min(positive)) / (2.0 * math.pi), assumptions


def summarize_reference_errors(rows: list[dict]) -> dict:
    fem_mape = []
    verifier_to_fem_mape = []
    decision_matches = []
    for row in rows:
        obs = row["observed_frequency_hz"]
        fem = row["fem_frequency_hz"]
        calibrated = row["verifier_calibrated_frequency_hz"]
        target = row["target_frequency_hz"]
        tol_pct = row["frequency_tolerance_pct"]
        err = safe_pct_error(fem, obs)
        if err is not None:
            fem_mape.append(err)
        err2 = safe_pct_error(calibrated, fem)
        if err2 is not None:
            verifier_to_fem_mape.append(err2)
        if fem is not None and calibrated is not None and target is not None:
            fem_ok = abs(fem - target) / max(abs(target), 1e-9) * 100.0 <= tol_pct
            verifier_ok = abs(calibrated - target) / max(abs(target), 1e-9) * 100.0 <= tol_pct
            decision_matches.append(fem_ok == verifier_ok)
    return {
        "count": len(rows),
        "fem_frequency_mape_pct": statistics.mean(fem_mape) if fem_mape else None,
        "fem_frequency_median_ape_pct": statistics.median(fem_mape) if fem_mape else None,
        "verifier_vs_fem_frequency_mape_pct": statistics.mean(verifier_to_fem_mape) if verifier_to_fem_mape else None,
        "verifier_vs_fem_decision_consistency": sum(decision_matches) / len(decision_matches) if decision_matches else None,
    }


def audited_reference_subset(rows: list[dict]) -> list[dict]:
    keep = []
    noisy_prefixes = (
        "defaulted substrate_material",
        "defaulted substrate_thickness",
        "defaulted piezo_thickness",
    )
    for row in rows:
        assumptions = row.get("fem_assumptions") or []
        if any(note.startswith(noisy_prefixes) for note in assumptions):
            continue
        keep.append(row)
    return keep


def local_ranking_transfer(tasks: list[dict], sample_count: int = 12) -> dict:
    calibration_profile = load_frequency_profile()
    per_task = []
    for task in tasks:
        if task["task_type"] != "frequency_matching":
            continue
        reference = task.get("reference_solution") or {}
        if not reference:
            continue
        verifier_scores = []
        fem_scores = []
        for idx in range(sample_count):
            unit = []
            for dim in range(len(task["variable_bounds"])):
                base = (idx + 0.5) / sample_count
                unit.append(min(0.98, max(0.02, (base + 0.17 * dim) % 1.0)))
            candidate = unit_to_candidate(task, unit)
            request = build_request_from_task(task, candidate, candidate_id=f"{task['task_id']}::fem_rank::{idx}")
            verifier = evaluate_request_record(
                {"request": request},
                task=task,
                apply_frequency_calibration=True,
                calibration_profile=calibration_profile,
                use_task_anchors=False,
            )
            verifier_freq = (verifier["response"].get("outputs") or {}).get("resonant_frequency_hz")
            fem_freq, _ = build_beam_fem_frequency(request)
            target = (task.get("fixed_conditions") or {}).get("target_resonant_frequency_hz")
            if verifier_freq is None or fem_freq is None or target is None:
                continue
            verifier_scores.append(-abs(verifier_freq - target))
            fem_scores.append(-abs(fem_freq - target))
        if len(verifier_scores) >= 4:
            rho = spearman_correlation(verifier_scores, fem_scores)
            if rho is not None and not math.isnan(rho):
                per_task.append(
                    {
                        "task_id": task["task_id"],
                        "spearman_rho": float(rho),
                        "sample_count": len(verifier_scores),
                    }
                )
    rhos = [row["spearman_rho"] for row in per_task]
    return {
        "task_count": len(per_task),
        "mean_spearman_rho": statistics.mean(rhos) if rhos else None,
        "median_spearman_rho": statistics.median(rhos) if rhos else None,
        "per_task": per_task,
    }


def main() -> None:
    calibration_profile = load_frequency_profile()
    requests = load_jsonl(REQUESTS_PATH)
    seeds = {row["seed_id"]: row for row in load_jsonl(SEEDS_PATH)}
    tasks = load_tasks(BENCH_DIR / "tasks_paper_grounded.jsonl", task_type="frequency_matching")

    records = []
    for request in requests:
        if request.get("candidate_role") != "reference_solution":
            continue
        task_id = request["task_id"]
        if not task_id.endswith("::frequency_matching"):
            continue
        task = next(task for task in tasks if task["task_id"] == task_id)
        seed = seeds[request["source_seed_id"]]
        observed_frequency = seed["verifier_mapping"]["observed_outputs"].get("resonant_frequency_hz")
        calibrated = evaluate_request_record(
            {"request": request["request"]},
            task=task,
            apply_frequency_calibration=True,
            calibration_profile=calibration_profile,
            use_task_anchors=False,
        )
        calibrated_frequency = (calibrated["response"].get("outputs") or {}).get("resonant_frequency_hz")
        fem_frequency, assumptions = build_beam_fem_frequency(request["request"])
        records.append(
            {
                "task_id": task_id,
                "source_paper_id": request["source_paper_id"],
                "observed_frequency_hz": observed_frequency,
                "verifier_calibrated_frequency_hz": calibrated_frequency,
                "fem_frequency_hz": fem_frequency,
                "target_frequency_hz": (task.get("fixed_conditions") or {}).get("target_resonant_frequency_hz"),
                "frequency_tolerance_pct": (task.get("hard_constraints") or {}).get("frequency_error_tolerance_pct") or 5.0,
                "fem_assumptions": assumptions,
            }
        )

    reference_summary = summarize_reference_errors(records)
    ranking_summary = local_ranking_transfer(tasks)
    audited_rows = audited_reference_subset(records)
    audited_summary = summarize_reference_errors(audited_rows)
    summary = {
        "reference_transfer": reference_summary,
        "audited_reference_transfer": audited_summary,
        "local_ranking_transfer": {
            "task_count": ranking_summary["task_count"],
            "mean_spearman_rho": ranking_summary["mean_spearman_rho"],
            "median_spearman_rho": ranking_summary["median_spearman_rho"],
        },
    }

    write_jsonl(DETAIL_PATH, records)
    SUMMARY_PATH.write_text(json.dumps(summary, indent=2))

    lines = [
        "# Frequency FEM Transfer",
        "",
        "This report compares the calibrated verifier against an independent 1D Euler-Bernoulli beam FEM frequency model over the paper-grounded frequency tasks.",
        "",
        "## Reference-Solution Transfer",
        "",
        f"- evaluated reference designs: `{reference_summary['count']}`",
        f"- FEM vs literature frequency MAPE (%): `{fmt(reference_summary['fem_frequency_mape_pct'])}`",
        f"- FEM vs literature median APE (%): `{fmt(reference_summary['fem_frequency_median_ape_pct'])}`",
        f"- calibrated verifier vs FEM frequency MAPE (%): `{fmt(reference_summary['verifier_vs_fem_frequency_mape_pct'])}`",
        f"- calibrated verifier vs FEM frequency decision consistency: `{fmt(reference_summary['verifier_vs_fem_decision_consistency'])}`",
        "",
        "## Audited Reference Subset",
        "",
        f"- subset count (no defaulted thickness/material placeholders): `{audited_summary['count']}`",
        f"- audited FEM vs literature frequency MAPE (%): `{fmt(audited_summary['fem_frequency_mape_pct'])}`",
        f"- audited FEM vs literature median APE (%): `{fmt(audited_summary['fem_frequency_median_ape_pct'])}`",
        f"- audited calibrated verifier vs FEM frequency MAPE (%): `{fmt(audited_summary['verifier_vs_fem_frequency_mape_pct'])}`",
        f"- audited calibrated verifier vs FEM decision consistency: `{fmt(audited_summary['verifier_vs_fem_decision_consistency'])}`",
        "",
        "## Local Ranking Transfer",
        "",
        f"- frequency tasks probed: `{ranking_summary['task_count']}`",
        f"- mean Spearman rho: `{fmt(ranking_summary['mean_spearman_rho'])}`",
        f"- median Spearman rho: `{fmt(ranking_summary['median_spearman_rho'])}`",
        "",
        "## Notes",
        "",
        "- The FEM model here is intentionally independent from the runtime verifier: it uses Euler-Bernoulli beam finite elements rather than the runtime lumped tip-stiffness approximation.",
        "- This is a frequency-only transfer study; it does not yet provide an electromechanical power FEM.",
        "- The aim is benchmark credibility, not full multiphysics replacement.",
        "",
    ]
    REPORT_PATH.write_text("\n".join(lines))
    print(json.dumps({"summary_path": str(SUMMARY_PATH), "report_path": str(REPORT_PATH)}, indent=2))


if __name__ == "__main__":
    main()
