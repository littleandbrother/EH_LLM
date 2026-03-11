#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = PROJECT_ROOT / "configs" / "power_condition_audit_v1.json"
SEEDS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "paper_grounded_task_seeds.jsonl"
EXTRACTED_DIR = PROJECT_ROOT / "data_registry" / "extracted"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "power_condition_audit.md"


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


def evidence_summary(record: dict) -> dict:
    evidence = record.get("evidence") or {}
    excitation = evidence.get("excitation") or {}
    output = evidence.get("output") or {}
    return {
        "load": (evidence.get("load") or {}).get("load_resistance_ohm") or {},
        "frequency": excitation.get("frequency_Hz") or {},
        "acceleration": excitation.get("acceleration_g") or {},
        "power": output.get("output_power_W") or {},
    }


def auto_reason(title: str, summary: dict) -> str:
    load = summary["load"]
    frequency = summary["frequency"]
    acceleration = summary["acceleration"]
    power = summary["power"]
    sections = [
        load.get("section"),
        frequency.get("section"),
        acceleration.get("section"),
        power.get("section"),
    ]
    normalized_sections = {value for value in sections if value}

    if acceleration.get("quote") is None:
        return "missing_acceleration_evidence"

    load_quote = (load.get("quote") or "").lower()
    title_lower = title.lower()
    power_section = (power.get("section") or "").lower()
    freq_section = (frequency.get("section") or "").lower()
    accel_section = (acceleration.get("section") or "").lower()

    if re.search(r"\b(theoretical|theory|simulation|simulated)\b", load_quote):
        return "theoretical_or_simulated_load_not_condition_locked"
    if re.search(r"\bcomparison|survey|review\b", power_section):
        return "comparison_table_or_review_context"
    if "table" in power_section and (power_section != freq_section or power_section != accel_section):
        return "table_condition_not_fully_locked"
    if "simulation" in title_lower or "modeling" in title_lower:
        return "modeling_or_simulation_dominant_context"
    if len(normalized_sections) > 1:
        return "mixed_condition_sections"
    if re.search(r"\b(optimal|optimum|best matching|matched load)\b", load_quote):
        return "optimal_load_reported_without_strict_condition_lock"
    return "not_promoted_in_conservative_power_audit"


def main() -> None:
    config = json.loads(CONFIG_PATH.read_text())
    manual_keep = config["keep"]

    seeds = [row for row in load_jsonl(SEEDS_PATH) if row["mapping_status"] == "ready"]
    audit_rows = []
    subset_rows = []
    kept_ids = []

    for seed in seeds:
        paper_id = seed["source_paper_id"]
        record = json.loads((EXTRACTED_DIR / f"{paper_id}.json").read_text())
        summary = evidence_summary(record)
        sections = {
            "load": summary["load"].get("section"),
            "frequency": summary["frequency"].get("section"),
            "acceleration": summary["acceleration"].get("section"),
            "power": summary["power"].get("section"),
        }

        if paper_id in manual_keep:
            decision = "keep"
            reason = manual_keep[paper_id]
            kept_ids.append(paper_id)
            subset_rows.append(seed)
        else:
            decision = "reject"
            reason = auto_reason(record["metadata"]["title"], summary)

        audit_rows.append(
            {
                "paper_id": paper_id,
                "title": record["metadata"]["title"],
                "decision": decision,
                "reason": reason,
                "sections": sections,
                "evidence": summary,
            }
        )

    write_jsonl(BENCHMARK_DIR / "power_condition_audit.jsonl", audit_rows)
    write_jsonl(BENCHMARK_DIR / "power_gold_subset_seeds.jsonl", subset_rows)
    (BENCHMARK_DIR / "power_gold_subset_papers.json").write_text(
        json.dumps({"papers": kept_ids}, indent=2)
    )

    reject_counts: dict[str, int] = {}
    for row in audit_rows:
        if row["decision"] == "reject":
            reject_counts[row["reason"]] = reject_counts.get(row["reason"], 0) + 1

    lines = [
        "# Power Condition Audit",
        "",
        "This audit keeps only records where `power / load / excitation frequency / acceleration` are judged to refer to the same operating condition with conservative evidence rules.",
        "",
        f"- ready mappings audited: `{len(audit_rows)}`",
        f"- kept in power-gold subset: `{len(subset_rows)}`",
        f"- rejected: `{len(audit_rows) - len(subset_rows)}`",
        "",
        "## Rejection Reasons",
        "",
    ]
    for reason, count in sorted(reject_counts.items()):
        lines.append(f"- `{reason}`: `{count}`")
    lines.extend(
        [
            "",
            "## Kept Papers",
            "",
        ]
    )
    for row in audit_rows:
        if row["decision"] == "keep":
            lines.append(f"- `{row['paper_id']}`: {row['reason']}")
    REPORT_PATH.write_text("\n".join(lines) + "\n")
    print(json.dumps({
        "audited": len(audit_rows),
        "kept": len(subset_rows),
        "rejected": len(audit_rows) - len(subset_rows),
    }, indent=2))


if __name__ == "__main__":
    main()
