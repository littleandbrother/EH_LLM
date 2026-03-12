from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np

from ..verifier.v1.evaluator import (
    _build_layers,
    _composite_section,
    _resolved_geometry,
    _resolved_material_profile,
)

LOG_SCALE_KEYS = {"load_resistance_ohm"}


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def hash_seed(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16) % (2**32)


def bounded(value: float | None, unit: str, scale_low: float, scale_high: float) -> dict | None:
    if value is None:
        return None
    low = value * scale_low
    high = value * scale_high
    if value > 0 and low <= 0:
        low = value * 0.5
    return {
        "min": round(low, 8),
        "max": round(high, 8),
        "unit": unit,
    }


def _uses_log_scale(variable_bounds: dict, key: str) -> bool:
    if key not in LOG_SCALE_KEYS:
        return False
    bounds = variable_bounds[key]
    low = float(bounds["min"])
    high = float(bounds["max"])
    return low > 0 and high / low >= 50.0


def clamp_candidate(variable_bounds: dict, candidate: dict) -> dict:
    clamped = {}
    for key, bounds in variable_bounds.items():
        value = candidate.get(key)
        if value is None:
            value = (float(bounds["min"]) + float(bounds["max"])) / 2.0
        clamped[key] = min(float(bounds["max"]), max(float(bounds["min"]), float(value)))
    return clamped


def candidate_to_unit(variable_bounds: dict, candidate: dict) -> list[float]:
    vector = []
    for key, bounds in variable_bounds.items():
        low = float(bounds["min"])
        high = float(bounds["max"])
        value = float(candidate.get(key, (low + high) / 2.0))
        if _uses_log_scale(variable_bounds, key):
            low_log = math.log(low)
            high_log = math.log(high)
            unit = (math.log(max(value, low)) - low_log) / max(high_log - low_log, 1e-12)
        else:
            unit = (value - low) / max(high - low, 1e-12)
        vector.append(min(1.0, max(0.0, unit)))
    return vector


def unit_to_candidate(variable_bounds: dict, vector: list[float]) -> dict:
    candidate = {}
    for key, unit in zip(variable_bounds.keys(), vector):
        bounds = variable_bounds[key]
        low = float(bounds["min"])
        high = float(bounds["max"])
        clipped = min(1.0, max(0.0, float(unit)))
        if _uses_log_scale(variable_bounds, key):
            value = math.exp(math.log(low) + clipped * (math.log(high) - math.log(low)))
        else:
            value = low + clipped * (high - low)
        candidate[key] = float(value)
    return clamp_candidate(variable_bounds, candidate)


def build_request(anchor: dict, candidate: dict, synthetic_seed_id: str) -> dict:
    mapping = anchor["verifier_mapping"]
    load_value = candidate.get("load_resistance_ohm", mapping["load_settings"].get("load_resistance_ohm"))
    return {
        "task_id": synthetic_seed_id,
        "candidate_id": f"{synthetic_seed_id}::reference_solution",
        "design_parameters": dict(candidate),
        "material_parameters": dict(mapping["material_parameters"]),
        "excitation_settings": dict(mapping["excitation_settings"]),
        "load_settings": {
            "load_type": "resistive" if load_value is not None else mapping["load_settings"].get("load_type"),
            "load_resistance_ohm": load_value,
        },
        "constraint_context": {
            "target_resonant_frequency_hz": None,
            "stress_limit_mpa": None,
            "displacement_limit_mm": None,
            "power_target_uw": None,
        },
    }


def generalized_positive_eigenvalues(stiffness: np.ndarray, mass: np.ndarray) -> list[float]:
    try:
        transformed = np.linalg.solve(mass, stiffness)
    except np.linalg.LinAlgError:
        return []
    eigvals = np.linalg.eigvals(transformed)
    real = [float(value.real) for value in eigvals if abs(value.imag) <= 1e-7 and value.real > 1e-9]
    return sorted(real)


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
