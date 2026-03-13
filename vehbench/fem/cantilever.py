from __future__ import annotations

import math

import numpy as np

from ..verifier.v1.evaluator import (
    EPS0,
    MODAL_MASS_COEFFICIENT,
    _build_layers,
    _composite_section,
    _resolved_geometry,
    _resolved_material_profile,
    _resolve_excitation,
)


def generalized_positive_eigenvalues(stiffness: np.ndarray, mass: np.ndarray) -> list[float]:
    try:
        transformed = np.linalg.solve(mass, stiffness)
    except np.linalg.LinAlgError:
        return []
    eigvals = np.linalg.eigvals(transformed)
    real = [float(value.real) for value in eigvals if abs(value.imag) <= 1e-7 and value.real > 1e-9]
    return sorted(real)


def build_beam_fem_frequency_and_mode(
    request: dict,
    element_count: int = 24,
) -> tuple[dict, list[str], bool]:
    assumptions: list[str] = []
    geometry = _resolved_geometry(request, assumptions)
    if not geometry["is_valid"]:
        return {"geometry": geometry}, assumptions + ["invalid_geometry"], False

    material = _resolved_material_profile(request, geometry, assumptions)
    section = _composite_section(_build_layers(geometry, material))
    length_m = geometry["beam_length_mm"] * 1e-3
    if length_m <= 0:
        return {"geometry": geometry, "section": section}, assumptions + ["invalid_length"], False

    ei = section["bending_stiffness_n_m2"]
    rho_a = section["mass_per_length_kg_m"]
    if ei <= 0 or rho_a <= 0:
        return {"geometry": geometry, "section": section}, assumptions + ["nonpositive_section_property"], False

    node_count = element_count + 1
    dof = 2 * node_count
    le = length_m / element_count
    k_global = np.zeros((dof, dof))
    m_global = np.zeros((dof, dof))

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
        return {"geometry": geometry, "section": section}, assumptions + ["no_positive_eigenvalue"], False

    mode_eig = min(positive)
    frequency_hz = math.sqrt(mode_eig) / (2.0 * math.pi)
    beam_mass_kg = rho_a * length_m
    tip_mass_kg = 0.0 if tip_mass is None else float(tip_mass) * 1e-3
    effective_mass_kg = MODAL_MASS_COEFFICIENT * beam_mass_kg + tip_mass_kg
    tip_stiffness_n_m = mode_eig * effective_mass_kg

    return (
        {
            "geometry": geometry,
            "material": material,
            "section": section,
            "frequency_hz": frequency_hz,
            "beam_mass_kg": beam_mass_kg,
            "effective_mass_kg": effective_mass_kg,
            "tip_stiffness_n_m": tip_stiffness_n_m,
            "element_count": element_count,
        },
        assumptions,
        True,
    )


def estimate_quality_factor(
    structure_class: str | None,
    piezo_material: str | None,
    substrate_material: str | None,
    beam_length_mm: float,
    resonant_frequency_hz: float,
    tip_mass_g: float | None,
) -> float:
    q = 24.0
    if structure_class == "unimorph":
        q += 10.0
    elif structure_class == "bimorph":
        q += 6.0

    if piezo_material == "PZT":
        q *= 1.1
    elif piezo_material == "PVDF":
        q *= 0.65
    elif piezo_material == "AlN":
        q *= 1.2

    substrate = (substrate_material or "").lower()
    if "silicon" in substrate:
        q *= 1.35
    elif "steel" in substrate:
        q *= 0.95
    elif "pen" in substrate:
        q *= 0.75

    if beam_length_mm <= 10:
        q *= 1.2
    elif beam_length_mm >= 60:
        q *= 0.88

    if resonant_frequency_hz <= 20:
        q *= 0.8
    elif resonant_frequency_hz >= 800:
        q *= 1.15

    if tip_mass_g is not None and tip_mass_g >= 5:
        q *= 0.85

    return min(100.0, max(6.0, q))


def evaluate_cantilever_request(
    request: dict,
    element_count: int = 24,
) -> tuple[dict, list[str], bool]:
    fem, assumptions, valid = build_beam_fem_frequency_and_mode(request, element_count=element_count)
    if not valid:
        return fem, assumptions, False

    geometry = fem["geometry"]
    material = fem["material"]
    section = fem["section"]
    resonant_frequency_hz = float(fem["frequency_hz"])
    excitation = _resolve_excitation(request, resonant_frequency_hz, assumptions)
    excitation_frequency_hz = excitation["frequency_hz"] or resonant_frequency_hz
    omega_n = 2.0 * math.pi * max(resonant_frequency_hz, 1e-9)
    omega = 2.0 * math.pi * max(excitation_frequency_hz, 1e-9)
    q_factor = estimate_quality_factor(
        material["structure_class"],
        material["piezo_material"],
        material["substrate_material"],
        geometry["beam_length_mm"],
        resonant_frequency_hz,
        geometry["tip_mass_g"],
    )
    damping_ratio = 1.0 / max(2.0 * q_factor, 1e-9)
    r = omega / omega_n
    dynamic_factor = 1.0 / math.sqrt((1.0 - r**2) ** 2 + (2.0 * damping_ratio * r) ** 2)

    base_acc = excitation["acceleration_ms2"]
    modal_static_displacement_m = base_acc / max(omega_n**2, 1e-12)
    tip_displacement_m = modal_static_displacement_m * dynamic_factor * 1.08
    length_m = geometry["beam_length_mm"] * 1e-3
    curvature = 2.9 * tip_displacement_m / max(length_m**2, 1e-12)
    root_stress_pa = section["bending_stiffness_n_m2"] * curvature * section["max_distance_m"] / max(
        section["bending_stiffness_n_m2"] / max(material["substrate_modulus_pa"], 1e-9),
        1e-18,
    )
    root_stress_mpa = root_stress_pa / 1e6

    piezo_stress_pa = material["piezo_modulus_pa"] * abs(curvature) * section["piezo_mean_distance_m"]
    open_circuit_voltage_v = (
        abs(material["g31_vm_per_n"])
        * piezo_stress_pa
        * geometry["piezo_thickness_um"]
        * 1e-6
        * (2.0 if material["structure_class"] == "bimorph" else 1.0)
        * material["voltage_scale"]
        * 0.82
    )

    piezo_capacitance_f = EPS0 * material["epsilon_r"] * length_m * section["piezo_area_over_thickness_m"]
    load_settings = request.get("load_settings") or {}
    user_load_ohm = load_settings.get("load_resistance_ohm")
    if user_load_ohm is None:
        user_load_ohm = geometry.get("load_resistance_ohm")
    if user_load_ohm is None:
        user_load_ohm = 1e6
        assumptions.append("defaulted load_resistance_ohm=1000000")
    user_load_ohm = max(float(user_load_ohm), 1.0)

    if piezo_capacitance_f > 0:
        reactance_ohm = 1.0 / max(omega * piezo_capacitance_f, 1e-12)
        matched_load_ohm = reactance_ohm
        short_circuit_current_a = omega * piezo_capacitance_f * open_circuit_voltage_v
        bandwidth_hz = resonant_frequency_hz / max(q_factor, 1e-9)
    else:
        reactance_ohm = None
        matched_load_ohm = user_load_ohm
        short_circuit_current_a = None
        bandwidth_hz = None
        assumptions.append("piezo_capacitance unavailable")

    def load_power_for_resistance(load_ohm: float) -> float:
        if reactance_ohm is None:
            v_rms = open_circuit_voltage_v / math.sqrt(2.0)
            return v_rms**2 / max(load_ohm, 1.0)
        transfer = load_ohm / math.sqrt(load_ohm**2 + reactance_ohm**2)
        v_rms = open_circuit_voltage_v / math.sqrt(2.0) * transfer
        return v_rms**2 / max(load_ohm, 1.0)

    load_power_w = load_power_for_resistance(user_load_ohm)
    matched_load_power_w = load_power_for_resistance(max(matched_load_ohm, 1.0))

    outputs = {
        "resonant_frequency_hz": resonant_frequency_hz,
        "tip_displacement_mm": tip_displacement_m * 1e3,
        "root_stress_mpa": root_stress_mpa,
        "load_power_w": load_power_w,
        "matched_load_power_w": matched_load_power_w,
        "matched_load_resistance_ohm": matched_load_ohm,
        "open_circuit_voltage_v": open_circuit_voltage_v,
        "short_circuit_current_a": short_circuit_current_a,
        "bandwidth_hz": bandwidth_hz,
        "quality_factor": q_factor,
        "element_count": element_count,
    }
    label_assumptions = assumptions + [f"quality_factor={round(q_factor, 3)}"]
    return outputs, label_assumptions, True


def format_observed_outputs(outputs: dict) -> dict:
    return {
        "resonant_frequency_hz": None if outputs.get("resonant_frequency_hz") is None else round(float(outputs["resonant_frequency_hz"]), 6),
        "load_power_w": None if outputs.get("load_power_w") is None else float(outputs["load_power_w"]),
        "matched_load_power_w": None if outputs.get("matched_load_power_w") is None else float(outputs["matched_load_power_w"]),
        "matched_load_resistance_ohm": None if outputs.get("matched_load_resistance_ohm") is None else float(outputs["matched_load_resistance_ohm"]),
        "open_circuit_voltage_v": None if outputs.get("open_circuit_voltage_v") is None else float(outputs["open_circuit_voltage_v"]),
        "short_circuit_current_a": None if outputs.get("short_circuit_current_a") is None else float(outputs["short_circuit_current_a"]),
        "bandwidth_hz": None if outputs.get("bandwidth_hz") is None else float(outputs["bandwidth_hz"]),
        "tip_displacement_mm": None if outputs.get("tip_displacement_mm") is None else float(outputs["tip_displacement_mm"]),
        "root_stress_mpa": None if outputs.get("root_stress_mpa") is None else float(outputs["root_stress_mpa"]),
    }
