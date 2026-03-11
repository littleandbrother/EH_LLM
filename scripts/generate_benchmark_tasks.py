#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter
from itertools import combinations, product
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from vehbench.verifier.v1.adapter import (
    VERIFIER_MODEL_FAMILY,
    VERIFIER_VERSION,
    VIOLATION_LABELS,
)
from vehbench.verifier.v1.calibration import load_frequency_profile
from vehbench.verifier.v1.evaluator import evaluate_request

SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "paper_grounded_task_seeds.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "benchmark_task_generation.md"
CALIBRATION_PROFILE = load_frequency_profile()
FREQUENCY_TOLERANCE_PCT = 2.0
FREQUENCY_SHIFT_MIN_PCT = 8.0
FREQUENCY_SHIFT_MAX_PCT = 30.0
POOL_RANDOM_SAMPLES = 24
REPAIR_DIFFICULTY_PROFILES = {
    "train": {
        "min_error_pct": 3.0,
        "max_error_pct": 7.5,
        "target_error_pct": 5.0,
    },
    "val": {
        "min_error_pct": 4.5,
        "max_error_pct": 9.5,
        "target_error_pct": 6.5,
    },
    "test-id": {
        "min_error_pct": 6.5,
        "max_error_pct": 14.0,
        "target_error_pct": 9.5,
    },
    "test-ood": {
        "min_error_pct": 5.5,
        "max_error_pct": 11.5,
        "target_error_pct": 8.0,
    },
}
REPAIR_FREQUENCY_TOLERANCE_BY_SPLIT = {
    "train": FREQUENCY_TOLERANCE_PCT,
    "val": FREQUENCY_TOLERANCE_PCT,
    "test-id": 1.0,
    "test-ood": FREQUENCY_TOLERANCE_PCT,
}


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


def hash_key(text: str) -> int:
    return int(hashlib.md5(text.encode()).hexdigest(), 16)


def compute_ood_tags(seeds: list[dict]) -> dict[str, list[str]]:
    freq_values = [
        seed["verifier_mapping"]["excitation_settings"]["frequency_hz"]
        for seed in seeds
        if seed["verifier_mapping"]["excitation_settings"]["frequency_hz"] is not None
    ]
    accel_values = [
        seed["verifier_mapping"]["excitation_settings"]["acceleration_g"]
        for seed in seeds
        if seed["verifier_mapping"]["excitation_settings"]["acceleration_g"] is not None
    ]
    load_values = [
        seed["verifier_mapping"]["load_settings"]["load_resistance_ohm"]
        for seed in seeds
        if seed["verifier_mapping"]["load_settings"]["load_resistance_ohm"] is not None
    ]
    length_values = [
        seed["verifier_mapping"]["design_parameters"]["beam_length_mm"]
        for seed in seeds
        if seed["verifier_mapping"]["design_parameters"]["beam_length_mm"] is not None
    ]
    material_counter = Counter(
        (
            seed["verifier_mapping"]["material_parameters"]["structure_class"],
            seed["verifier_mapping"]["material_parameters"]["piezo_material"],
        )
        for seed in seeds
    )

    def percentile_bounds(values: list[float]) -> tuple[float | None, float | None]:
        if len(values) < 4:
            return None, None
        ordered = sorted(values)
        low_idx = max(0, int(round(0.1 * (len(ordered) - 1))))
        high_idx = min(len(ordered) - 1, int(round(0.9 * (len(ordered) - 1))))
        return ordered[low_idx], ordered[high_idx]

    freq_lo, freq_hi = percentile_bounds(freq_values)
    accel_lo, accel_hi = percentile_bounds(accel_values)
    load_lo, load_hi = percentile_bounds(load_values)
    len_lo, len_hi = percentile_bounds(length_values)

    out = {}
    for seed in seeds:
        tags = []
        paper_id = seed["source_paper_id"]
        mapping = seed["verifier_mapping"]
        design = mapping["design_parameters"]
        excitation = mapping["excitation_settings"]
        load = mapping["load_settings"]
        material_key = (
            mapping["material_parameters"]["structure_class"],
            mapping["material_parameters"]["piezo_material"],
        )

        length = design.get("beam_length_mm")
        if length is not None and len_lo is not None and (length <= len_lo or length >= len_hi):
            tags.append("unseen_geometry_regime")

        freq = excitation.get("frequency_hz")
        accel = excitation.get("acceleration_g")
        if (
            (freq is not None and freq_lo is not None and (freq <= freq_lo or freq >= freq_hi))
            or (accel is not None and accel_lo is not None and (accel <= accel_lo or accel >= accel_hi))
        ):
            tags.append("unseen_excitation_range")

        if material_counter[material_key] <= 2:
            tags.append("unseen_material_combination")

        load_value = load.get("load_resistance_ohm")
        if load_value is not None and load_lo is not None and (load_value <= load_lo or load_value >= load_hi):
            tags.append("unseen_load_regime")

        out[paper_id] = sorted(set(tags))
    return out


def assign_seed_splits(seeds: list[dict]) -> dict[str, dict]:
    ood_tags = compute_ood_tags(seeds)
    total = len(seeds)
    ood_candidates = sorted(
        [seed for seed in seeds if ood_tags[seed["source_paper_id"]]],
        key=lambda seed: (-len(ood_tags[seed["source_paper_id"]]), seed["source_paper_id"]),
    )
    ood_target = min(len(ood_candidates), max(1, round(total * 0.18)))
    ood_ids = {seed["source_paper_id"] for seed in ood_candidates[:ood_target]}

    remaining = [seed for seed in seeds if seed["source_paper_id"] not in ood_ids]
    remaining = sorted(remaining, key=lambda seed: hash_key(seed["source_paper_id"]))
    val_target = max(1, round(total * 0.15))
    test_id_target = max(1, round(total * 0.15))

    split_map = {}
    for seed in seeds:
        paper_id = seed["source_paper_id"]
        if paper_id in ood_ids:
            split_map[paper_id] = {
                "name": "test-ood",
                "ood_tags": ood_tags[paper_id],
            }

    for idx, seed in enumerate(remaining):
        paper_id = seed["source_paper_id"]
        if idx < val_target:
            split_map[paper_id] = {"name": "val", "ood_tags": []}
        elif idx < val_target + test_id_target:
            split_map[paper_id] = {"name": "test-id", "ood_tags": []}
        else:
            split_map[paper_id] = {"name": "train", "ood_tags": []}
    return split_map


def metric_spec(task_type: str) -> dict:
    if task_type == "frequency_matching":
        return {
            "primary_metric": "constraint_satisfaction_rate",
            "secondary_metrics": [
                "frequency_error_hz",
                "frequency_error_pct",
                "invalid_proposal_rate",
                "wall_clock_s",
                "dollar_cost",
            ],
        }
    if task_type == "constrained_power_maximization":
        return {
            "primary_metric": "normalized_objective",
            "secondary_metrics": [
                "feasible_power_uw",
                "invalid_proposal_rate",
                "wall_clock_s",
                "dollar_cost",
            ],
        }
    return {
        "primary_metric": "repair_success_rate",
        "secondary_metrics": [
            "invalid_proposal_rate",
            "wall_clock_s",
            "dollar_cost",
        ],
    }


def clamp_candidate(variable_bounds: dict, candidate: dict) -> dict:
    clamped = {}
    for key, bounds in variable_bounds.items():
        value = candidate.get(key)
        if value is None:
            value = (bounds["min"] + bounds["max"]) / 2.0
        clamped[key] = max(bounds["min"], min(bounds["max"], float(value)))
    return clamped


def midpoint_candidate(variable_bounds: dict) -> dict:
    return {
        key: (bounds["min"] + bounds["max"]) / 2.0
        for key, bounds in variable_bounds.items()
    }


def count_bound_touches(variable_bounds: dict, candidate: dict) -> int:
    touches = 0
    for key, bounds in variable_bounds.items():
        value = float(candidate[key])
        if abs(value - bounds["min"]) < 1e-9 or abs(value - bounds["max"]) < 1e-9:
            touches += 1
    return touches


def frequency_error_pct(target_frequency_hz: float | None, observed_frequency_hz: float | None) -> float | None:
    if target_frequency_hz is None or observed_frequency_hz is None:
        return None
    target = float(target_frequency_hz)
    observed = float(observed_frequency_hz)
    return abs(observed - target) / max(abs(target), 1e-9) * 100.0


def build_request_from_seed(
    seed: dict,
    candidate: dict,
    task_type: str,
    target_frequency_hz: float | None = None,
    power_target_uw: float | None = None,
) -> dict:
    mapping = seed["verifier_mapping"]
    candidate = dict(candidate)
    load_value = candidate.get("load_resistance_ohm", mapping["load_settings"].get("load_resistance_ohm"))
    return {
        "task_id": f"{seed['source_paper_id']}::{task_type}",
        "candidate_id": f"{seed['source_paper_id']}::{task_type}::generator",
        "design_parameters": candidate,
        "material_parameters": dict(mapping["material_parameters"]),
        "excitation_settings": dict(mapping["excitation_settings"]),
        "load_settings": {
            "load_type": "resistive" if load_value is not None else mapping["load_settings"].get("load_type"),
            "load_resistance_ohm": load_value,
        },
        "constraint_context": {
            "target_resonant_frequency_hz": target_frequency_hz,
            "stress_limit_mpa": None,
            "displacement_limit_mm": None,
            "power_target_uw": power_target_uw,
        },
    }


def evaluate_seed_candidate(
    seed: dict,
    variable_bounds: dict,
    candidate: dict,
    task_type: str,
    target_frequency_hz: float | None = None,
    power_target_uw: float | None = None,
    frequency_tolerance_pct: float = FREQUENCY_TOLERANCE_PCT,
) -> dict:
    candidate = clamp_candidate(variable_bounds, candidate)
    request = build_request_from_seed(
        seed,
        candidate,
        task_type=task_type,
        target_frequency_hz=target_frequency_hz,
        power_target_uw=power_target_uw,
    )
    temp_task = {
        "task_type": task_type,
        "hard_constraints": {
            "frequency_error_tolerance_pct": frequency_tolerance_pct,
        },
    }
    return evaluate_request(
        request,
        task=temp_task,
        apply_frequency_calibration=True,
        calibration_profile=CALIBRATION_PROFILE,
        use_task_anchors=False,
    )


def sample_candidate_pool(seed: dict, variable_bounds: dict) -> list[dict]:
    base = clamp_candidate(variable_bounds, seed["verifier_mapping"]["design_parameters"])
    mid = midpoint_candidate(variable_bounds)
    pool = [base, mid]

    for key, bounds in variable_bounds.items():
        for endpoint in (bounds["min"], bounds["max"]):
            candidate = dict(mid)
            candidate[key] = endpoint
            pool.append(clamp_candidate(variable_bounds, candidate))

    seed_int = hash_key(seed["source_paper_id"]) % (2**32)
    rng = random.Random(seed_int)
    keys = list(variable_bounds.keys())
    sample_count = POOL_RANDOM_SAMPLES
    strata = {key: list(range(sample_count)) for key in keys}
    for key in keys:
        rng.shuffle(strata[key])
    for row in range(sample_count):
        candidate = {}
        for key in keys:
            slot = strata[key][row]
            fraction = (slot + rng.random()) / sample_count
            bounds = variable_bounds[key]
            if key == "load_resistance_ohm" and bounds["min"] > 0:
                low = bounds["min"]
                high = bounds["max"]
                value = low * ((high / low) ** fraction)
            else:
                value = bounds["min"] + fraction * (bounds["max"] - bounds["min"])
            candidate[key] = value
        pool.append(clamp_candidate(variable_bounds, candidate))

    dedup = {}
    for candidate in pool:
        key = tuple(round(candidate[name], 8) for name in keys)
        dedup[key] = candidate
    return list(dedup.values())


def select_frequency_design(seed: dict, blueprint: dict) -> dict | None:
    variable_bounds = blueprint["variable_bounds"]
    observed_target = float(blueprint["objective"]["target_value"])
    midpoint = midpoint_candidate(variable_bounds)
    midpoint_response = evaluate_seed_candidate(
        seed,
        variable_bounds,
        midpoint,
        task_type="frequency_matching",
        target_frequency_hz=observed_target,
    )["response"]
    midpoint_frequency = midpoint_response["outputs"]["resonant_frequency_hz"]
    if midpoint_frequency is None:
        return None

    pool = sample_candidate_pool(seed, variable_bounds)
    choices = []
    for candidate in pool:
        response = evaluate_seed_candidate(
            seed,
            variable_bounds,
            candidate,
            task_type="frequency_matching",
            target_frequency_hz=observed_target,
        )["response"]
        frequency = response["outputs"]["resonant_frequency_hz"]
        if frequency is None:
            continue
        shift_pct = abs(frequency - observed_target) / max(abs(observed_target), 1e-9) * 100.0
        midpoint_gap_pct = abs(frequency - midpoint_frequency) / max(abs(frequency), 1e-9) * 100.0
        if shift_pct < FREQUENCY_SHIFT_MIN_PCT or shift_pct > FREQUENCY_SHIFT_MAX_PCT:
            continue
        if midpoint_gap_pct <= FREQUENCY_TOLERANCE_PCT:
            continue
        choices.append(
            {
                "candidate": candidate,
                "target_frequency_hz": round(frequency, 6),
                "shift_pct": round(shift_pct, 6),
                "midpoint_gap_pct": round(midpoint_gap_pct, 6),
                "bound_touches": count_bound_touches(variable_bounds, candidate),
            }
        )

    if not choices:
        return None

    choices.sort(
        key=lambda item: (
            item["bound_touches"],
            -item["midpoint_gap_pct"],
            abs(item["shift_pct"] - 14.0),
        )
    )
    return {
        **choices[0],
        "midpoint_frequency_hz": round(midpoint_frequency, 6),
        "midpoint_feasible_to_original": bool(midpoint_response["is_feasible"]),
    }


def select_repair_initial_candidate(
    seed: dict,
    blueprint: dict,
    reference_solution: dict,
    target_frequency_hz: float,
    split_name: str,
    frequency_tolerance_pct: float,
) -> dict | None:
    variable_bounds = blueprint["variable_bounds"]
    pool = sample_candidate_pool(seed, variable_bounds)
    targeted = []
    for key, bounds in variable_bounds.items():
        for endpoint in (bounds["min"], bounds["max"]):
            candidate = dict(reference_solution)
            candidate[key] = endpoint
            targeted.append(clamp_candidate(variable_bounds, candidate))
        reference_value = reference_solution.get(key)
        if reference_value is None:
            continue
        for factor in (0.82, 0.9, 1.1, 1.18):
            candidate = dict(reference_solution)
            candidate[key] = float(reference_value) * factor
            targeted.append(clamp_candidate(variable_bounds, candidate))
    keys = list(variable_bounds)
    for key_a, key_b in combinations(keys, 2):
        bounds_a = variable_bounds[key_a]
        bounds_b = variable_bounds[key_b]
        for endpoint_a, endpoint_b in product(
            (bounds_a["min"], bounds_a["max"]),
            (bounds_b["min"], bounds_b["max"]),
        ):
            candidate = dict(reference_solution)
            candidate[key_a] = endpoint_a
            candidate[key_b] = endpoint_b
            targeted.append(clamp_candidate(variable_bounds, candidate))
    pool.extend(targeted)

    profile = REPAIR_DIFFICULTY_PROFILES.get(split_name, REPAIR_DIFFICULTY_PROFILES["train"])
    preferred: list[dict] = []
    fallback: list[dict] = []
    for candidate in pool:
        if candidate == reference_solution:
            continue
        response = evaluate_seed_candidate(
            seed,
            variable_bounds,
            candidate,
            task_type="feasibility_repair",
            target_frequency_hz=target_frequency_hz,
            frequency_tolerance_pct=frequency_tolerance_pct,
        )["response"]
        if response["is_feasible"]:
            continue
        violations = response.get("violations") or []
        error_pct = frequency_error_pct(
            target_frequency_hz,
            response["outputs"]["resonant_frequency_hz"],
        )
        only_frequency = bool(violations) and all(item.startswith("frequency_") for item in violations)
        in_band = (
            error_pct is not None
            and profile["min_error_pct"] <= error_pct <= profile["max_error_pct"]
        )
        record = {
            "candidate": candidate,
            "violations": violations,
            "normalized_objective": response.get("normalized_objective"),
            "frequency_hz": response["outputs"]["resonant_frequency_hz"],
            "frequency_error_pct": None if error_pct is None else round(error_pct, 6),
            "bound_touches": count_bound_touches(variable_bounds, candidate),
            "selection_key": (
                1 if in_band else 0,
                1 if len(violations) == 1 and only_frequency else 0,
                1 if only_frequency else 0,
                0.0 if error_pct is None else -abs(error_pct - profile["target_error_pct"]),
                0.0 if error_pct is None else error_pct,
                -count_bound_touches(variable_bounds, candidate),
            ),
        }
        if in_band:
            preferred.append(record)
        fallback.append(record)

    choices = preferred or fallback
    if not choices:
        return None
    choices.sort(key=lambda item: item["selection_key"], reverse=True)
    return choices[0]


def tune_seed_blueprints(seed: dict, split: dict) -> dict:
    blueprints = [dict(blueprint) for blueprint in seed["task_blueprints"]]
    by_type = {blueprint["task_type"]: blueprint for blueprint in blueprints}
    difficulty_audit = {}

    frequency_blueprint = by_type.get("frequency_matching")
    if frequency_blueprint is not None:
        frequency_blueprint["hard_constraints"] = {
            **frequency_blueprint["hard_constraints"],
            "frequency_error_tolerance_pct": FREQUENCY_TOLERANCE_PCT,
        }
        selected = select_frequency_design(seed, frequency_blueprint)
        if selected is not None:
            frequency_blueprint["fixed_conditions"] = {
                **frequency_blueprint["fixed_conditions"],
                "target_resonant_frequency_hz": selected["target_frequency_hz"],
            }
            frequency_blueprint["objective"] = {
                **frequency_blueprint["objective"],
                "target_value": selected["target_frequency_hz"],
            }
            frequency_blueprint["reference_solution_override"] = selected["candidate"]
            difficulty_audit["frequency_matching"] = {
                "status": "challenged",
                **{key: value for key, value in selected.items() if key != "candidate"},
            }
        else:
            difficulty_audit["frequency_matching"] = {"status": "fallback_to_original_target"}

    repair_blueprint = by_type.get("feasibility_repair")
    if repair_blueprint is not None:
        repair_frequency_tolerance_pct = REPAIR_FREQUENCY_TOLERANCE_BY_SPLIT[split["name"]]
        repair_blueprint["hard_constraints"] = {
            **repair_blueprint["hard_constraints"],
            "frequency_error_tolerance_pct": repair_frequency_tolerance_pct,
        }
        reference_solution = (
            frequency_blueprint.get("reference_solution_override")
            if frequency_blueprint is not None and frequency_blueprint.get("reference_solution_override")
            else seed["verifier_mapping"]["design_parameters"]
        )
        target_frequency_hz = (
            frequency_blueprint["objective"]["target_value"]
            if frequency_blueprint is not None
            else seed["verifier_mapping"]["observed_outputs"]["resonant_frequency_hz"]
        )
        repair_blueprint["fixed_conditions"] = {
            **repair_blueprint["fixed_conditions"],
            "target_resonant_frequency_hz": target_frequency_hz,
        }
        repair_blueprint["reference_solution_override"] = dict(reference_solution)
        selected = select_repair_initial_candidate(
            seed,
            repair_blueprint,
            reference_solution=dict(reference_solution),
            target_frequency_hz=float(target_frequency_hz),
            split_name=split["name"],
            frequency_tolerance_pct=repair_frequency_tolerance_pct,
        )
        if selected is not None:
            repair_blueprint["initial_candidate_override"] = selected["candidate"]
            difficulty_audit["feasibility_repair"] = {
                "status": "challenged",
                "violations": selected["violations"],
                "normalized_objective": selected["normalized_objective"],
                "frequency_hz": selected["frequency_hz"],
                "frequency_error_pct": selected["frequency_error_pct"],
                "bound_touches": selected["bound_touches"],
                "target_split": split["name"],
            }
        else:
            difficulty_audit["feasibility_repair"] = {"status": "dropped_no_infeasible_start"}
            blueprints = [bp for bp in blueprints if bp["task_type"] != "feasibility_repair"]

    return {
        **seed,
        "task_blueprints": blueprints,
        "difficulty_audit": difficulty_audit,
    }


def best_known_score(seed: dict, task_type: str, objective: dict) -> float | None:
    outputs = seed["verifier_mapping"]["observed_outputs"]
    if task_type == "constrained_power_maximization":
        power = outputs.get("load_power_w")
        return None if power is None else round(power * 1e6, 6)
    if task_type == "frequency_matching":
        return objective.get("target_value")
    return None


def build_task(seed: dict, blueprint: dict, split: dict) -> dict:
    paper_id = seed["source_paper_id"]
    task_type = blueprint["task_type"]
    task_id = f"{paper_id}::{task_type}"
    reference_solution = dict(
        blueprint.get("reference_solution_override")
        or seed["verifier_mapping"]["design_parameters"]
    )
    reference_solution["best_known_score"] = best_known_score(seed, task_type, blueprint["objective"])

    task = {
        "schema_version": "vehbench_task_v1",
        "record_type": "benchmark_task",
        "task_id": task_id,
        "source_type": "paper_grounded",
        "task_type": task_type,
        "source_refs": {
            "source_paper_uid": paper_id,
            "source_record_id": seed["seed_id"],
            "generator_name": "generate_benchmark_tasks_v1",
            "generator_seed": None,
        },
        "variable_bounds": blueprint["variable_bounds"],
        "fixed_conditions": blueprint["fixed_conditions"],
        "hard_constraints": blueprint["hard_constraints"],
        "objective": {
            **blueprint["objective"],
            "normalization_reference": paper_id,
        },
        "verifier": {
            "verifier_version": VERIFIER_VERSION,
            "model_family": VERIFIER_MODEL_FAMILY,
            "deterministic": True,
            "violation_labels": VIOLATION_LABELS,
        },
        "budget": {
            "max_queries": blueprint["budget_hint"],
            "max_wall_clock_s": 900,
            "max_tokens": 120000 if task_type == "feasibility_repair" else 60000,
        },
        "metric_spec": metric_spec(task_type),
        "split": split,
        "initial_candidate": blueprint.get("initial_candidate_override") if task_type == "feasibility_repair" else None,
        "reference_solution": reference_solution,
        "notes": f"paper_grounded_from_curated_gold::{paper_id}",
    }
    return task


def main() -> None:
    raw_seeds = load_jsonl(SEEDS_PATH)
    split_map = assign_seed_splits(raw_seeds)
    seeds = [tune_seed_blueprints(seed, split_map[seed["source_paper_id"]]) for seed in raw_seeds]

    tasks = []
    by_type = {"frequency_matching": [], "constrained_power_maximization": [], "feasibility_repair": []}
    by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}

    for seed in seeds:
        split = split_map[seed["source_paper_id"]]
        for blueprint in seed["task_blueprints"]:
            task = build_task(seed, blueprint, split)
            tasks.append(task)
            by_type[task["task_type"]].append(task)
            by_split[task["split"]["name"]].append(task)

    write_jsonl(BENCHMARK_DIR / "tasks_paper_grounded.jsonl", tasks)
    write_jsonl(BENCHMARK_DIR / "tasks_frequency_matching.jsonl", by_type["frequency_matching"])
    write_jsonl(BENCHMARK_DIR / "tasks_constrained_power_maximization.jsonl", by_type["constrained_power_maximization"])
    write_jsonl(BENCHMARK_DIR / "tasks_feasibility_repair.jsonl", by_type["feasibility_repair"])
    write_jsonl(BENCHMARK_DIR / "tasks_train.jsonl", by_split["train"])
    write_jsonl(BENCHMARK_DIR / "tasks_val.jsonl", by_split["val"])
    write_jsonl(BENCHMARK_DIR / "tasks_test_id.jsonl", by_split["test-id"])
    write_jsonl(BENCHMARK_DIR / "tasks_test_ood.jsonl", by_split["test-ood"])

    lines = [
        "# Benchmark Task Generation",
        "",
        f"- seeds input: `{len(seeds)}`",
        f"- total paper-grounded tasks: `{len(tasks)}`",
        f"- frequency_matching: `{len(by_type['frequency_matching'])}`",
        f"- constrained_power_maximization: `{len(by_type['constrained_power_maximization'])}`",
        f"- feasibility_repair: `{len(by_type['feasibility_repair'])}`",
        "",
        "## Split Counts",
        "",
        f"- train: `{len(by_split['train'])}`",
        f"- val: `{len(by_split['val'])}`",
        f"- test-id: `{len(by_split['test-id'])}`",
        f"- test-ood: `{len(by_split['test-ood'])}`",
        "",
        "## Difficulty Audit",
        "",
    ]
    freq_challenged = sum(
        1
        for seed in seeds
        if (seed.get("difficulty_audit", {}).get("frequency_matching", {}) or {}).get("status") == "challenged"
    )
    repair_challenged = sum(
        1
        for seed in seeds
        if (seed.get("difficulty_audit", {}).get("feasibility_repair", {}) or {}).get("status") == "challenged"
    )
    repair_dropped = sum(
        1
        for seed in seeds
        if (seed.get("difficulty_audit", {}).get("feasibility_repair", {}) or {}).get("status") == "dropped_no_infeasible_start"
    )
    repair_errors_by_split = {"train": [], "val": [], "test-id": [], "test-ood": []}
    for seed in seeds:
        split_name = split_map[seed["source_paper_id"]]["name"]
        audit = (seed.get("difficulty_audit", {}).get("feasibility_repair", {}) or {})
        if audit.get("status") != "challenged":
            continue
        error_pct = audit.get("frequency_error_pct")
        if error_pct is not None:
            repair_errors_by_split[split_name].append(float(error_pct))
    lines.extend(
        [
            f"- frequency tasks retargeted: `{freq_challenged}`",
            f"- repair tasks with audited infeasible starts: `{repair_challenged}`",
            f"- repair tasks dropped for triviality: `{repair_dropped}`",
            "",
            "## Repair Initial Difficulty",
            "",
        ]
    )
    for split_name in ("train", "val", "test-id", "test-ood"):
        errors = repair_errors_by_split[split_name]
        profile = REPAIR_DIFFICULTY_PROFILES[split_name]
        if not errors:
            lines.append(f"- {split_name}: `0` tasks")
            continue
        lines.append(
            "- "
            + split_name
            + ": "
            + f"`{len(errors)}` tasks, avg error `{sum(errors) / len(errors):.3f}%`, "
            + f"range `{min(errors):.3f}%`-`{max(errors):.3f}%`, "
            + f"profile `{profile['min_error_pct']:.1f}%`-`{profile['max_error_pct']:.1f}%`, "
            + f"tolerance `{REPAIR_FREQUENCY_TOLERANCE_BY_SPLIT[split_name]:.1f}%`"
        )
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "seeds": len(seeds),
        "tasks": len(tasks),
        "frequency_matching": len(by_type["frequency_matching"]),
        "constrained_power_maximization": len(by_type["constrained_power_maximization"]),
        "feasibility_repair": len(by_type["feasibility_repair"]),
    }, indent=2))


if __name__ == "__main__":
    main()
