from __future__ import annotations

import json
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PROFILE_PATH = (
    PROJECT_ROOT / "data_registry" / "benchmark" / "verifier_v1_frequency_calibration_profile.json"
)


def _safe_number(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _feature_value(number: float | None, fallback: float) -> float:
    value = fallback if number is None else number
    return math.log10(max(value, 1e-12))


def build_frequency_feature_map(request: dict, raw_outputs: dict) -> dict[str, float]:
    design = request.get("design_parameters") or {}
    excitation = request.get("excitation_settings") or {}
    material = request.get("material_parameters") or {}

    structure_class = material.get("structure_class") or "other_piezo_cantilever"
    piezo_material = material.get("piezo_material") or "unknown"

    return {
        "bias": 1.0,
        "log10_raw_resonant_frequency_hz": _feature_value(
            _safe_number(raw_outputs.get("resonant_frequency_hz")),
            1.0,
        ),
        "log10_excitation_frequency_hz": _feature_value(
            _safe_number(excitation.get("frequency_hz")),
            1.0,
        ),
        "log10_acceleration_g": _feature_value(
            _safe_number(excitation.get("acceleration_g")),
            1.0,
        ),
        "log10_load_resistance_ohm": _feature_value(
            _safe_number((request.get("load_settings") or {}).get("load_resistance_ohm"))
            or _safe_number(design.get("load_resistance_ohm")),
            1e6,
        ),
        "log10_beam_length_mm": _feature_value(_safe_number(design.get("beam_length_mm")), 10.0),
        "log10_beam_width_mm": _feature_value(_safe_number(design.get("beam_width_mm")), 1.0),
        "log10_substrate_thickness_um": _feature_value(
            _safe_number(design.get("substrate_thickness_um")),
            100.0,
        ),
        "log10_piezo_thickness_um": _feature_value(
            _safe_number(design.get("piezo_thickness_um")),
            100.0,
        ),
        "log10_tip_mass_g": _feature_value(_safe_number(design.get("tip_mass_g")), 0.01),
        f"struct::{structure_class}": 1.0,
        f"piezo::{piezo_material}": 1.0,
    }


def profile_feature_vector(feature_map: dict[str, float], profile: dict) -> list[float]:
    return [feature_map.get(name, 0.0) for name in profile["feature_names"]]


def load_frequency_profile(path: Path | None = None) -> dict | None:
    path = path or DEFAULT_PROFILE_PATH
    if not path.exists():
        return None
    return json.loads(path.read_text())


def apply_frequency_profile(raw_outputs: dict, request: dict, profile: dict | None) -> tuple[float | None, str | None]:
    if profile is None or raw_outputs.get("resonant_frequency_hz") is None:
        return raw_outputs.get("resonant_frequency_hz"), None
    feature_map = build_frequency_feature_map(request, raw_outputs)
    vector = profile_feature_vector(feature_map, profile)
    coefficients = profile["coefficients"]
    log_prediction = sum(weight * value for weight, value in zip(coefficients, vector))
    calibrated = 10 ** log_prediction
    return calibrated, f"applied frequency calibration profile:{profile.get('profile_name', 'unknown')}"
