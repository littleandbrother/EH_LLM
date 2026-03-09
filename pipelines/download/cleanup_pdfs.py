#!/usr/bin/env python3
"""
Match local PDFs into the registry raw directory and update pdf_path values.

This is primarily for importing PDFs exported from Zotero or other local
collections after metadata filtering is complete.
"""

import argparse
import hashlib
import json
import re
import shutil
from difflib import SequenceMatcher
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "pdf"
DEFAULT_DEST_DIR = PROJECT_ROOT / "data_registry" / "raw"
INPUT_CANDIDATES = [
    PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.jsonl",
    PROJECT_ROOT / "data_registry" / "papers_filtered.jsonl",
    PROJECT_ROOT / "data_registry" / "papers.jsonl",
]

DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:a-z0-9]+", re.IGNORECASE)
YEAR_RE = re.compile(r"(19|20)\d{2}")


def normalize_doi(doi: str) -> str:
    value = (doi or "").strip()
    if not value:
        return ""
    value = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", value,
                   flags=re.IGNORECASE)
    return value.lower()


def normalize_safe_doi_token(value: str) -> str:
    """Normalize a DOI-like filename token such as 10_1016_j_xxx_2020_123456."""
    value = (value or "").strip().lower()
    if not value:
        return ""
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def normalize_title(title: str) -> str:
    value = (title or "").strip().lower()
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"[^\w\s]", "", value)
    return value.strip()


def detect_input_jsonl(explicit_path: str | None) -> Path:
    if explicit_path:
        return Path(explicit_path)
    for candidate in INPUT_CANDIDATES:
        if candidate.exists():
            return candidate
    return INPUT_CANDIDATES[0]


def make_paper_id(paper: dict) -> str:
    doi = normalize_doi(paper.get("doi", ""))
    if doi:
        safe = re.sub(r"[^a-zA-Z0-9]", "_", doi)
        return safe[:80]
    hash_value = paper.get("hash", "")
    if not hash_value:
        key = f"{paper.get('title', '')}|{paper.get('year', '')}"
        hash_value = hashlib.md5(key.encode("utf-8")).hexdigest()[:12]
    return f"noid_{hash_value}"


def extract_filename_title(stem: str) -> str:
    parts = stem.split(" - ")
    if len(parts) >= 3:
        return " - ".join(parts[2:])
    return stem


def score_title_match(pdf_title: str, paper_title: str) -> float:
    if not pdf_title or not paper_title:
        return 0.0
    if pdf_title == paper_title:
        return 1.0
    if pdf_title in paper_title or paper_title in pdf_title:
        overlap = min(len(pdf_title), len(paper_title)) / max(len(pdf_title), len(paper_title))
        return 0.92 + 0.08 * overlap
    return SequenceMatcher(None, pdf_title[:200], paper_title[:200]).ratio()


def load_papers(input_path: Path) -> list[dict]:
    papers = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            paper = json.loads(line)
            paper["_doi_norm"] = normalize_doi(paper.get("doi", ""))
            paper["_doi_safe"] = normalize_safe_doi_token(paper["_doi_norm"])
            paper["_title_norm"] = normalize_title(paper.get("title", ""))
            papers.append(paper)
    return papers


def build_doi_index(papers: list[dict], key: str) -> dict[str, list[dict]]:
    index = {}
    for paper in papers:
        doi = paper.get(key, "")
        if not doi:
            continue
        index.setdefault(doi, []).append(paper)
    return index


def find_best_match(pdf_path: Path, papers: list[dict], doi_index: dict[str, list[dict]],
                    safe_doi_index: dict[str, list[dict]],
                    min_score: float) -> tuple[dict | None, str, float]:
    stem = pdf_path.stem
    doi_match = DOI_RE.search(stem)
    if doi_match:
        doi = normalize_doi(doi_match.group(0))
        candidates = doi_index.get(doi, [])
        if len(candidates) == 1:
            return candidates[0], "doi", 1.5
        if len(candidates) > 1:
            return None, "ambiguous-doi", 0.0

    safe_doi = normalize_safe_doi_token(stem)
    safe_candidates = safe_doi_index.get(safe_doi, [])
    if len(safe_candidates) == 1:
        return safe_candidates[0], "safe-doi", 1.45
    if len(safe_candidates) > 1:
        return None, "ambiguous-safe-doi", 0.0

    title_norm = normalize_title(extract_filename_title(stem))
    if len(title_norm) < 12:
        return None, "title-too-short", 0.0

    year_match = YEAR_RE.search(stem)
    year = int(year_match.group(0)) if year_match else None

    candidates = []
    for paper in papers:
        paper_title = paper.get("_title_norm", "")
        score = score_title_match(title_norm, paper_title)
        if year and paper.get("year"):
            if int(paper["year"]) == year:
                score += 0.03
            else:
                score -= 0.05
        if score >= min_score:
            candidates.append((score, paper))

    if not candidates:
        return None, "no-match", 0.0

    candidates.sort(key=lambda item: item[0], reverse=True)
    if len(candidates) > 1 and candidates[0][0] - candidates[1][0] < 0.03:
        return None, "ambiguous-title", candidates[0][0]
    return candidates[0][1], "title", candidates[0][0]


def write_updated_registry(input_path: Path, papers: list[dict]):
    with open(input_path, "w", encoding="utf-8") as f:
        for paper in papers:
            paper.pop("_doi_norm", None)
            paper.pop("_doi_safe", None)
            paper.pop("_title_norm", None)
            f.write(json.dumps(paper, ensure_ascii=False) + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Import local PDFs into EH-LLM and update pdf_path fields")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_DIR),
                        help="Directory containing local PDFs to import")
    parser.add_argument("--input", default=None,
                        help="Registry JSONL to update")
    parser.add_argument("--dest-dir", default=str(DEFAULT_DEST_DIR),
                        help="Destination raw PDF directory")
    parser.add_argument("--min-score", type=float, default=0.78,
                        help="Minimum fuzzy title score to accept")
    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    input_path = detect_input_jsonl(args.input)
    dest_dir = Path(args.dest_dir)

    if not source_dir.exists():
        raise SystemExit(f"Source directory does not exist: {source_dir}")
    if not input_path.exists():
        raise SystemExit(f"Registry JSONL does not exist: {input_path}")

    dest_dir.mkdir(parents=True, exist_ok=True)
    papers = load_papers(input_path)
    doi_index = build_doi_index(papers, "_doi_norm")
    safe_doi_index = build_doi_index(papers, "_doi_safe")

    matched = 0
    updated = 0
    failed = 0
    ambiguous = 0
    seen_paper_ids = set()

    for pdf_path in sorted(source_dir.rglob("*.pdf")):
        paper, method, score = find_best_match(
            pdf_path, papers, doi_index, safe_doi_index, args.min_score)
        if not paper:
            if method.startswith("ambiguous"):
                ambiguous += 1
            else:
                failed += 1
            print(f"SKIP [{method}]: {pdf_path.name}")
            continue

        paper_id = make_paper_id(paper)
        if paper_id in seen_paper_ids:
            ambiguous += 1
            print(f"SKIP [duplicate-paper]: {pdf_path.name} -> {paper_id}")
            continue

        dest_path = dest_dir / f"{paper_id}.pdf"
        shutil.copy2(pdf_path, dest_path)
        rel_path = str(dest_path.relative_to(PROJECT_ROOT))

        if paper.get("pdf_path") != rel_path:
            paper["pdf_path"] = rel_path
            updated += 1

        seen_paper_ids.add(paper_id)
        matched += 1
        print(f"MATCH [{method}:{score:.2f}]: {pdf_path.name} -> {dest_path.name}")

    write_updated_registry(input_path, papers)

    print(f"\nCleanup complete.")
    print(f"  Matched:    {matched}")
    print(f"  Updated:    {updated}")
    print(f"  Ambiguous:  {ambiguous}")
    print(f"  Unmatched:  {failed}")
    print(f"  Registry:   {input_path}")


if __name__ == "__main__":
    main()
