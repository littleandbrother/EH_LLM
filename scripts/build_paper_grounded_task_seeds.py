#!/usr/bin/env python3
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CURATED_GOLD_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "gold_records_curated.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
SEED_SCHEMA_PATH = PROJECT_ROOT / "schemas" / "vehbench_paper_grounded_task_seed_v1.json"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "paper_grounded_task_seed_report.md"


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


def infer_structure_class(record: dict) -> str:
    text = " ".join(
        str(part or "")
        for part in [
            record["metadata"].get("title"),
            record.get("evidence", {}).get("configuration", {}).get("quote"),
        ]
    ).lower()
    if "unimorph" in text:
        return "unimorph"
    if "bimorph" in text or "multimorph" in text:
        return "bimorph"
    return "other_piezo_cantilever"


def infer_material(record: dict, candidates: list[str]) -> str | None:
    text_parts = [
        record["metadata"].get("title"),
        record.get("evidence", {}).get("geometry", {}).get("piezo_thickness_um", {}).get("quote"),
        record.get("evidence", {}).get("geometry", {}).get("substrate_thickness_um", {}).get("quote"),
        record.get("evidence", {}).get("configuration", {}).get("quote"),
    ]
    text = " ".join(str(part or "") for part in text_parts).lower()
    for item in candidates:
        if item.lower() in text:
            return item
    return None


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


def build_variable_bounds(record: dict) -> dict:
    geometry = record.get("geometry", {})
    load = record.get("load", {})
    return {
        "beam_length_mm": bounded(geometry.get("length_mm"), "mm", 0.85, 1.15),
        "beam_width_mm": bounded(geometry.get("width_mm"), "mm", 0.85, 1.15),
        "substrate_thickness_um": bounded(geometry.get("substrate_thickness_um"), "um", 0.85, 1.15),
        "piezo_thickness_um": bounded(geometry.get("piezo_thickness_um"), "um", 0.85, 1.15),
        "tip_mass_g": bounded(geometry.get("tip_mass_g"), "g", 0.75, 1.25),
        "load_resistance_ohm": bounded(load.get("load_resistance_ohm"), "ohm", 0.1, 10.0),
    }


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


def build_verifier_mapping(record: dict) -> dict:
    geometry = record.get("geometry", {})
    excitation = record.get("excitation", {})
    load = record.get("load", {})
    output = record.get("output", {})
    material_parameters = {
        "structure_class": infer_structure_class(record),
        "piezo_material": infer_material(
            record,
            ["PZT", "PVDF", "AlN", "PMN-PT", "LiTaO3", "ScAlN", "ZnO"],
        ),
        "substrate_material": infer_material(
            record,
            ["silicon", "stainless steel", "steel", "aluminum", "copper", "bronze", "PEN", "PVC"],
        ),
    }
    mapping = {
        "design_parameters": {
            "beam_length_mm": geometry.get("length_mm"),
            "beam_width_mm": geometry.get("width_mm"),
            "substrate_thickness_um": geometry.get("substrate_thickness_um"),
            "piezo_thickness_um": geometry.get("piezo_thickness_um"),
            "tip_mass_g": geometry.get("tip_mass_g"),
            "load_resistance_ohm": load.get("load_resistance_ohm"),
        },
        "excitation_settings": {
            "excitation_type": "sinusoidal_base_excitation" if excitation.get("type") == "vibration" else "other",
            "frequency_hz": excitation.get("frequency_Hz"),
            "acceleration_g": excitation.get("acceleration_g"),
            "base_displacement_mm": excitation.get("displacement_mm"),
            "motion_source": excitation.get("motion_source"),
        },
        "load_settings": {
            "load_type": "resistive" if load.get("load_resistance_ohm") is not None else "unspecified",
            "load_resistance_ohm": load.get("load_resistance_ohm"),
        },
        "material_parameters": material_parameters,
        "observed_outputs": {
            "resonant_frequency_hz": output.get("resonant_frequency_Hz"),
            "load_power_w": output.get("output_power_W"),
            "open_circuit_voltage_v": output.get("open_circuit_voltage_V"),
            "short_circuit_current_a": output.get("short_circuit_current_A"),
            "bandwidth_hz": output.get("bandwidth_Hz"),
        },
    }
    missing = []
    if geometry.get("length_mm") is None:
        missing.append("beam_length_mm")
    if geometry.get("width_mm") is None:
        missing.append("beam_width_mm")
    if load.get("load_resistance_ohm") is None:
        missing.append("load_resistance_ohm")
    if excitation.get("frequency_Hz") is None:
        missing.append("excitation.frequency_hz")
    if excitation.get("acceleration_g") is None and excitation.get("displacement_mm") is None:
        missing.append("excitation.amplitude")
    if output.get("resonant_frequency_Hz") is None:
        missing.append("output.resonant_frequency_hz")
    mapping["missing_for_verifier"] = missing
    return mapping


def build_task_blueprints(record: dict, verifier_mapping: dict, seed_id: str) -> list[dict]:
    output = record.get("output", {})
    excitation = record.get("excitation", {})
    bounds = prune_none(build_variable_bounds(record))
    fixed_conditions = {
        "device_type": "piezoelectric_cantilever",
        "structure_class": verifier_mapping["material_parameters"]["structure_class"],
        "piezo_material": verifier_mapping["material_parameters"]["piezo_material"],
        "substrate_material": verifier_mapping["material_parameters"]["substrate_material"],
        "excitation_frequency_hz": excitation.get("frequency_Hz"),
        "acceleration_g": excitation.get("acceleration_g"),
        "target_resonant_frequency_hz": output.get("resonant_frequency_Hz"),
        "load_type": verifier_mapping["load_settings"]["load_type"],
        "notes": f"paper_grounded_seed:{seed_id}",
    }
    blueprints = []

    if output.get("resonant_frequency_Hz") is not None:
        blueprints.append(
            {
                "task_type": "frequency_matching",
                "variable_bounds": bounds,
                "fixed_conditions": fixed_conditions,
                "hard_constraints": {
                    "frequency_error_tolerance_pct": 5.0,
                    "require_linear_regime": True,
                    "geometry_notes": "paper-grounded around curated gold record",
                },
                "objective": {
                    "name": "match_resonant_frequency",
                    "direction": "target",
                    "target_value": output.get("resonant_frequency_Hz"),
                    "target_unit": "Hz",
                },
                "budget_hint": 24,
            }
        )

    if (
        output.get("output_power_W") is not None
        and verifier_mapping["load_settings"]["load_resistance_ohm"] is not None
        and (
            verifier_mapping["excitation_settings"]["acceleration_g"] is not None
            or verifier_mapping["excitation_settings"]["base_displacement_mm"] is not None
        )
    ):
        blueprints.append(
            {
                "task_type": "constrained_power_maximization",
                "variable_bounds": bounds,
                "fixed_conditions": fixed_conditions,
                "hard_constraints": {
                    "power_target_uw": round(output.get("output_power_W") * 1e6, 6),
                    "require_linear_regime": True,
                    "geometry_notes": "maximize feasible power around paper-grounded geometry regime",
                },
                "objective": {
                    "name": "maximize_feasible_power",
                    "direction": "maximize",
                    "target_value": round(output.get("output_power_W") * 1e6, 6),
                    "target_unit": "uW",
                },
                "budget_hint": 32,
            }
        )

    if not verifier_mapping["missing_for_verifier"]:
        blueprints.append(
            {
                "task_type": "feasibility_repair",
                "variable_bounds": bounds,
                "fixed_conditions": fixed_conditions,
                "hard_constraints": {
                    "require_linear_regime": True,
                    "geometry_notes": "repair near-feasible candidates around curated gold design point",
                },
                "objective": {
                    "name": "repair_feasibility",
                    "direction": "minimize",
                    "target_value": None,
                    "target_unit": None,
                },
                "budget_hint": 16,
            }
        )
    return blueprints


def build_seed(row: dict) -> dict:
    record = row["record"]
    paper_id = row["metadata"]["paper_id"]
    seed_id = f"pg_seed::{paper_id}"
    verifier_mapping = build_verifier_mapping(record)
    task_blueprints = build_task_blueprints(record, verifier_mapping, seed_id)
    mapping_status = "ready" if not verifier_mapping["missing_for_verifier"] else "partial"
    return {
        "schema_version": "vehbench_paper_grounded_task_seed_v1",
        "record_type": "paper_grounded_task_seed",
        "seed_id": seed_id,
        "source_record_id": paper_id,
        "source_paper_id": paper_id,
        "source_doi": row["metadata"].get("doi"),
        "mapping_status": mapping_status,
        "task_family_candidates": [bp["task_type"] for bp in task_blueprints],
        "verifier_mapping": verifier_mapping,
        "task_blueprints": task_blueprints,
    }


def main() -> None:
    curated_rows = load_jsonl(CURATED_GOLD_PATH)
    seeds = [build_seed(row) for row in curated_rows]

    verifier_rows = []
    for seed in seeds:
        verifier_rows.append(
            {
                "source_paper_id": seed["source_paper_id"],
                "mapping_status": seed["mapping_status"],
                "missing_for_verifier": seed["verifier_mapping"]["missing_for_verifier"],
                "verifier_mapping": seed["verifier_mapping"],
            }
        )

    write_jsonl(BENCHMARK_DIR / "paper_grounded_task_seeds.jsonl", seeds)
    write_jsonl(BENCHMARK_DIR / "verifier_mapping_records.jsonl", verifier_rows)

    mapping_counter = Counter(seed["mapping_status"] for seed in seeds)
    family_counter = Counter()
    structure_counter = Counter()
    for seed in seeds:
        family_counter.update(seed["task_family_candidates"])
        structure_counter.update([seed["verifier_mapping"]["material_parameters"]["structure_class"]])

    lines = [
        "# Paper-Grounded Task Seed Report",
        "",
        f"- curated gold inputs: `{len(curated_rows)}`",
        f"- ready verifier mappings: `{mapping_counter.get('ready', 0)}`",
        f"- partial verifier mappings: `{mapping_counter.get('partial', 0)}`",
        "",
        "## Task Family Coverage",
        "",
    ]
    for key, value in family_counter.most_common():
        lines.append(f"- `{key}`: `{value}`")
    lines.extend(["", "## Structure Class Coverage", ""])
    for key, value in structure_counter.most_common():
        lines.append(f"- `{key}`: `{value}`")
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "curated_gold": len(curated_rows),
                "seeds": len(seeds),
                "ready_mappings": mapping_counter.get("ready", 0),
                "partial_mappings": mapping_counter.get("partial", 0),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
