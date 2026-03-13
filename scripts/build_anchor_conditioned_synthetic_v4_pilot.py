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

from vehbench.fem import evaluate_cantilever_request, format_observed_outputs
from vehbench.synthetic import (
    bounded,
    build_request,
    candidate_to_unit,
    clamp_candidate,
    hash_seed,
    load_jsonl,
    unit_to_candidate,
    write_jsonl,
)


BENCH_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
SEEDS_PATH = BENCH_DIR / "paper_grounded_task_seeds.jsonl"
TASKS_PATH = BENCH_DIR / "tasks_paper_grounded.jsonl"
CONFIG_PATH = PROJECT_ROOT / "configs" / "synthetic_v4_generation_spec.json"
OUT_PATH = BENCH_DIR / "synthetic_v4_pilot_1k_seeds.jsonl"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "synthetic_v4_pilot_1k.md"


def load_config() -> dict:
    return json.loads(CONFIG_PATH.read_text())


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
    return {
        anchor["seed_id"]: base + (1 if idx < remainder else 0)
        for idx, anchor in enumerate(anchors)
    }


def sample_policy(sample_index: int) -> str:
    policies = [
        "local_gaussian",
        "wide_gaussian",
        "geometry_edge_push",
        "thickness_exchange",
        "load_sweep",
    ]
    return policies[sample_index % len(policies)]


def _push_edge(value: float, rng: np.random.Generator) -> float:
    return float(np.clip((0.08 if value < 0.5 else 0.92) + rng.normal(0.0, 0.025), 0.03, 0.97))


def sample_candidate(anchor: dict, sample_index: int) -> tuple[dict, str, int]:
    blueprint = anchor["task_blueprints"][0]
    variable_bounds = blueprint["variable_bounds"]
    base_candidate = clamp_candidate(variable_bounds, anchor["verifier_mapping"]["design_parameters"])
    base_unit = np.array(candidate_to_unit(variable_bounds, base_candidate), dtype=float)
    policy = sample_policy(sample_index)
    rng_seed = hash_seed(f"{anchor['seed_id']}::{sample_index}::{policy}::v4")
    rng = np.random.default_rng(rng_seed)
    vector = base_unit.copy()
    keys = list(variable_bounds.keys())

    if policy == "local_gaussian":
        vector = np.clip(rng.normal(base_unit, 0.07), 0.03, 0.97)
    elif policy == "wide_gaussian":
        vector = np.clip(rng.normal(base_unit, 0.14), 0.03, 0.97)
    elif policy == "geometry_edge_push":
        for idx, key in enumerate(keys):
            if key in {"beam_length_mm", "beam_width_mm", "tip_mass_g"}:
                vector[idx] = _push_edge(base_unit[idx], rng)
            else:
                vector[idx] = float(np.clip(rng.normal(base_unit[idx], 0.06), 0.03, 0.97))
    elif policy == "thickness_exchange":
        for idx, key in enumerate(keys):
            if key == "substrate_thickness_um":
                vector[idx] = float(np.clip(base_unit[idx] + 0.18 + rng.normal(0.0, 0.04), 0.03, 0.97))
            elif key == "piezo_thickness_um":
                vector[idx] = float(np.clip(base_unit[idx] - 0.15 + rng.normal(0.0, 0.04), 0.03, 0.97))
            else:
                vector[idx] = float(np.clip(rng.normal(base_unit[idx], 0.06), 0.03, 0.97))
    else:
        for idx, key in enumerate(keys):
            if key == "load_resistance_ohm":
                vector[idx] = _push_edge(base_unit[idx], rng)
            else:
                vector[idx] = float(np.clip(rng.normal(base_unit[idx], 0.08), 0.03, 0.97))

    candidate = unit_to_candidate(variable_bounds, vector.tolist())
    return candidate, policy, rng_seed


def candidate_bounds(candidate: dict) -> dict:
    return prune_none(
        {
            "beam_length_mm": bounded(candidate.get("beam_length_mm"), "mm", 0.88, 1.12),
            "beam_width_mm": bounded(candidate.get("beam_width_mm"), "mm", 0.88, 1.12),
            "substrate_thickness_um": bounded(candidate.get("substrate_thickness_um"), "um", 0.9, 1.12),
            "piezo_thickness_um": bounded(candidate.get("piezo_thickness_um"), "um", 0.9, 1.12),
            "tip_mass_g": bounded(candidate.get("tip_mass_g"), "g", 0.75, 1.25),
            "load_resistance_ohm": bounded(candidate.get("load_resistance_ohm"), "ohm", 0.08, 12.0),
        }
    )


def build_blueprints(anchor: dict, candidate: dict, outputs: dict) -> list[dict]:
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
        "target_resonant_frequency_hz": round(outputs["resonant_frequency_hz"], 6),
        "load_type": "resistive",
        "notes": f"synthetic_anchor:{anchor['seed_id']}",
    }
    blueprints = [
        {
            "task_type": "frequency_matching",
            "variable_bounds": bounds,
            "fixed_conditions": dict(fixed_conditions),
            "hard_constraints": {
                "frequency_error_tolerance_pct": 1.5,
                "require_linear_regime": True,
                "stress_limit_mpa": outputs.get("root_stress_mpa"),
                "displacement_limit_mm": outputs.get("tip_displacement_mm"),
                "geometry_notes": "synthetic_v4 around FEM-labeled anchor-conditioned design",
            },
            "objective": {
                "name": "match_resonant_frequency",
                "direction": "target",
                "target_value": round(outputs["resonant_frequency_hz"], 6),
                "target_unit": "Hz",
            },
            "budget_hint": 18,
        },
        {
            "task_type": "feasibility_repair",
            "variable_bounds": bounds,
            "fixed_conditions": dict(fixed_conditions),
            "hard_constraints": {
                "frequency_error_tolerance_pct": 1.2,
                "require_linear_regime": True,
                "stress_limit_mpa": outputs.get("root_stress_mpa"),
                "displacement_limit_mm": outputs.get("tip_displacement_mm"),
                "geometry_notes": "repair synthetic candidate around FEM-labeled design point",
            },
            "objective": {
                "name": "repair_feasibility",
                "direction": "minimize",
                "target_value": None,
                "target_unit": None,
            },
            "budget_hint": 12,
        },
    ]
    if outputs.get("load_power_w") is not None and outputs.get("load_power_w", 0.0) > 0:
        blueprints.append(
            {
                "task_type": "constrained_power_maximization",
                "variable_bounds": bounds,
                "fixed_conditions": dict(fixed_conditions),
                "hard_constraints": {
                    "power_target_uw": round(float(outputs["load_power_w"]) * 1e6, 6),
                    "require_linear_regime": True,
                    "stress_limit_mpa": outputs.get("root_stress_mpa"),
                    "displacement_limit_mm": outputs.get("tip_displacement_mm"),
                    "geometry_notes": "maximize synthetic v4 power around FEM/electromech anchor-conditioned regime",
                },
                "objective": {
                    "name": "maximize_feasible_power",
                    "direction": "maximize",
                    "target_value": round(float(outputs["load_power_w"]) * 1e6, 6),
                    "target_unit": "uW",
                },
                "budget_hint": 24,
            }
        )
    return blueprints


def build_seed(anchor: dict, sample_index: int, config: dict) -> dict | None:
    synthetic_seed_id = f"{anchor['seed_id']}::v4::{sample_index:04d}"
    candidate, policy, rng_seed = sample_candidate(anchor, sample_index)
    request = build_request(anchor, candidate, synthetic_seed_id)
    outputs, assumptions, valid = evaluate_cantilever_request(
        request,
        element_count=int(config["element_count"]),
    )
    if not valid:
        return None
    formatted_outputs = format_observed_outputs(outputs)
    ood_tags = list((anchor["assigned_split"] or {}).get("ood_tags") or [])
    policy_tag = {
        "geometry_edge_push": "synthetic_geometry_edge_push",
        "thickness_exchange": "synthetic_thickness_exchange",
        "load_sweep": "synthetic_load_sweep",
    }.get(policy)
    if policy_tag is not None:
        ood_tags = sorted(set(ood_tags + [policy_tag]))

    return {
        "schema_version": "vehbench_anchor_conditioned_synthetic_seed_v2",
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
            "frequency_label_source": "vehbench_fem_cantilever_v1",
            "stress_label_source": "vehbench_fem_cantilever_v1",
            "displacement_label_source": "vehbench_fem_cantilever_v1",
            "power_label_source": "vehbench_electromech_surrogate_v4",
            "rng_seed": rng_seed,
            "element_count": int(config["element_count"]),
            "fem_assumptions": assumptions,
            "electromech_assumptions": assumptions,
        },
        "verifier_mapping": {
            "design_parameters": dict(candidate),
            "excitation_settings": dict(anchor["verifier_mapping"]["excitation_settings"]),
            "load_settings": {
                "load_type": "resistive",
                "load_resistance_ohm": candidate.get(
                    "load_resistance_ohm",
                    anchor["verifier_mapping"]["load_settings"].get("load_resistance_ohm"),
                ),
            },
            "material_parameters": dict(anchor["verifier_mapping"]["material_parameters"]),
            "observed_outputs": formatted_outputs,
            "missing_for_verifier": [],
        },
        "task_blueprints": build_blueprints(anchor, candidate, formatted_outputs),
    }


def main() -> None:
    config = load_config()
    anchors = ready_anchors()
    counts = allocate_counts(anchors, int(config["target_seed_count"]))

    rows = []
    policy_counter = Counter()
    split_counter = Counter()
    failures = 0
    for anchor in anchors:
        for sample_index in range(counts[anchor["seed_id"]]):
            row = build_seed(anchor, sample_index, config)
            if row is None:
                failures += 1
                continue
            rows.append(row)
            policy_counter[row["sample_policy"]] += 1
            split_counter[row["assigned_split"]["name"]] += 1

    write_jsonl(OUT_PATH, rows)
    lines = [
        "# Synthetic v4 Pilot 1k",
        "",
        f"- anchors: `{len(anchors)}`",
        f"- target_seed_count: `{config['target_seed_count']}`",
        f"- generated_seed_count: `{len(rows)}`",
        f"- dropped_seed_count: `{failures}`",
        f"- element_count: `{config['element_count']}`",
        "",
        "## Policy Counts",
        "",
    ]
    for key in sorted(policy_counter):
        lines.append(f"- {key}: `{policy_counter[key]}`")
    lines.extend(["", "## Split Counts", ""])
    for split_name in ("train", "val", "test-id", "test-ood"):
        lines.append(f"- {split_name}: `{split_counter.get(split_name, 0)}`")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(
        json.dumps(
            {
                "generated": len(rows),
                "dropped": failures,
                "policy_counts": policy_counter,
                "split_counts": split_counter,
                "output": str(OUT_PATH),
            },
            indent=2,
            default=dict,
        )
    )


if __name__ == "__main__":
    main()
