#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parents[1]
import sys

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.synthetic import (
    bounded,
    build_beam_fem_frequency,
    build_request,
    candidate_to_unit,
    clamp_candidate,
    hash_seed,
    load_jsonl,
    unit_to_candidate,
    write_jsonl,
)
from vehbench.verifier.v1.evaluator import evaluate_request


SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "paper_grounded_task_seeds.jsonl"
TASKS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "tasks_paper_grounded.jsonl"
TARGET_SYNTHETIC_COUNT = 1000
FREQUENCY_LABEL_SOURCE = "beam_fem_1d_v1"
ELECTROMECH_LABEL_SOURCE = "vehbench_verifier_surrogate_v1"
RUNTIME_FREQUENCY_LABEL_SOURCE = "vehbench_verifier_calibrated_v1"
SYNTHETIC_VERSION = "v2"
OUT_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / f"synthetic_pilot_{SYNTHETIC_VERSION}_seeds.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / f"synthetic_pilot_{SYNTHETIC_VERSION}.md"


def prune_none(mapping: dict) -> dict:
    out = {}
    for key, value in mapping.items():
        if isinstance(value, dict):
            nested = prune_none(value)
            if nested:
                out[key] = nested
        elif value is not None:
            out[key] = value
    return out


def build_anchor_split_map() -> dict[str, dict]:
    split_map = {}
    for task in load_jsonl(TASKS_PATH):
        refs = task.get("source_refs") or {}
        seed_id = refs.get("source_record_id")
        if seed_id and seed_id not in split_map:
            split_map[seed_id] = dict(task["split"])
    return split_map


def ready_anchors() -> list[dict]:
    split_map = build_anchor_split_map()
    anchors = []
    for seed in load_jsonl(SEEDS_PATH):
        if seed.get("mapping_status") != "ready":
            continue
        if seed["seed_id"] not in split_map:
            continue
        anchors.append({**seed, "assigned_split": split_map[seed["seed_id"]]})
    anchors.sort(key=lambda row: row["seed_id"])
    return anchors


def allocate_counts(anchors: list[dict], total: int) -> dict[str, int]:
    base = total // len(anchors)
    remainder = total % len(anchors)
    counts = {}
    for idx, anchor in enumerate(anchors):
        counts[anchor["seed_id"]] = base + (1 if idx < remainder else 0)
    return counts


def sample_policy(sample_index: int) -> str:
    if sample_index % 10 == 0:
        return "boundary_push"
    if sample_index % 4 == 0:
        return "wide_gaussian"
    return "local_gaussian"


def sample_candidate(anchor: dict, sample_index: int) -> tuple[dict, str, int]:
    blueprint = anchor["task_blueprints"][0]
    variable_bounds = blueprint["variable_bounds"]
    base_candidate = clamp_candidate(variable_bounds, anchor["verifier_mapping"]["design_parameters"])
    base_unit = np.array(candidate_to_unit(variable_bounds, base_candidate), dtype=float)
    policy = sample_policy(sample_index)
    rng_seed = hash_seed(f"{anchor['seed_id']}::{sample_index}::{policy}")
    rng = np.random.default_rng(rng_seed)

    if policy == "local_gaussian":
        vector = np.clip(rng.normal(base_unit, 0.08), 0.04, 0.96)
    elif policy == "wide_gaussian":
        vector = np.clip(rng.normal(base_unit, 0.13), 0.04, 0.96)
    else:
        vector = base_unit.copy()
        dim_count = min(len(vector), 2 if len(vector) >= 4 else 1)
        dims = rng.choice(len(vector), size=dim_count, replace=False)
        for dim in np.atleast_1d(dims):
            direction = 0.10 if vector[dim] >= 0.5 else 0.90
            vector[dim] = float(np.clip(direction + rng.normal(0.0, 0.015), 0.04, 0.96))
        untouched = [idx for idx in range(len(vector)) if idx not in set(np.atleast_1d(dims))]
        for dim in untouched:
            vector[dim] = float(np.clip(rng.normal(vector[dim], 0.05), 0.04, 0.96))

    candidate = unit_to_candidate(variable_bounds, vector.tolist())
    return candidate, policy, rng_seed


def candidate_bounds(candidate: dict) -> dict:
    return prune_none(
        {
            "beam_length_mm": bounded(candidate.get("beam_length_mm"), "mm", 0.85, 1.15),
            "beam_width_mm": bounded(candidate.get("beam_width_mm"), "mm", 0.85, 1.15),
            "substrate_thickness_um": bounded(candidate.get("substrate_thickness_um"), "um", 0.85, 1.15),
            "piezo_thickness_um": bounded(candidate.get("piezo_thickness_um"), "um", 0.85, 1.15),
            "tip_mass_g": bounded(candidate.get("tip_mass_g"), "g", 0.75, 1.25),
            "load_resistance_ohm": bounded(candidate.get("load_resistance_ohm"), "ohm", 0.1, 10.0),
        }
    )


def build_blueprints(anchor: dict, candidate: dict, frequency_hz: float, power_w: float | None) -> list[dict]:
    excitation = anchor["verifier_mapping"]["excitation_settings"]
    material = anchor["verifier_mapping"]["material_parameters"]
    bounds = candidate_bounds(candidate)
    fixed_conditions = {
        "device_type": "piezoelectric_cantilever",
        "structure_class": material.get("structure_class"),
        "piezo_material": material.get("piezo_material"),
        "substrate_material": material.get("substrate_material"),
        "excitation_frequency_hz": excitation.get("frequency_hz"),
        "acceleration_g": excitation.get("acceleration_g"),
        "target_resonant_frequency_hz": round(frequency_hz, 6),
        "load_type": "resistive",
        "notes": f"synthetic_anchor:{anchor['seed_id']}",
    }
    blueprints = [
        {
            "task_type": "frequency_matching",
            "variable_bounds": bounds,
            "fixed_conditions": dict(fixed_conditions),
            "hard_constraints": {
                "frequency_error_tolerance_pct": 2.0,
                "require_linear_regime": True,
                "geometry_notes": "synthetic pilot around anchor-conditioned design",
            },
            "objective": {
                "name": "match_resonant_frequency",
                "direction": "target",
                "target_value": round(frequency_hz, 6),
                "target_unit": "Hz",
            },
            "budget_hint": 24,
        },
        {
            "task_type": "feasibility_repair",
            "variable_bounds": bounds,
            "fixed_conditions": dict(fixed_conditions),
            "hard_constraints": {
                "require_linear_regime": True,
                "geometry_notes": "repair synthetic candidate around anchor-conditioned design",
            },
            "objective": {
                "name": "repair_feasibility",
                "direction": "minimize",
                "target_value": None,
                "target_unit": None,
            },
            "budget_hint": 16,
        },
    ]
    if power_w is not None and power_w > 0:
        blueprints.append(
            {
                "task_type": "constrained_power_maximization",
                "variable_bounds": bounds,
                "fixed_conditions": dict(fixed_conditions),
                "hard_constraints": {
                    "power_target_uw": round(power_w * 1e6, 6),
                    "require_linear_regime": True,
                    "geometry_notes": "power target from surrogate-labeled synthetic candidate",
                },
                "objective": {
                    "name": "maximize_feasible_power",
                    "direction": "maximize",
                    "target_value": round(power_w * 1e6, 6),
                    "target_unit": "uW",
                },
                "budget_hint": 32,
            }
        )
    return blueprints


def build_seed(anchor: dict, sample_index: int) -> dict | None:
    synthetic_seed_id = f"{anchor['seed_id']}::syn::{sample_index:04d}"
    candidate, policy, rng_seed = sample_candidate(anchor, sample_index)
    request = build_request(anchor, candidate, synthetic_seed_id)

    fem_frequency_hz, fem_assumptions = build_beam_fem_frequency(request)
    if fem_frequency_hz is None:
        return None

    interaction = evaluate_request(
        request,
        task=None,
        apply_frequency_calibration=True,
        calibration_profile=None,
        use_task_anchors=False,
    )
    response = interaction["response"]
    outputs = response.get("outputs") or {}
    diagnostics = response.get("diagnostics") or {}
    surrogate_assumptions = []
    assumption_notes = diagnostics.get("assumption_notes")
    if assumption_notes:
        surrogate_assumptions = [item.strip() for item in assumption_notes.split(";") if item.strip()]

    runtime_frequency_hz = outputs.get("resonant_frequency_hz")
    if runtime_frequency_hz is None:
        return None

    observed_outputs = {
        "resonant_frequency_hz": round(runtime_frequency_hz, 6),
        "load_power_w": None if outputs.get("load_power_uw") is None else float(outputs["load_power_uw"]) * 1e-6,
        "open_circuit_voltage_v": outputs.get("open_circuit_voltage_v"),
        "short_circuit_current_a": None,
        "bandwidth_hz": None,
        "tip_displacement_mm": outputs.get("tip_displacement_mm"),
        "root_stress_mpa": outputs.get("root_stress_mpa"),
    }
    task_blueprints = build_blueprints(anchor, candidate, runtime_frequency_hz, observed_outputs["load_power_w"])
    ood_tags = list((anchor["assigned_split"] or {}).get("ood_tags") or [])
    if policy == "boundary_push":
        ood_tags = sorted(set(ood_tags + ["synthetic_boundary_push"]))

    return {
        "schema_version": "vehbench_anchor_conditioned_synthetic_seed_v1",
        "record_type": "anchor_conditioned_synthetic_seed",
        "synthetic_seed_id": synthetic_seed_id,
        "source_type": "synthetic",
        "parent_anchor_id": anchor["seed_id"],
        "parent_paper_id": anchor["source_paper_id"],
        "parent_doi": anchor.get("source_doi"),
        "assigned_split": {
            "name": anchor["assigned_split"]["name"],
            "ood_tags": ood_tags,
        },
        "sample_policy": policy,
        "sample_index": sample_index,
        "label_provenance": {
            "frequency_label_source": FREQUENCY_LABEL_SOURCE,
            "runtime_frequency_label_source": RUNTIME_FREQUENCY_LABEL_SOURCE,
            "electromechanical_label_source": ELECTROMECH_LABEL_SOURCE,
            "rng_seed": rng_seed,
            "raw_fem_frequency_hz": round(fem_frequency_hz, 6),
            "runtime_calibrated_frequency_hz": round(runtime_frequency_hz, 6),
            "fem_assumptions": fem_assumptions,
            "surrogate_assumptions": surrogate_assumptions,
        },
        "verifier_mapping": {
            "design_parameters": dict(candidate),
            "excitation_settings": dict(anchor["verifier_mapping"]["excitation_settings"]),
            "load_settings": {
                "load_type": "resistive",
                "load_resistance_ohm": candidate.get("load_resistance_ohm"),
            },
            "material_parameters": dict(anchor["verifier_mapping"]["material_parameters"]),
            "observed_outputs": observed_outputs,
            "missing_for_verifier": [],
        },
        "task_blueprints": task_blueprints,
    }


def main() -> None:
    anchors = ready_anchors()
    counts = allocate_counts(anchors, TARGET_SYNTHETIC_COUNT)
    rows = []
    dropped = 0
    for anchor in anchors:
        for sample_index in range(counts[anchor["seed_id"]]):
            record = build_seed(anchor, sample_index)
            if record is None:
                dropped += 1
                continue
            rows.append(record)

    rows = rows[:TARGET_SYNTHETIC_COUNT]
    write_jsonl(OUT_PATH, rows)

    split_counter = Counter(row["assigned_split"]["name"] for row in rows)
    policy_counter = Counter(row["sample_policy"] for row in rows)
    task_counter = Counter()
    for row in rows:
        for blueprint in row["task_blueprints"]:
            task_counter[blueprint["task_type"]] += 1

    lines = [
        f"# Synthetic Pilot {SYNTHETIC_VERSION.upper()}",
        "",
        f"- ready anchors used: `{len(anchors)}`",
        f"- target synthetic seeds: `{TARGET_SYNTHETIC_COUNT}`",
        f"- generated synthetic seeds: `{len(rows)}`",
        f"- dropped during FEM labeling: `{dropped}`",
        "",
        "## Split Counts",
        "",
    ]
    for split_name in ("train", "val", "test-id", "test-ood"):
        lines.append(f"- {split_name}: `{split_counter.get(split_name, 0)}`")
    lines.extend(["", "## Sampling Policies", ""])
    for policy in ("local_gaussian", "wide_gaussian", "boundary_push"):
        lines.append(f"- {policy}: `{policy_counter.get(policy, 0)}`")
    lines.extend(["", "## Task Blueprint Counts", ""])
    for task_type in ("frequency_matching", "constrained_power_maximization", "feasibility_repair"):
        lines.append(f"- {task_type}: `{task_counter.get(task_type, 0)}`")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "anchors": len(anchors),
                "synthetic_seeds": len(rows),
                "split_counter": split_counter,
                "policy_counter": policy_counter,
                "task_counter": task_counter,
                "output": str(OUT_PATH),
            },
            indent=2,
            default=lambda value: dict(value),
        )
    )


if __name__ == "__main__":
    main()
