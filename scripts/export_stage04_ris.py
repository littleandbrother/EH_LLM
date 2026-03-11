#!/usr/bin/env python3
"""
Export the stage-04 core corpus JSONL to a Zotero-friendly RIS file.
"""

import argparse
import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INPUT = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.jsonl"
DEFAULT_OUTPUT = PROJECT_ROOT / "artifacts" / "reports" / "vehbench_stage04_core_corpus.ris"


def ris_type(publication_types: list[str]) -> str:
    joined = " ".join((publication_types or [])).lower()
    if "conference" in joined or "proceedings" in joined:
        return "CONF"
    return "JOUR"


def clean(value: str) -> str:
    return " ".join((value or "").replace("\r", " ").replace("\n", " ").split())


def load_records(path: Path) -> list[dict]:
    records = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                records.append(json.loads(line))
    return records


def write_ris(records: list[dict], output_path: Path):
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        for record in records:
            f.write(f"TY  - {ris_type(record.get('publication_types', []))}\n")
            f.write(f"TI  - {clean(record.get('title', ''))}\n")

            for author in record.get("authors", []) or []:
                name = clean(author.get("name", ""))
                if name:
                    f.write(f"AU  - {name}\n")

            venue = clean(record.get("venue", ""))
            if venue:
                f.write(f"JO  - {venue}\n")
                f.write(f"T2  - {venue}\n")

            year = record.get("year")
            if year:
                f.write(f"PY  - {year}\n")

            doi = clean(record.get("doi", ""))
            if doi:
                f.write(f"DO  - {doi}\n")

            url = clean(record.get("pdf_url", ""))
            if url:
                f.write(f"UR  - {url}\n")

            abstract = clean(record.get("abstract", ""))
            if abstract:
                f.write(f"AB  - {abstract}\n")

            source_id = clean(record.get("paper_id_oa") or record.get("paper_id_s2") or record.get("hash", ""))
            if source_id:
                f.write(f"ID  - {source_id}\n")

            f.write("ER  - \n\n")


def main():
    parser = argparse.ArgumentParser(description="Export stage4 core corpus to RIS")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    records = load_records(args.input)
    write_ris(records, args.output)
    print(f"Exported {len(records)} records -> {args.output}")


if __name__ == "__main__":
    main()
