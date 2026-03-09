#!/usr/bin/env python3
"""
EH-LLM Abstract Backfill Script
================================
Backfill missing abstracts in papers.jsonl by re-querying
OpenAlex and Semantic Scholar APIs.

Usage:
    python backfill_abstracts.py              # 补全全部
    python backfill_abstracts.py --dry-run    # 仅统计，不修改
    python backfill_abstracts.py --source oa  # 仅补全 OpenAlex
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
ENV_PATH = SCRIPT_DIR / ".env"

load_dotenv(ENV_PATH)

S2_API_KEY = os.getenv("S2_API_KEY", "")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "")

PAPERS_JSONL = PROJECT_ROOT / "data_registry" / "papers.jsonl"


# ---------------------------------------------------------------------------
# OpenAlex abstract reconstruction
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex abstract_inverted_index."""
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return ""
    return " ".join(words[i] for i in sorted(words.keys()))


# ---------------------------------------------------------------------------
# API Fetchers
# ---------------------------------------------------------------------------

def fetch_openalex_abstract(paper_id_oa: str, session: requests.Session) -> str:
    """Fetch abstract from OpenAlex single-work API.

    Args:
        paper_id_oa: OpenAlex work ID, e.g. "https://openalex.org/W2741809807"
    """
    if not paper_id_oa:
        return ""

    # Normalize ID to URL format
    if not paper_id_oa.startswith("http"):
        paper_id_oa = f"https://openalex.org/{paper_id_oa}"

    url = paper_id_oa.replace("https://openalex.org/", "https://api.openalex.org/works/")
    params = {"select": "abstract_inverted_index"}
    if OPENALEX_EMAIL:
        params["mailto"] = OPENALEX_EMAIL

    try:
        resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 429:
            time.sleep(5)
            resp = session.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return reconstruct_abstract(data.get("abstract_inverted_index"))
    except requests.RequestException:
        pass
    return ""


def fetch_s2_abstract(paper_id_s2: str, session: requests.Session) -> str:
    """Fetch abstract from Semantic Scholar Paper Detail API.

    Args:
        paper_id_s2: Semantic Scholar paper ID
    """
    if not paper_id_s2:
        return ""

    url = f"https://api.semanticscholar.org/graph/v1/paper/{paper_id_s2}"
    params = {"fields": "abstract"}
    headers = {}
    if S2_API_KEY:
        headers["x-api-key"] = S2_API_KEY

    try:
        resp = session.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 429:
            time.sleep(30)
            resp = session.get(url, params=params, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            return (data.get("abstract") or "").strip()
    except requests.RequestException:
        pass
    return ""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def backfill(source_filter: str = None, dry_run: bool = False):
    """Backfill missing abstracts in papers.jsonl."""
    if not PAPERS_JSONL.exists():
        print(f"❌ {PAPERS_JSONL} not found.")
        sys.exit(1)

    # Load all papers
    papers = []
    with open(PAPERS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))

    # Identify papers missing abstracts
    missing = []
    for i, p in enumerate(papers):
        if p.get("abstract", "").strip():
            continue
        src = p.get("source", "")
        if source_filter:
            if source_filter == "oa" and src not in ("openalex", "both"):
                continue
            if source_filter == "s2" and src not in ("semantic_scholar", "both"):
                continue
        missing.append((i, p))

    total = len(papers)
    already_have = sum(1 for p in papers if p.get("abstract", "").strip())
    print(f"\n📊 Abstract Backfill Status")
    print(f"{'='*50}")
    print(f"  Total papers:          {total}")
    print(f"  Already have abstract: {already_have} ({100*already_have/total:.1f}%)")
    print(f"  Missing abstract:      {len(missing)}")
    print(f"  Source filter:         {source_filter or 'all'}")
    print(f"{'='*50}\n")

    if dry_run:
        # Show breakdown
        oa_miss = sum(1 for _, p in missing if p.get("source") in ("openalex", "both"))
        s2_miss = sum(1 for _, p in missing if p.get("source") in ("semantic_scholar", "both"))
        print(f"  OpenAlex missing:  {oa_miss}")
        print(f"  S2 missing:        {s2_miss}")
        print("  (dry-run, no changes made)")
        return

    session = requests.Session()
    recovered = 0
    failed = 0

    pbar = tqdm(missing, desc="Backfilling", unit="paper", ncols=80)
    for idx, paper in pbar:
        src = paper.get("source", "")
        abstract = ""
        doi = paper.get("doi", "")

        allow_oa = source_filter in (None, "oa")
        allow_s2 = source_filter in (None, "s2")

        # Try OpenAlex first (faster API, more permissive rate limits)
        if allow_oa and src in ("openalex", "both"):
            oa_id = paper.get("paper_id_oa", "")
            abstract = fetch_openalex_abstract(oa_id, session)
            time.sleep(0.15)  # OpenAlex: ~10 req/s for polite pool

        # Try S2 if no OA abstract or source is S2
        if not abstract and allow_s2 and src in ("semantic_scholar", "both"):
            s2_id = paper.get("paper_id_s2", "")
            abstract = fetch_s2_abstract(s2_id, session)
            time.sleep(1.0)  # S2: ~1 req/s without API key

        # Cross-source fallback: Try S2 via DOI if OA failed
        if not abstract and allow_s2 and source_filter is None and doi:
            s2_url = f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
            params = {"fields": "abstract"}
            headers = {}
            if S2_API_KEY:
                headers["x-api-key"] = S2_API_KEY
            try:
                resp = session.get(s2_url, params=params, headers=headers, timeout=15)
                if resp.status_code == 429:
                    time.sleep(30)
                    resp = session.get(s2_url, params=params, headers=headers, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = (data.get("abstract") or "").strip()
            except requests.RequestException:
                pass
            time.sleep(1.0) # S2 rate limit

        # Cross-source fallback: Try OA via DOI if S2 failed
        if not abstract and allow_oa and source_filter is None and doi:
            oa_url = f"https://api.openalex.org/works/doi:{doi}"
            params = {"select": "abstract_inverted_index"}
            if OPENALEX_EMAIL:
                params["mailto"] = OPENALEX_EMAIL
            try:
                resp = session.get(oa_url, params=params, timeout=15)
                if resp.status_code == 200:
                    data = resp.json()
                    abstract = reconstruct_abstract(data.get("abstract_inverted_index"))
            except requests.RequestException:
                pass
            time.sleep(0.15)

        if abstract:
            papers[idx]["abstract"] = abstract
            recovered += 1
        else:
            failed += 1

        pbar.set_postfix(ok=recovered, fail=failed)

    # Write back
    with open(PAPERS_JSONL, "w", encoding="utf-8") as f:
        for p in papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    final_have = sum(1 for p in papers if p.get("abstract", "").strip())
    print(f"\n{'='*50}")
    print(f"  ✅ Backfill Complete")
    print(f"{'='*50}")
    print(f"  Recovered:   {recovered}")
    print(f"  Still missing: {failed}")
    print(f"  Coverage now: {final_have}/{total} ({100*final_have/total:.1f}%)")
    print(f"{'='*50}")


def main():
    parser = argparse.ArgumentParser(
        description="Backfill missing abstracts in papers.jsonl")
    parser.add_argument("--dry-run", action="store_true",
                        help="Only show stats, don't modify data")
    parser.add_argument("--source", choices=["oa", "s2"],
                        help="Only backfill from specific source")
    args = parser.parse_args()
    backfill(source_filter=args.source, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
