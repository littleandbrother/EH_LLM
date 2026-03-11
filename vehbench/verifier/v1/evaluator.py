from __future__ import annotations

import math
import time

from .adapter import VERIFIER_VERSION
from .calibration import apply_frequency_profile, load_frequency_profile

EPS0 = 8.8541878128e-12
DEFAULT_FREQUENCY_TOLERANCE_PCT = 5.0
MODAL_MASS_COEFFICIENT = 0.236
FREQUENCY_SCALE = 1.0
DISPLACEMENT_SCALE = 1.0

PIEZO_DEFAULTS = {
    "PZT": {
        "youngs_modulus_gpa": 63.0,
        "density_kg_m3": 7500.0,
        "g31_vm_per_n": 0.011,
        "epsilon_r": 1200.0,
        "voltage_scale": 1.6,
    },
    "PVDF": {
        "youngs_modulus_gpa": 3.0,
        "density_kg_m3": 1780.0,
        "g31_vm_per_n": 0.216,
        "epsilon_r": 12.0,
        "voltage_scale": 0.18,
    },
    "AlN": {
        "youngs_modulus_gpa": 330.0,
        "density_kg_m3": 3260.0,
        "g31_vm_per_n": 0.006,
        "epsilon_r": 10.0,
        "voltage_scale": 0.9,
    },
    None: {
        "youngs_modulus_gpa": 63.0,
        "density_kg_m3": 7500.0,
        "g31_vm_per_n": 0.011,
        "epsilon_r": 1200.0,
        "voltage_scale": 1.2,
    },
}

SUBSTRATE_DEFAULTS = {
    "silicon": {"youngs_modulus_gpa": 169.0, "density_kg_m3": 2330.0},
    "stainless steel": {"youngs_modulus_gpa": 200.0, "density_kg_m3": 8000.0},
    "steel": {"youngs_modulus_gpa": 200.0, "density_kg_m3": 7850.0},
    "copper": {"youngs_modulus_gpa": 110.0, "density_kg_m3": 8960.0},
    "bronze": {"youngs_modulus_gpa": 115.0, "density_kg_m3": 8800.0},
    "pen": {"youngs_modulus_gpa": 4.5, "density_kg_m3": 1360.0},
}


def _coalesce(*values):
    for value in values:
        if value is not None:
            return value
    return None


def _safe_number(value) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _normalize_material_name(value: str | None) -> str | None:
    if value is None:
        return None
    return value.strip().lower()


def _parse_task_type(task_id: str | None) -> str | None:
    if not task_id or "::" not in task_id:
        return None
    return task_id.rsplit("::", 1)[-1]


def _estimate_quality_factor(
    structure_class: str | None,
    piezo_material: str | None,
    substrate_material: str | None,
    beam_length_mm: float,
    resonant_frequency_hz: float,
    tip_mass_g: float | None,
) -> float:
    q = {
        "unimorph": 32.0,
        "bimorph": 28.0,
        "other_piezo_cantilever": 24.0,
        None: 24.0,
    }[structure_class]

    if piezo_material == "PZT":
        q *= 1.1
    elif piezo_material == "PVDF":
        q *= 0.7
    elif piezo_material == "AlN":
        q *= 1.25

    if substrate_material == "silicon":
        q *= 1.6
    elif substrate_material == "pen":
        q *= 0.7

    if beam_length_mm <= 8:
        q *= 1.3
    elif beam_length_mm >= 80:
        q *= 0.85

    if resonant_frequency_hz >= 1000:
        q *= 1.3
    elif resonant_frequency_hz <= 10:
        q *= 0.75

    if tip_mass_g is not None and tip_mass_g >= 10:
        q *= 0.8

    return min(90.0, max(8.0, q))


def _default_substrate_material(
    structure_class: str | None,
    substrate_material: str | None,
    beam_length_mm: float,
    piezo_material: str | None,
) -> str:
    normalized = _normalize_material_name(substrate_material)
    if normalized in SUBSTRATE_DEFAULTS:
        return normalized
    if normalized and "steel" in normalized:
        return "stainless steel" if "stainless" in normalized else "steel"
    if normalized and "silicon" in normalized:
        return "silicon"
    if normalized and "copper" in normalized:
        return "copper"
    if normalized and "bronze" in normalized:
        return "bronze"
    if normalized and "pen" in normalized:
        return "pen"
    if piezo_material == "PVDF":
        return "pen"
    if structure_class == "unimorph" and beam_length_mm <= 20:
        return "silicon"
    return "stainless steel"


def _default_substrate_thickness_um(
    substrate_material: str,
    beam_length_mm: float,
) -> float:
    if substrate_material == "silicon":
        return 725.0 if beam_length_mm <= 20 else 500.0
    if substrate_material == "pen":
        return 125.0
    if beam_length_mm <= 10:
        return 50.0
    if beam_length_mm <= 40:
        return 100.0
    return 200.0


def _default_piezo_thickness_um(
    piezo_material: str | None,
    substrate_material: str,
    beam_length_mm: float,
) -> float:
    if piezo_material == "PVDF":
        return 28.0
    if piezo_material == "AlN":
        return 1.0
    if substrate_material == "silicon" and beam_length_mm <= 20:
        return 2.5
    if beam_length_mm <= 20:
        return 100.0
    return 200.0


def _resolved_material_profile(request: dict, design: dict, assumptions: list[str]) -> dict:
    material = request.get("material_parameters") or {}
    structure_class = material.get("structure_class")
    piezo_material = material.get("piezo_material")
    beam_length_mm = design["beam_length_mm"]
    substrate_material = _default_substrate_material(
        structure_class,
        material.get("substrate_material"),
        beam_length_mm,
        piezo_material,
    )
    if material.get("substrate_material") is None:
        assumptions.append(f"defaulted substrate_material={substrate_material}")

    piezo_defaults = PIEZO_DEFAULTS.get(piezo_material, PIEZO_DEFAULTS[None])
    substrate_defaults = SUBSTRATE_DEFAULTS.get(substrate_material, SUBSTRATE_DEFAULTS["stainless steel"])

    piezo_modulus = _coalesce(_safe_number(material.get("piezo_modulus_gpa")), piezo_defaults["youngs_modulus_gpa"])
    if material.get("piezo_modulus_gpa") is None:
        assumptions.append(f"defaulted piezo_modulus_gpa={piezo_modulus}")
    substrate_modulus = _coalesce(
        _safe_number(material.get("substrate_modulus_gpa")),
        substrate_defaults["youngs_modulus_gpa"],
    )
    if material.get("substrate_modulus_gpa") is None:
        assumptions.append(f"defaulted substrate_modulus_gpa={substrate_modulus}")
    piezo_density = _coalesce(
        _safe_number(material.get("piezo_density_kg_m3")),
        piezo_defaults["density_kg_m3"],
    )
    if material.get("piezo_density_kg_m3") is None:
        assumptions.append(f"defaulted piezo_density_kg_m3={piezo_density}")
    substrate_density = _coalesce(
        _safe_number(material.get("substrate_density_kg_m3")),
        substrate_defaults["density_kg_m3"],
    )
    if material.get("substrate_density_kg_m3") is None:
        assumptions.append(f"defaulted substrate_density_kg_m3={substrate_density}")

    return {
        "structure_class": structure_class,
        "piezo_material": piezo_material,
        "substrate_material": substrate_material,
        "piezo_modulus_pa": piezo_modulus * 1e9,
        "substrate_modulus_pa": substrate_modulus * 1e9,
        "piezo_density_kg_m3": piezo_density,
        "substrate_density_kg_m3": substrate_density,
        "g31_vm_per_n": piezo_defaults["g31_vm_per_n"],
        "epsilon_r": piezo_defaults["epsilon_r"],
        "voltage_scale": piezo_defaults["voltage_scale"],
    }


def _resolved_geometry(request: dict, assumptions: list[str]) -> dict:
    design = request.get("design_parameters") or {}
    length_mm = _safe_number(design.get("beam_length_mm"))
    width_mm = _safe_number(design.get("beam_width_mm"))
    if length_mm is None or width_mm is None or length_mm <= 0 or width_mm <= 0:
        return {
            "is_valid": False,
            "beam_length_mm": length_mm,
            "beam_width_mm": width_mm,
        }

    material_stub = request.get("material_parameters") or {}
    substrate_material = _default_substrate_material(
        material_stub.get("structure_class"),
        material_stub.get("substrate_material"),
        length_mm,
        material_stub.get("piezo_material"),
    )
    substrate_thickness_um = _safe_number(design.get("substrate_thickness_um"))
    if substrate_thickness_um is None:
        substrate_thickness_um = _default_substrate_thickness_um(substrate_material, length_mm)
        assumptions.append(f"defaulted substrate_thickness_um={substrate_thickness_um}")

    piezo_thickness_um = _safe_number(design.get("piezo_thickness_um"))
    if piezo_thickness_um is None:
        piezo_thickness_um = _default_piezo_thickness_um(
            material_stub.get("piezo_material"),
            substrate_material,
            length_mm,
        )
        assumptions.append(f"defaulted piezo_thickness_um={piezo_thickness_um}")

    tip_mass_g = _safe_number(design.get("tip_mass_g"))
    load_resistance_ohm = _safe_number(design.get("load_resistance_ohm"))
    if load_resistance_ohm is None:
        load_resistance_ohm = None

    return {
        "is_valid": substrate_thickness_um > 0 and piezo_thickness_um > 0,
        "beam_length_mm": length_mm,
        "beam_width_mm": width_mm,
        "substrate_thickness_um": substrate_thickness_um,
        "piezo_thickness_um": piezo_thickness_um,
        "tip_mass_g": tip_mass_g,
        "load_resistance_ohm": load_resistance_ohm,
    }


def _build_layers(geometry: dict, material: dict) -> list[dict]:
    width_m = geometry["beam_width_mm"] * 1e-3
    t_sub = geometry["substrate_thickness_um"] * 1e-6
    t_p = geometry["piezo_thickness_um"] * 1e-6
    layers = []
    structure_class = material["structure_class"]
    if structure_class == "bimorph":
        layers.append(
            {
                "name": "piezo_bottom",
                "width_m": width_m,
                "thickness_m": t_p,
                "modulus_pa": material["piezo_modulus_pa"],
                "density_kg_m3": material["piezo_density_kg_m3"],
                "is_piezo": True,
            }
        )
        layers.append(
            {
                "name": "substrate",
                "width_m": width_m,
                "thickness_m": t_sub,
                "modulus_pa": material["substrate_modulus_pa"],
                "density_kg_m3": material["substrate_density_kg_m3"],
                "is_piezo": False,
            }
        )
        layers.append(
            {
                "name": "piezo_top",
                "width_m": width_m,
                "thickness_m": t_p,
                "modulus_pa": material["piezo_modulus_pa"],
                "density_kg_m3": material["piezo_density_kg_m3"],
                "is_piezo": True,
            }
        )
    else:
        layers.append(
            {
                "name": "substrate",
                "width_m": width_m,
                "thickness_m": t_sub,
                "modulus_pa": material["substrate_modulus_pa"],
                "density_kg_m3": material["substrate_density_kg_m3"],
                "is_piezo": False,
            }
        )
        layers.append(
            {
                "name": "piezo_top",
                "width_m": width_m,
                "thickness_m": t_p,
                "modulus_pa": material["piezo_modulus_pa"],
                "density_kg_m3": material["piezo_density_kg_m3"],
                "is_piezo": True,
            }
        )
    return layers


def _composite_section(layers: list[dict]) -> dict:
    z_cursor = 0.0
    enriched = []
    axial_stiffness_sum = 0.0
    neutral_axis_numerator = 0.0
    mass_per_length = 0.0
    piezo_area_over_thickness_m = 0.0
    for layer in layers:
        thickness = layer["thickness_m"]
        width = layer["width_m"]
        area = width * thickness
        centroid = z_cursor + thickness / 2.0
        axial_stiffness = layer["modulus_pa"] * area
        axial_stiffness_sum += axial_stiffness
        neutral_axis_numerator += axial_stiffness * centroid
        mass_per_length += layer["density_kg_m3"] * area
        if layer["is_piezo"]:
            piezo_area_over_thickness_m += layer["width_m"] / max(thickness, 1e-12)
        enriched.append(
            {
                **layer,
                "area_m2": area,
                "centroid_m": centroid,
            }
        )
        z_cursor += thickness

    z_neutral = neutral_axis_numerator / axial_stiffness_sum
    bending_stiffness = 0.0
    max_distance = 0.0
    piezo_distances = []
    total_thickness = z_cursor
    for layer in enriched:
        width = layer["width_m"]
        thickness = layer["thickness_m"]
        area = layer["area_m2"]
        centroid = layer["centroid_m"]
        local_i = width * thickness**3 / 12.0
        bending_stiffness += layer["modulus_pa"] * (local_i + area * (centroid - z_neutral) ** 2)
        top = abs(z_cursor - z_neutral)
        bottom = abs(z_neutral)
        max_distance = max(max_distance, top, bottom)
        if layer["is_piezo"]:
            piezo_distances.append(abs(centroid - z_neutral))

    if not piezo_distances:
        piezo_distances = [total_thickness / 4.0]

    return {
        "neutral_axis_m": z_neutral,
        "bending_stiffness_n_m2": bending_stiffness,
        "mass_per_length_kg_m": mass_per_length,
        "max_distance_m": max_distance,
        "piezo_mean_distance_m": sum(piezo_distances) / len(piezo_distances),
        "total_thickness_m": total_thickness,
        "piezo_area_over_thickness_m": piezo_area_over_thickness_m,
    }


def _resolve_excitation(request: dict, resonant_frequency_hz: float, assumptions: list[str]) -> dict:
    excitation = request.get("excitation_settings") or {}
    frequency_hz = _coalesce(
        _safe_number(excitation.get("frequency_hz")),
        _safe_number((request.get("constraint_context") or {}).get("target_resonant_frequency_hz")),
        resonant_frequency_hz,
    )
    acceleration_ms2 = _coalesce(
        _safe_number(excitation.get("acceleration_ms2")),
        None,
    )
    acceleration_g = _safe_number(excitation.get("acceleration_g"))
    if acceleration_ms2 is None and acceleration_g is not None:
        acceleration_ms2 = acceleration_g * 9.81
    base_displacement_mm = _safe_number(excitation.get("base_displacement_mm"))
    if acceleration_ms2 is None and base_displacement_mm is not None and frequency_hz is not None:
        omega = 2.0 * math.pi * max(frequency_hz, 1e-9)
        acceleration_ms2 = base_displacement_mm * 1e-3 * omega**2
    if acceleration_ms2 is None:
        acceleration_ms2 = 9.81
        assumptions.append("defaulted excitation acceleration to 1g")
    return {
        "frequency_hz": frequency_hz,
        "acceleration_ms2": acceleration_ms2,
        "base_displacement_mm": base_displacement_mm,
    }


def _load_resistance_ohm(request: dict, geometry: dict, assumptions: list[str]) -> float:
    load = request.get("load_settings") or {}
    value = _coalesce(_safe_number(load.get("load_resistance_ohm")), geometry.get("load_resistance_ohm"))
    if value is None:
        value = 1e6
        assumptions.append("defaulted load_resistance_ohm=1000000")
    return max(value, 1.0)


def _task_context(task: dict | None, request: dict) -> dict:
    if task is None:
        task_type = _parse_task_type(request.get("task_id"))
        return {
            "task_type": task_type,
            "frequency_tolerance_pct": DEFAULT_FREQUENCY_TOLERANCE_PCT,
        }
    hard = task.get("hard_constraints") or {}
    return {
        "task_type": task.get("task_type"),
        "frequency_tolerance_pct": _coalesce(
            _safe_number(hard.get("frequency_error_tolerance_pct")),
            DEFAULT_FREQUENCY_TOLERANCE_PCT,
        ),
    }


def _evaluate_raw_outputs(request: dict) -> tuple[dict, list[str], bool]:
    assumptions: list[str] = []
    geometry = _resolved_geometry(request, assumptions)
    if not geometry["is_valid"]:
        return (
            {
                "resonant_frequency_hz": None,
                "tip_displacement_mm": None,
                "root_stress_mpa": None,
                "load_power_uw": None,
                "open_circuit_voltage_v": None,
            },
            assumptions,
            False,
        )

    material = _resolved_material_profile(request, geometry, assumptions)
    layers = _build_layers(geometry, material)
    section = _composite_section(layers)
    length_m = geometry["beam_length_mm"] * 1e-3
    tip_mass_kg = 0.0 if geometry["tip_mass_g"] is None else geometry["tip_mass_g"] * 1e-3
    beam_mass_kg = section["mass_per_length_kg_m"] * length_m
    effective_mass = tip_mass_kg + MODAL_MASS_COEFFICIENT * beam_mass_kg
    if effective_mass <= 0 or section["bending_stiffness_n_m2"] <= 0 or length_m <= 0:
        return (
            {
                "resonant_frequency_hz": None,
                "tip_displacement_mm": None,
                "root_stress_mpa": None,
                "load_power_uw": None,
                "open_circuit_voltage_v": None,
            },
            assumptions,
            False,
        )

    tip_stiffness = 3.0 * section["bending_stiffness_n_m2"] / (length_m**3)
    resonant_frequency_hz = (
        math.sqrt(tip_stiffness / effective_mass) / (2.0 * math.pi) * FREQUENCY_SCALE
    )
    excitation = _resolve_excitation(request, resonant_frequency_hz, assumptions)
    input_frequency_hz = excitation["frequency_hz"]
    q_factor = _estimate_quality_factor(
        material["structure_class"],
        material["piezo_material"],
        material["substrate_material"],
        geometry["beam_length_mm"],
        resonant_frequency_hz,
        geometry["tip_mass_g"],
    )
    omega_n = 2.0 * math.pi * max(resonant_frequency_hz, 1e-9)
    omega = 2.0 * math.pi * max(input_frequency_hz, 1e-9)
    r = omega / omega_n
    dynamic_factor = 1.0 / math.sqrt((1.0 - r**2) ** 2 + (r / max(q_factor, 1e-9)) ** 2)
    tip_displacement_m = (
        excitation["acceleration_ms2"] / max(omega_n**2, 1e-9) * dynamic_factor * DISPLACEMENT_SCALE
    )
    curvature = 3.0 * tip_displacement_m / max(length_m**2, 1e-12)
    max_stress_pa = 0.0
    for layer in layers:
        distance = section["max_distance_m"]
        layer_stress = layer["modulus_pa"] * abs(curvature) * distance
        max_stress_pa = max(max_stress_pa, layer_stress)
    root_stress_mpa = max_stress_pa / 1e6

    piezo_stress_pa = material["piezo_modulus_pa"] * abs(curvature) * section["piezo_mean_distance_m"]
    open_circuit_voltage_v = (
        abs(material["g31_vm_per_n"])
        * piezo_stress_pa
        * geometry["piezo_thickness_um"]
        * 1e-6
        * (2.0 if material["structure_class"] == "bimorph" else 1.0)
        * material["voltage_scale"]
    )

    load_resistance_ohm = _load_resistance_ohm(request, geometry, assumptions)
    piezo_capacitance_f = (
        EPS0
        * material["epsilon_r"]
        * length_m
        * section["piezo_area_over_thickness_m"]
    )
    if piezo_capacitance_f > 0:
        reactance_ohm = 1.0 / (omega * piezo_capacitance_f)
        transfer = load_resistance_ohm / math.sqrt(load_resistance_ohm**2 + reactance_ohm**2)
    else:
        reactance_ohm = None
        transfer = 1.0
    load_voltage_rms = open_circuit_voltage_v / math.sqrt(2.0) * transfer
    load_power_uw = load_voltage_rms**2 / load_resistance_ohm * 1e6

    if reactance_ohm is None:
        assumptions.append("piezo_capacitance unavailable; used ideal resistive transfer")

    return (
        {
            "resonant_frequency_hz": resonant_frequency_hz,
            "tip_displacement_mm": tip_displacement_m * 1e3,
            "root_stress_mpa": root_stress_mpa,
            "load_power_uw": load_power_uw,
            "open_circuit_voltage_v": open_circuit_voltage_v,
        },
        assumptions + [f"quality_factor={round(q_factor, 3)}"],
        True,
    )


def _build_reference_request(request: dict, task: dict) -> dict | None:
    reference = task.get("reference_solution") or {}
    if not reference:
        return None
    design_parameters = dict(request.get("design_parameters") or {})
    for key in (
        "beam_length_mm",
        "beam_width_mm",
        "substrate_thickness_um",
        "piezo_thickness_um",
        "tip_mass_g",
        "load_resistance_ohm",
    ):
        if reference.get(key) is not None:
            design_parameters[key] = reference.get(key)

    load_settings = dict(request.get("load_settings") or {})
    if design_parameters.get("load_resistance_ohm") is not None:
        load_settings["load_resistance_ohm"] = design_parameters["load_resistance_ohm"]

    return {
        **request,
        "design_parameters": design_parameters,
        "load_settings": load_settings,
    }


def _apply_task_local_anchors(
    outputs: dict,
    request: dict,
    task: dict,
    assumptions: list[str],
) -> dict:
    anchored = dict(outputs)
    reference_request = _build_reference_request(request, task)
    if reference_request is None:
        return anchored

    reference_outputs, _, reference_valid = _evaluate_raw_outputs(reference_request)
    if not reference_valid:
        return anchored

    context = request.get("constraint_context") or {}
    target_frequency = _safe_number(context.get("target_resonant_frequency_hz"))
    if (
        target_frequency is not None
        and outputs.get("resonant_frequency_hz") is not None
        and reference_outputs.get("resonant_frequency_hz") not in (None, 0)
    ):
        anchored["resonant_frequency_hz"] = (
            target_frequency
            * outputs["resonant_frequency_hz"]
            / reference_outputs["resonant_frequency_hz"]
        )
        assumptions.append("applied task-local frequency anchor")

    power_anchor = None
    if task.get("task_type") == "constrained_power_maximization":
        power_anchor = _coalesce(
            _safe_number(task.get("objective", {}).get("target_value")),
            _safe_number(context.get("power_target_uw")),
        )
    if (
        power_anchor is not None
        and outputs.get("load_power_uw") is not None
        and reference_outputs.get("load_power_uw") not in (None, 0)
    ):
        scale = outputs["load_power_uw"] / reference_outputs["load_power_uw"]
        anchored["load_power_uw"] = power_anchor * scale
        if outputs.get("open_circuit_voltage_v") is not None and anchored["load_power_uw"] >= 0:
            voltage_scale = math.sqrt(max(anchored["load_power_uw"], 0.0) / max(outputs["load_power_uw"], 1e-12))
            anchored["open_circuit_voltage_v"] = outputs["open_circuit_voltage_v"] * voltage_scale
        assumptions.append("applied task-local power anchor")

    return anchored


def _violations_and_objective(
    outputs: dict,
    request: dict,
    task: dict | None,
    is_valid_request: bool,
) -> tuple[list[str], float | None, float | None]:
    if not is_valid_request:
        return ["invalid_geometry"], None, None

    context = request.get("constraint_context") or {}
    task_ctx = _task_context(task, request)
    target_frequency = _safe_number(context.get("target_resonant_frequency_hz"))
    frequency_tolerance_pct = task_ctx["frequency_tolerance_pct"]
    stress_limit = _safe_number(context.get("stress_limit_mpa"))
    displacement_limit = _safe_number(context.get("displacement_limit_mm"))
    power_target = _safe_number(context.get("power_target_uw"))

    freq = outputs["resonant_frequency_hz"]
    displacement = outputs["tip_displacement_mm"]
    stress = outputs["root_stress_mpa"]
    power = outputs["load_power_uw"]

    violations: list[str] = []
    frequency_error_hz = None
    frequency_error_pct = None
    if target_frequency is not None and freq is not None:
        frequency_error_hz = abs(freq - target_frequency)
        frequency_error_pct = frequency_error_hz / max(abs(target_frequency), 1e-9) * 100.0
        if frequency_error_pct > frequency_tolerance_pct:
            if freq > target_frequency:
                violations.append("frequency_too_high")
            else:
                violations.append("frequency_too_low")

    if stress_limit is not None and stress is not None and stress > stress_limit:
        violations.append("stress_exceeded")
    if displacement_limit is not None and displacement is not None and displacement > displacement_limit:
        violations.append("displacement_exceeded")
    if power_target is not None and power is not None and power < power_target:
        violations.append("power_below_target")

    task_type = task_ctx["task_type"]
    objective_value = None
    normalized_objective = None
    if task_type == "frequency_matching":
        objective_value = frequency_error_hz
        if frequency_error_pct is not None:
            normalized_objective = max(0.0, 1.0 - frequency_error_pct / max(frequency_tolerance_pct, 1e-9))
    elif task_type == "constrained_power_maximization":
        objective_value = power
        if power_target is not None and power is not None:
            normalized_objective = power / max(power_target, 1e-9)
    elif task_type == "feasibility_repair":
        objective_value = float(len(violations))
        normalized_objective = 1.0 if not violations else 1.0 / (1.0 + len(violations))

    return sorted(set(violations)), objective_value, normalized_objective


def _solver_visible_message(outputs: dict, violations: list[str], is_valid_request: bool) -> str:
    if not is_valid_request:
        return "Invalid geometry; missing or non-positive cantilever dimensions."
    msg = (
        f"f={outputs['resonant_frequency_hz']} Hz, "
        f"x={outputs['tip_displacement_mm']} mm, "
        f"stress={outputs['root_stress_mpa']} MPa, "
        f"power={outputs['load_power_uw']} uW"
    )
    if violations:
        return f"{msg}; violations={','.join(violations)}"
    return f"{msg}; feasible"


def evaluate_request(
    request: dict,
    task: dict | None = None,
    apply_frequency_calibration: bool = False,
    calibration_profile: dict | None = None,
) -> dict:
    start = time.perf_counter()
    outputs, assumptions, is_valid_request = _evaluate_raw_outputs(request)
    if is_valid_request and apply_frequency_calibration:
        calibration_profile = calibration_profile or load_frequency_profile()
        calibrated_frequency, note = apply_frequency_profile(outputs, request, calibration_profile)
        outputs["resonant_frequency_hz"] = calibrated_frequency
        if note:
            assumptions.append(note)
    if is_valid_request and task is not None:
        outputs = _apply_task_local_anchors(outputs, request, task, assumptions)
    rounded_outputs = {
        "resonant_frequency_hz": None
        if outputs.get("resonant_frequency_hz") is None
        else round(outputs["resonant_frequency_hz"], 6),
        "tip_displacement_mm": None
        if outputs.get("tip_displacement_mm") is None
        else round(outputs["tip_displacement_mm"], 12),
        "root_stress_mpa": None
        if outputs.get("root_stress_mpa") is None
        else round(outputs["root_stress_mpa"], 9),
        "load_power_uw": None
        if outputs.get("load_power_uw") is None
        else round(outputs["load_power_uw"], 15),
        "open_circuit_voltage_v": None
        if outputs.get("open_circuit_voltage_v") is None
        else round(outputs["open_circuit_voltage_v"], 12),
    }
    violations, objective_value, normalized_objective = _violations_and_objective(
        rounded_outputs,
        request,
        task,
        is_valid_request,
    )
    wall_time_ms = int((time.perf_counter() - start) * 1000)
    response = {
        "verifier_version": VERIFIER_VERSION,
        "is_valid_request": is_valid_request,
        "is_feasible": is_valid_request and not violations,
        "outputs": rounded_outputs,
        "violations": violations,
        "objective_value": None if objective_value is None else round(objective_value, 6),
        "normalized_objective": None if normalized_objective is None else round(normalized_objective, 6),
        "diagnostics": {
            "wall_time_ms": wall_time_ms,
            "solver_visible_message": _solver_visible_message(rounded_outputs, violations, is_valid_request),
            "assumption_notes": "; ".join(assumptions) if assumptions else None,
        },
    }
    return {
        "schema_version": "vehbench_verifier_io_v1",
        "record_type": "verifier_interaction",
        "request": request,
        "response": response,
    }


def evaluate_request_record(
    request_record: dict,
    task: dict | None = None,
    apply_frequency_calibration: bool = False,
    calibration_profile: dict | None = None,
) -> dict:
    request = request_record["request"]
    return evaluate_request(
        request,
        task=task,
        apply_frequency_calibration=apply_frequency_calibration,
        calibration_profile=calibration_profile,
    )
