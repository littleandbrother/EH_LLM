#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUDIT_CONFIG = PROJECT_ROOT / "configs" / "gold_scope_audit_v1.json"
RECORD_TIERS_PATH = PROJECT_ROOT / "data_registry" / "benchmark" / "record_tiers.jsonl"
BENCHMARK_DIR = PROJECT_ROOT / "data_registry" / "benchmark"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "gold_scope_audit.md"


def load_json(path: Path) -> dict:
    return json.loads(path.read_text())


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


def main() -> None:
    config = load_json(AUDIT_CONFIG)
    excludes = config.get("exclude", {})
    rows = [row for row in load_jsonl(RECORD_TIERS_PATH) if row.get("tier") == "gold"]

    audit_rows = []
    curated_rows = []
    excluded_rows = []

    for row in rows:
        paper_id = row["metadata"]["paper_id"]
        reason = excludes.get(paper_id)
        audit_row = {
            "metadata": row["metadata"],
            "decision": "exclude" if reason else "keep",
            "reason": reason,
            "record": row["record"],
        }
        audit_rows.append(audit_row)
        if reason:
            excluded_rows.append(audit_row)
        else:
            curated_rows.append(audit_row)

    write_jsonl(BENCHMARK_DIR / "gold_scope_audit.jsonl", audit_rows)
    write_jsonl(BENCHMARK_DIR / "gold_scope_excluded.jsonl", excluded_rows)
    write_jsonl(BENCHMARK_DIR / "gold_records_curated.jsonl", curated_rows)

    lines = [
        "# Gold Scope Audit",
        "",
        "Manual scope audit over pre-verifier gold records.",
        "",
        f"- pre-verifier gold input: `{len(rows)}`",
        f"- kept after scope audit: `{len(curated_rows)}`",
        f"- excluded after scope audit: `{len(excluded_rows)}`",
        "",
        "## Excluded Records",
        "",
    ]
    for row in excluded_rows:
        lines.append(
            f"- `{row['metadata']['paper_id']}`: {row['metadata']['title']} "
            f"(`{row['reason']}`)"
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines) + "\n")

    print(
        json.dumps(
            {
                "gold_input": len(rows),
                "gold_curated": len(curated_rows),
                "gold_excluded": len(excluded_rows),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
