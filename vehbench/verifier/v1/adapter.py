from __future__ import annotations

from copy import deepcopy


VERIFIER_VERSION = "vehbench_verifier_v1"
VERIFIER_MODEL_FAMILY = "cantilever_linear_lumped_v1"
VIOLATION_LABELS = [
    "frequency_too_high",
    "frequency_too_low",
    "stress_exceeded",
    "displacement_exceeded",
    "power_below_target",
    "invalid_geometry",
]


def candidate_parameter_keys() -> tuple[str, ...]:
    return (
        "beam_length_mm",
        "beam_width_mm",
        "substrate_thickness_um",
        "piezo_thickness_um",
        "tip_mass_g",
        "load_resistance_ohm",
    )


def compact_candidate(candidate: dict | None) -> dict:
    candidate = candidate or {}
    return {key: candidate.get(key) for key in candidate_parameter_keys()}


def build_constraint_context(task: dict) -> dict:
    hard = deepcopy(task.get("hard_constraints") or {})
    fixed = task.get("fixed_conditions") or {}
    return {
        "target_resonant_frequency_hz": fixed.get("target_resonant_frequency_hz"),
        "stress_limit_mpa": hard.get("stress_limit_mpa"),
        "displacement_limit_mm": hard.get("displacement_limit_mm"),
        "power_target_uw": hard.get("power_target_uw"),
    }


def select_candidate(task: dict) -> tuple[str, dict]:
    if task.get("task_type") == "feasibility_repair":
        return "initial_candidate", compact_candidate(task.get("initial_candidate"))
    return "reference_solution", compact_candidate(task.get("reference_solution"))


def build_request(task: dict, seed: dict) -> dict:
    candidate_role, candidate = select_candidate(task)
    verifier_mapping = seed["verifier_mapping"]
    excitation_settings = deepcopy(verifier_mapping["excitation_settings"])
    load_settings = deepcopy(verifier_mapping["load_settings"])
    load_value = candidate.get("load_resistance_ohm")
    if load_value is not None:
        load_settings["load_resistance_ohm"] = load_value
        load_settings["load_type"] = "resistive"

    return {
        "task_id": task["task_id"],
        "candidate_id": f"{task['task_id']}::{candidate_role}",
        "design_parameters": candidate,
        "material_parameters": deepcopy(verifier_mapping["material_parameters"]),
        "excitation_settings": excitation_settings,
        "load_settings": load_settings,
        "constraint_context": build_constraint_context(task),
    }


def build_request_record(task: dict, seed: dict) -> dict:
    candidate_role, _ = select_candidate(task)
    return {
        "schema_version": "vehbench_verifier_request_adapter_v1",
        "record_type": "verifier_request_adapter",
        "task_id": task["task_id"],
        "source_paper_id": seed["source_paper_id"],
        "source_seed_id": seed["seed_id"],
        "candidate_role": candidate_role,
        "request": build_request(task, seed),
    }
