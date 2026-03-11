#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTRACTED_DIR = PROJECT_ROOT / "data_registry" / "extracted"
STAGE4_PATH = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus_paper_pdf_cleaned.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "vehbench_record_tiers.md"

PIEZO_CUES = [
    "piezo",
    "pzt",
    "pvdf",
    "aln",
    "unimorph",
    "bimorph",
]

DOMAIN_EXCLUDES = [
    "triboelectric",
    "magnetostrictive",
    "electromagnetic",
    "electrostatic",
    "thermoelectric",
    "pyroelectric",
]

REGIME_EXCLUDES = [
    "impact",
    "shock excitation",
    "shock-induced",
    "plucking",
    "pluck",
    "up-conversion",
    "up conversion",
    "up-converted",
    "frequency up-conversion",
    "frequency-excitation-up conversion",
    "nonlinear",
    "bistable",
    "bi-stable",
    "multistable",
    "autoparametric",
    "magnetic force",
    "magnetic coupling",
    "wind",
    "airflow",
    "human motion",
    "wearable",
    "wrist",
    "footstep",
]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def load_stage4_metadata() -> dict[str, dict]:
    records = {}
    for row in load_jsonl(STAGE4_PATH):
        paper_id = row.get("paper_id") or row.get("id") or row.get("hash")
        if paper_id:
            records[paper_id] = row
    return records


def load_extracted_records() -> list[dict]:
    records = []
    for path in sorted(EXTRACTED_DIR.glob("*.json")):
        data = json.loads(path.read_text())
        data["_path"] = str(path)
        records.append(data)
    return records


def combined_text(record: dict, stage4_meta: dict[str, dict]) -> str:
    metadata = record.get("metadata", {})
    paper_id = metadata.get("paper_id")
    source = stage4_meta.get(paper_id, {})
    parts = [
        metadata.get("title"),
        source.get("title"),
        source.get("abstract"),
    ]
    return " ".join(str(part or "") for part in parts).lower()


def count_populated(node: dict | None) -> int:
    if not isinstance(node, dict):
        return 0
    return sum(value is not None for value in node.values())


def has_any(node: dict | None, keys: list[str]) -> bool:
    if not isinstance(node, dict):
        return False
    return any(node.get(key) is not None for key in keys)


def scope_reasons(record: dict, stage4_meta: dict[str, dict]) -> list[str]:
    reasons = []
    text = combined_text(record, stage4_meta)
    configuration = record.get("configuration")
    excitation_type = (record.get("excitation") or {}).get("type")

    if configuration != "cantilever":
        reasons.append("non_cantilever")
    if excitation_type != "vibration":
        reasons.append("non_vibration_excitation")
    if not any(cue in text for cue in PIEZO_CUES):
        reasons.append("missing_piezo_signal")
    if any(term in text for term in DOMAIN_EXCLUDES):
        reasons.append("non_piezo_domain")
    if "array" in text or "arrays" in text:
        reasons.append("array_structure")
    if any(term in text for term in REGIME_EXCLUDES):
        reasons.append("excluded_regime")
    return reasons


def candidate_blockers(record: dict) -> list[str]:
    blockers = []
    geometry = record.get("geometry") or {}
    excitation = record.get("excitation") or {}
    output = record.get("output") or {}

    if count_populated(geometry) < 1:
        blockers.append("missing_geometry")
    if not has_any(excitation, ["frequency_Hz", "acceleration_g", "displacement_mm"]):
        blockers.append("missing_numeric_excitation")
    if not has_any(
        output,
        [
            "resonant_frequency_Hz",
            "output_power_W",
            "open_circuit_voltage_V",
            "short_circuit_current_A",
            "bandwidth_Hz",
        ],
    ):
        blockers.append("missing_output_metric")
    return blockers


def silver_blockers(record: dict) -> list[str]:
    blockers = []
    geometry = record.get("geometry") or {}
    excitation = record.get("excitation") or {}
    load = record.get("load") or {}
    output = record.get("output") or {}

    if count_populated(geometry) < 2:
        blockers.append("insufficient_geometry_detail")
    if excitation.get("frequency_Hz") is None:
        blockers.append("missing_excitation_frequency")
    if load.get("load_resistance_ohm") is None:
        blockers.append("missing_load")
    if output.get("resonant_frequency_Hz") is None:
        blockers.append("missing_resonant_frequency")
    if not has_any(output, ["output_power_W", "open_circuit_voltage_V", "short_circuit_current_A"]):
        blockers.append("missing_electrical_output")
    return blockers


def gold_blockers(record: dict) -> list[str]:
    blockers = []
    geometry = record.get("geometry") or {}
    excitation = record.get("excitation") or {}

    if geometry.get("length_mm") is None:
        blockers.append("missing_length")
    if not has_any(
        geometry,
        [
            "width_mm",
            "thickness_mm",
            "substrate_thickness_um",
            "piezo_thickness_um",
            "tip_mass_g",
        ],
    ):
        blockers.append("missing_secondary_geometry")
    if not has_any(excitation, ["acceleration_g", "displacement_mm"]):
        blockers.append("missing_excitation_amplitude")
    return blockers


def classify_record(record: dict, stage4_meta: dict[str, dict]) -> dict:
    scope = scope_reasons(record, stage4_meta)
    candidate = []
    silver = []
    gold = []

    if not scope:
        candidate = candidate_blockers(record)
        if not candidate:
            silver = silver_blockers(record)
            if not silver:
                gold = gold_blockers(record)

    if scope:
        tier = "raw_parsed"
        promotion_blockers = scope
    elif candidate:
        tier = "raw_parsed"
        promotion_blockers = candidate
    elif silver:
        tier = "candidate"
        promotion_blockers = silver
    elif gold:
        tier = "silver"
        promotion_blockers = gold
    else:
        tier = "gold"
        promotion_blockers = []

    summary = {
        "metadata": record.get("metadata", {}),
        "tier": tier,
        "scope_pass": not scope,
        "scope_reasons": scope,
        "candidate_blockers": candidate,
        "silver_blockers": silver,
        "gold_blockers": gold,
        "promotion_blockers": promotion_blockers,
        "record": record,
    }
    return summary


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def top_counter(items: list[str]) -> list[tuple[str, int]]:
    return Counter(items).most_common()


def build_report(
    rows: list[dict],
    candidate_rows: list[dict],
    silver_rows: list[dict],
    gold_rows: list[dict],
) -> str:
    scope_counter = Counter()
    candidate_counter = Counter()
    silver_counter = Counter()
    gold_counter = Counter()

    for row in rows:
        for item in row["scope_reasons"]:
            scope_counter[item] += 1
        if row["tier"] == "raw_parsed":
            for item in row["candidate_blockers"]:
                candidate_counter[item] += 1
        if row["tier"] == "candidate":
            for item in row["silver_blockers"]:
                silver_counter[item] += 1
        if row["tier"] == "silver":
            for item in row["gold_blockers"]:
                gold_counter[item] += 1

    lines = [
        "# VEHBench Record Tier Report",
        "",
        "This report is a pre-verifier stratification over valid extracted records.",
        "Final `gold` promotion still requires verifier back-substitution once verifier v1 exists.",
        "",
        "## Counts",
        "",
        f"- valid extracted records: `{len(rows)}`",
        f"- scope-passing records: `{sum(1 for row in rows if row['scope_pass'])}`",
        f"- candidate records: `{len(candidate_rows)}`",
        f"- silver records: `{len(silver_rows)}`",
        f"- gold records (pre-verifier): `{len(gold_rows)}`",
        "",
        "## Promotion Rules",
        "",
        "- `candidate`: in-scope piezoelectric cantilever vibration record with at least one geometry field, one numeric excitation field, and one output metric.",
        "- `silver`: candidate plus load resistance, excitation frequency, resonant frequency, one electrical output, and at least two geometry fields.",
        "- `gold`: silver plus cantilever-ready geometry (`length_mm` and one secondary geometry field) and an excitation amplitude (`acceleration_g` or `displacement_mm`).",
        "",
        "## Top Scope Exclusions",
        "",
    ]

    for reason, count in scope_counter.most_common():
        lines.append(f"- `{reason}`: `{count}`")

    lines.extend(
        [
            "",
            "## Top Candidate Blockers",
            "",
        ]
    )
    for reason, count in candidate_counter.most_common():
        lines.append(f"- `{reason}`: `{count}`")

    lines.extend(
        [
            "",
            "## Top Silver Blockers",
            "",
        ]
    )
    for reason, count in silver_counter.most_common():
        lines.append(f"- `{reason}`: `{count}`")

    lines.extend(
        [
            "",
            "## Top Gold Blockers",
            "",
        ]
    )
    for reason, count in gold_counter.most_common():
        lines.append(f"- `{reason}`: `{count}`")

    lines.extend(
        [
            "",
            "## Sample Gold Records",
            "",
        ]
    )
    for row in gold_rows[:20]:
        metadata = row["metadata"]
        lines.append(f"- `{metadata.get('paper_id')}`: {metadata.get('title')}")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-report", action="store_true")
    args = parser.parse_args()

    stage4_meta = load_stage4_metadata()
    records = load_extracted_records()
    rows = [classify_record(record, stage4_meta) for record in records]

    candidate_rows = [row for row in rows if row["tier"] in {"candidate", "silver", "gold"}]
    silver_rows = [row for row in rows if row["tier"] in {"silver", "gold"}]
    gold_rows = [row for row in rows if row["tier"] == "gold"]

    BENCHMARK_DIR.mkdir(parents=True, exist_ok=True)
    write_jsonl(BENCHMARK_DIR / "record_tiers.jsonl", rows)
    write_jsonl(BENCHMARK_DIR / "candidate_records.jsonl", candidate_rows)
    write_jsonl(BENCHMARK_DIR / "silver_records.jsonl", silver_rows)
    write_jsonl(BENCHMARK_DIR / "gold_records.jsonl", gold_rows)

    summary = {
        "valid_extracted": len(rows),
        "scope_passing": sum(1 for row in rows if row["scope_pass"]),
        "candidate": len(candidate_rows),
        "silver": len(silver_rows),
        "gold_pre_verifier": len(gold_rows),
    }
    (BENCHMARK_DIR / "tier_summary.json").write_text(json.dumps(summary, indent=2))

    if args.write_report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(build_report(rows, candidate_rows, silver_rows, gold_rows))

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
