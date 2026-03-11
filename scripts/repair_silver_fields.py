#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pipelines.extract import extract_schema as ex


RECORD_TIERS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "record_tiers.jsonl"
NORMALIZED_DIR = PROJECT_ROOT / "normalized_docs"
EXTRACTED_DIR = PROJECT_ROOT / "data_registry" / "extracted"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "silver_field_repairs.json"
REPAIR_LOG_PATH = PROJECT_ROOT / "runs" / "silver_field_repairs.log"
REPAIR_KEYWORDS = (
    "load",
    "resistance",
    "resistor",
    "matched",
    "optimal",
    "acceleration",
    "displacement",
    "amplitude",
    "excitation",
    "shaker",
    "vibration",
    "m/s",
    "mm",
    "um",
    "base motion",
    "base acceleration",
)
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "vehbench_extract_v1.yaml"


def load_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def log(message: str) -> None:
    line = f"{message}\n"
    print(message, flush=True)
    REPAIR_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REPAIR_LOG_PATH.open("a") as fh:
        fh.write(line)


def build_repair_context(doc: dict) -> str:
    parts = [
        "PAPER CONTEXT (metadata for reference only; do not output metadata):",
        f"paper_id: {doc.get('paper_id', '')}",
        f"doi: {doc.get('doi', '')}",
        f"title: {doc.get('title', '')}",
        f"year: {doc.get('year', '')}",
        f"journal: {doc.get('venue', '')}",
    ]

    for sec in doc.get("sections", []):
        heading = sec.get("heading", "")
        text = sec.get("text", "")
        text_l = f"{heading}\n{text}".lower()
        if any(keyword in text_l for keyword in REPAIR_KEYWORDS):
            parts.append(f"--- SECTION: {heading} ---\n{text}")

    for idx, tab in enumerate(doc.get("tables", []), 1):
        content = (tab.get("content") or "").strip()
        if content and any(keyword in content.lower() for keyword in REPAIR_KEYWORDS):
            parts.append(f"--- TABLE {idx} (Page {tab.get('page')}) ---\n{content}")

    for idx, fig in enumerate(doc.get("figures", []), 1):
        caption = (fig.get("caption") or "").strip()
        if caption and any(keyword in caption.lower() for keyword in REPAIR_KEYWORDS):
            parts.append(f"--- FIGURE CAPTION {idx} (Page {fig.get('page')}) ---\n{caption}")

    full_text = "\n\n".join(parts)
    if len(full_text) > 20000:
        full_text = full_text[:20000]
    return full_text


def build_patch_prompt(record: dict, blockers: list[str]) -> tuple[str, str]:
    needs_load = "missing_load" in blockers
    needs_amp = "missing_excitation_amplitude" in blockers
    current_snapshot = {
        "metadata": record.get("metadata"),
        "geometry": record.get("geometry"),
        "excitation": record.get("excitation"),
        "load": record.get("load"),
        "output": record.get("output"),
    }
    sys_prompt = """You are repairing an existing VEHBench extraction record.

Return JSON only with exactly this shape:
{
  "load": {
    "load_resistance_ohm": null,
    "evidence": {
      "load_resistance_ohm": {"quote": null, "section": null, "source_type": null}
    }
  },
  "excitation": {
    "acceleration_g": null,
    "displacement_mm": null,
    "evidence": {
      "acceleration_g": {"quote": null, "section": null, "source_type": null},
      "displacement_mm": {"quote": null, "section": null, "source_type": null}
    }
  }
}

Rules:
1. Only fill fields explicitly supported by the paper content. Otherwise leave null.
2. Do not change fields that are already populated in the current record.
3. For load_resistance_ohm, extract the external load or matched load resistance, not internal impedance.
4. For acceleration_g, convert acceleration to units of g.
5. For displacement_mm, convert displacement/base motion amplitude to units of mm.
6. Prefer the operating condition aligned with the current resonant frequency/output regime already in the record.
7. For every non-null field, provide field-level evidence with quote, section, and source_type.
8. source_type must be one of: section, table, figure_caption, abstract, title, unknown.
"""
    user_prompt = (
        "Repair only the missing benchmark fields in the current record.\n\n"
        f"CURRENT RECORD SNAPSHOT:\n{json.dumps(current_snapshot, ensure_ascii=False)}\n\n"
        f"MISSING TARGETS: load={needs_load}, excitation_amplitude={needs_amp}\n\n"
        f"{build_repair_context(record['_doc'])}"
    )
    return sys_prompt, user_prompt


def request_patch(client, record: dict, blockers: list[str]) -> dict:
    sys_prompt, user_prompt = build_patch_prompt(record, blockers)
    last_content = ""
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=ex.LLM_MODEL,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.0,
                max_tokens=1800,
                timeout=90,
            )
            last_content = response.choices[0].message.content.strip()
            return {
                "ok": True,
                "data": json.loads(ex.extract_json_block(last_content)),
                "raw_output": last_content,
            }
        except Exception as exc:
            if attempt < 2:
                time.sleep(5)
                continue
            return {
                "ok": False,
                "error": str(exc),
                "raw_output": last_content,
            }


def valid_evidence_leaf(leaf: dict | None) -> bool:
    if not isinstance(leaf, dict):
        return False
    return bool(leaf.get("quote") and leaf.get("section") and leaf.get("source_type"))


def apply_patch_to_record(record: dict, patch: dict, blockers: list[str]) -> list[str]:
    updates = []
    load = record.setdefault("load", {})
    evidence = record.setdefault("evidence", {})
    load_evidence = evidence.setdefault("load", {})
    excitation = record.setdefault("excitation", {})
    excitation_evidence = evidence.setdefault("excitation", {})

    if "missing_load" in blockers and load.get("load_resistance_ohm") is None:
        value = (((patch or {}).get("load") or {}).get("load_resistance_ohm"))
        ev = ((((patch or {}).get("load") or {}).get("evidence") or {}).get("load_resistance_ohm"))
        if value is not None and valid_evidence_leaf(ev):
            load["load_resistance_ohm"] = value
            load_evidence["load_resistance_ohm"] = ev
            updates.append("load.load_resistance_ohm")

    if "missing_excitation_amplitude" in blockers:
        patch_exc = (patch or {}).get("excitation") or {}
        patch_evidence = patch_exc.get("evidence") or {}
        for field in ("acceleration_g", "displacement_mm"):
            if excitation.get(field) is not None:
                continue
            value = patch_exc.get(field)
            ev = patch_evidence.get(field)
            if value is not None and valid_evidence_leaf(ev):
                excitation[field] = value
                excitation_evidence[field] = ev
                updates.append(f"excitation.{field}")
    return updates


def main() -> None:
    rows = load_rows(RECORD_TIERS_PATH)
    targets = [row for row in rows if row["tier"] == "silver" and row["promotion_blockers"]]
    client = ex.create_client()
    schema = ex.load_schema(SCHEMA_PATH)
    repair_reports = []
    REPAIR_LOG_PATH.write_text("")
    log(f"Starting targeted silver repair for {len(targets)} records")

    for idx, row in enumerate(targets, 1):
        paper_id = row["metadata"]["paper_id"]
        log(f"[{idx}/{len(targets)}] {paper_id} blockers={row['promotion_blockers']}")
        doc_path = NORMALIZED_DIR / f"{paper_id}.json"
        record_path = EXTRACTED_DIR / f"{paper_id}.json"
        if not doc_path.exists() or not record_path.exists():
            log("  missing_inputs")
            repair_reports.append({"paper_id": paper_id, "status": "missing_inputs"})
            continue

        doc = json.loads(doc_path.read_text())
        record = json.loads(record_path.read_text())
        record["_doc"] = doc
        blockers = row["promotion_blockers"]
        result = request_patch(client, record, blockers)
        if not result.get("ok"):
            log(f"  error: {result['error']}")
            repair_reports.append(
                {"paper_id": paper_id, "status": "error", "error": result["error"]}
            )
            continue

        updates = apply_patch_to_record(record, result["data"], blockers)
        errors, warnings = ex.validate_record(record, schema, doc)
        record.pop("_doc", None)
        if errors:
            log(f"  invalid_after_repair: {errors[:3]}")
            repair_reports.append(
                {
                    "paper_id": paper_id,
                    "status": "invalid_after_repair",
                    "updates": updates,
                    "errors": errors,
                    "warnings": warnings,
                }
            )
            continue
        record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2))
        log(f"  {'updated' if updates else 'no_change'} {updates}")
        repair_reports.append(
            {
                "paper_id": paper_id,
                "status": "updated" if updates else "no_change",
                "updates": updates,
                "warnings": warnings,
            }
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(repair_reports, ensure_ascii=False, indent=2))
    print(json.dumps({"targets": len(targets), "report": str(REPORT_PATH)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
