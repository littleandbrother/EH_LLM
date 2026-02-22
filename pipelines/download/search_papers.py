#!/usr/bin/env python3
"""
EH-LLM Paper Download Pipeline
===============================
Dual-source paper search & download using Semantic Scholar + OpenAlex APIs.

Usage:
    python search_papers.py                    # 运行全部查询
    python search_papers.py --query "piezo"    # 单个查询
    python search_papers.py --skip-pdf         # 只抓元数据，不下载 PDF
    python search_papers.py --stats            # 显示已有数据统计
"""

import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
import yaml
from dotenv import load_dotenv
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
ENV_PATH = SCRIPT_DIR / ".env"
CONFIG_PATH = SCRIPT_DIR / "search_config.yaml"

load_dotenv(ENV_PATH)

S2_API_KEY = os.getenv("S2_API_KEY", "")
OPENALEX_EMAIL = os.getenv("OPENALEX_EMAIL", "")

S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper"
OPENALEX_WORKS_URL = "https://api.openalex.org/works"


def load_config() -> dict:
    """Load search configuration from YAML."""
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------------------
# Semantic Scholar
# ---------------------------------------------------------------------------

class SemanticScholarClient:
    """Semantic Scholar Academic Graph API client."""

    def __init__(self, api_key: str, config: dict):
        self.api_key = api_key
        self.cfg = config.get("semantic_scholar", {})
        self.fields = ",".join(self.cfg.get("fields", []))
        self.max_results = self.cfg.get("max_results_per_query", 100)
        self.delay = self.cfg.get("rate_limit_delay", 1.0)
        self.session = requests.Session()
        if self.api_key:
            self.session.headers["x-api-key"] = self.api_key

    def search(self, query: str, year_range: list = None,
               min_citations: int = 0) -> list[dict]:
        """Search papers with pagination via bulk search endpoint."""
        papers = []
        params = {
            "query": query,
            "fields": self.fields,
        }
        if year_range and len(year_range) == 2:
            params["year"] = f"{year_range[0]}-{year_range[1]}"
        if min_citations > 0:
            params["minCitationCount"] = min_citations

        token = None
        fetched = 0

        while fetched < self.max_results:
            if token:
                params["token"] = token

            try:
                resp = self.session.get(S2_SEARCH_URL, params=params, timeout=30)
                if resp.status_code == 429:
                    print("  [S2] Rate limited, waiting 30s...")
                    time.sleep(30)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                print(f"  [S2] Error: {e}")
                break

            batch = data.get("data", [])
            if not batch:
                break

            papers.extend(batch)
            fetched += len(batch)
            token = data.get("token")

            if not token:
                break

            time.sleep(self.delay)

        return papers[:self.max_results]


# ---------------------------------------------------------------------------
# OpenAlex
# ---------------------------------------------------------------------------

class OpenAlexClient:
    """OpenAlex API client."""

    def __init__(self, email: str, config: dict):
        self.email = email
        self.cfg = config.get("openalex", {})
        self.max_results = self.cfg.get("max_results_per_query", 200)
        self.per_page = self.cfg.get("per_page", 50)
        self.delay = self.cfg.get("rate_limit_delay", 0.2)
        self.session = requests.Session()

    def search(self, query: str, year_range: list = None,
               min_citations: int = 0) -> list[dict]:
        """Search OpenAlex works API with cursor pagination."""
        papers = []
        params = {
            "search": query,
            "per-page": self.per_page,
            "cursor": "*",
            "select": "id,doi,title,publication_year,primary_location,"
                      "authorships,cited_by_count,open_access,"
                      "type,concepts,abstract_inverted_index",
        }
        if self.email:
            params["mailto"] = self.email

        # Build filter string
        filters = []
        if year_range and len(year_range) == 2:
            filters.append(f"publication_year:{year_range[0]}-{year_range[1]}")
        if min_citations > 0:
            filters.append(f"cited_by_count:>{min_citations}")
        filters.append("type:article|proceedings-article")
        if filters:
            params["filter"] = ",".join(filters)

        fetched = 0

        while fetched < self.max_results:
            try:
                resp = self.session.get(OPENALEX_WORKS_URL, params=params,
                                        timeout=30)
                if resp.status_code == 429:
                    print("  [OA] Rate limited, waiting 10s...")
                    time.sleep(10)
                    continue
                resp.raise_for_status()
                data = resp.json()
            except requests.RequestException as e:
                print(f"  [OA] Error: {e}")
                break

            results = data.get("results", [])
            if not results:
                break

            papers.extend(results)
            fetched += len(results)

            cursor = data.get("meta", {}).get("next_cursor")
            if not cursor:
                break
            params["cursor"] = cursor

            time.sleep(self.delay)

        return papers[:self.max_results]


# ---------------------------------------------------------------------------
# Normalization: Convert to unified schema
# ---------------------------------------------------------------------------

def reconstruct_abstract(inverted_index: dict) -> str:
    """Reconstruct abstract from OpenAlex abstract_inverted_index.

    OpenAlex returns abstracts as an inverted index to avoid copyright issues.
    Format: {"word": [position0, position1, ...], ...}
    This function reassembles the original abstract string.
    """
    if not inverted_index:
        return ""
    words = {}
    for word, positions in inverted_index.items():
        for pos in positions:
            words[pos] = word
    if not words:
        return ""
    return " ".join(words[i] for i in sorted(words.keys()))


def normalize_s2_paper(paper: dict) -> dict:
    """Normalize a Semantic Scholar paper to unified format."""
    ext_ids = paper.get("externalIds") or {}
    doi = ext_ids.get("DOI", "")

    oa_pdf = paper.get("openAccessPdf") or {}
    pdf_url = oa_pdf.get("url", "")

    authors = []
    for a in (paper.get("authors") or []):
        authors.append({
            "name": a.get("name", ""),
            "authorId": a.get("authorId", ""),
        })

    return {
        "source": "semantic_scholar",
        "paper_id_s2": paper.get("paperId", ""),
        "doi": doi,
        "title": (paper.get("title") or "").strip(),
        "abstract": (paper.get("abstract") or "").strip(),
        "year": paper.get("year"),
        "venue": (paper.get("venue") or "").strip(),
        "authors": authors,
        "citation_count": paper.get("citationCount", 0),
        "pdf_url": pdf_url,
        "publication_types": paper.get("publicationTypes") or [],
        "fields_of_study": paper.get("fieldsOfStudy") or [],
        "pdf_path": "",
        "hash": "",
    }


def normalize_oa_paper(paper: dict) -> dict:
    """Normalize an OpenAlex paper to unified format."""
    doi_raw = paper.get("doi") or ""
    doi = doi_raw.replace("https://doi.org/", "") if doi_raw else ""

    # Get venue from primary_location
    loc = paper.get("primary_location") or {}
    source = loc.get("source") or {}
    venue = source.get("display_name", "")

    # PDF URL
    oa_info = paper.get("open_access") or {}
    pdf_url = oa_info.get("oa_url", "") or ""

    authors = []
    for a in (paper.get("authorships") or []):
        author_info = a.get("author") or {}
        authors.append({
            "name": author_info.get("display_name", ""),
            "authorId": author_info.get("id", ""),
        })

    return {
        "source": "openalex",
        "paper_id_oa": paper.get("id", ""),
        "doi": doi,
        "title": (paper.get("title") or "").strip(),
        "abstract": reconstruct_abstract(paper.get("abstract_inverted_index")),
        "year": paper.get("publication_year"),
        "venue": venue,
        "authors": authors,
        "citation_count": paper.get("cited_by_count", 0),
        "pdf_url": pdf_url,
        "publication_types": [paper.get("type", "")],
        "fields_of_study": [
            c.get("display_name", "")
            for c in (paper.get("concepts") or [])[:5]
        ],
        "pdf_path": "",
        "hash": "",
    }


# ---------------------------------------------------------------------------
# Deduplication & Filtering
# ---------------------------------------------------------------------------

def compute_hash(paper: dict) -> str:
    """Compute a content hash for deduplication."""
    key = f"{paper.get('doi', '')}|{paper.get('title', '').lower()}"
    return hashlib.md5(key.encode()).hexdigest()


def deduplicate(papers: list[dict]) -> list[dict]:
    """Deduplicate papers by DOI and title hash."""
    seen_dois = set()
    seen_hashes = set()
    unique = []

    for p in papers:
        doi = p.get("doi", "").strip().lower()
        h = compute_hash(p)

        # Skip if we've seen this DOI (and it's not empty)
        if doi and doi in seen_dois:
            continue
        # Skip if title hash matches
        if h in seen_hashes:
            continue

        if doi:
            seen_dois.add(doi)
        seen_hashes.add(h)
        p["hash"] = h
        unique.append(p)

    return unique


def apply_exclusions(papers: list[dict], exclude_kw: list[str]) -> list[dict]:
    """Filter out papers matching exclusion keywords."""
    if not exclude_kw:
        return papers

    exclude_lower = [kw.lower() for kw in exclude_kw]
    filtered = []
    for p in papers:
        text = f"{p.get('title', '')} {p.get('abstract', '')}".lower()
        if any(kw in text for kw in exclude_lower):
            continue
        filtered.append(p)
    return filtered


# ---------------------------------------------------------------------------
# PDF Download
# ---------------------------------------------------------------------------

def download_pdf(paper: dict, pdf_dir: Path, session: requests.Session) -> str:
    """Download PDF if available. Returns the local path or empty string."""
    url = paper.get("pdf_url", "")
    if not url:
        return ""

    # Generate filename from DOI or hash
    doi = paper.get("doi", "")
    if doi:
        safe_name = doi.replace("/", "_").replace(":", "_")
    else:
        safe_name = paper.get("hash", "unknown")
    filename = f"{safe_name}.pdf"
    filepath = pdf_dir / filename

    if filepath.exists():
        return str(filepath.relative_to(PROJECT_ROOT))

    try:
        resp = session.get(url, timeout=60, stream=True,
                           allow_redirects=True)
        if resp.status_code == 200:
            content_type = resp.headers.get("Content-Type", "")
            if "pdf" in content_type or url.endswith(".pdf"):
                with open(filepath, "wb") as f:
                    for chunk in resp.iter_content(8192):
                        f.write(chunk)
                return str(filepath.relative_to(PROJECT_ROOT))
    except Exception:
        pass

    return ""


# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(config: dict, single_query: str = None,
                 skip_pdf: bool = False):
    """Run the full search + download pipeline."""
    filters = config.get("filters", {})
    year_range = filters.get("year_range", [2010, 2026])
    min_citations = filters.get("min_citation_count", 0)
    exclude_kw = filters.get("exclude_keywords", [])

    output_cfg = config.get("output", {})
    papers_jsonl_path = PROJECT_ROOT / output_cfg.get(
        "papers_jsonl", "data_registry/papers.jsonl")
    pdf_dir = PROJECT_ROOT / output_cfg.get("pdf_dir", "data_registry/raw/")
    download_pdfs = output_cfg.get("download_pdf", True) and not skip_pdf
    max_pdf_dl = output_cfg.get("max_pdf_downloads", 500)

    pdf_dir.mkdir(parents=True, exist_ok=True)

    # Determine queries
    queries = [single_query] if single_query else config.get("queries", [])

    print(f"{'='*60}")
    print(f"  EH-LLM Paper Download Pipeline")
    print(f"  Queries:     {len(queries)}")
    print(f"  Year range:  {year_range}")
    print(f"  Min cites:   {min_citations}")
    print(f"  Download PDF: {download_pdfs}")
    print(f"{'='*60}\n")

    all_papers = []

    # --- Semantic Scholar ---
    s2 = SemanticScholarClient(S2_API_KEY, config)
    print("📚 Searching Semantic Scholar...")
    for q in queries:
        print(f"  → \"{q}\"", end=" ")
        results = s2.search(q, year_range, min_citations)
        normalized = [normalize_s2_paper(p) for p in results]
        all_papers.extend(normalized)
        print(f"({len(results)} results)")

    s2_count = len(all_papers)
    print(f"  Total from S2: {s2_count}\n")

    # --- OpenAlex ---
    oa = OpenAlexClient(OPENALEX_EMAIL, config)
    print("📖 Searching OpenAlex...")
    for q in queries:
        print(f"  → \"{q}\"", end=" ")
        results = oa.search(q, year_range, min_citations)
        normalized = [normalize_oa_paper(p) for p in results]
        all_papers.extend(normalized)
        print(f"({len(results)} results)")

    oa_count = len(all_papers) - s2_count
    print(f"  Total from OpenAlex: {oa_count}\n")

    # --- Dedup & Filter ---
    print("🔍 Deduplicating...")
    papers = deduplicate(all_papers)
    print(f"  Before dedup: {len(all_papers)}, after: {len(papers)}")

    print("🔍 Applying exclusion filters...")
    papers = apply_exclusions(papers, exclude_kw)
    print(f"  After filtering: {len(papers)}\n")

    # --- Download PDFs ---
    pdf_count = 0
    if download_pdfs:
        print("📥 Downloading PDFs...")
        dl_session = requests.Session()
        candidates = [p for p in papers if p.get("pdf_url")]
        pbar = tqdm(candidates[:max_pdf_dl], desc="  PDFs",
                    unit="file", ncols=80)
        for p in pbar:
            path = download_pdf(p, pdf_dir, dl_session)
            if path:
                p["pdf_path"] = path
                pdf_count += 1
            time.sleep(0.5)  # Be polite
        print(f"  Downloaded: {pdf_count}/{len(candidates)} PDFs\n")

    # --- Load existing & merge ---
    existing = {}
    if papers_jsonl_path.exists():
        with open(papers_jsonl_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    p = json.loads(line)
                    h = p.get("hash", compute_hash(p))
                    existing[h] = p
        print(f"📂 Found {len(existing)} existing records, merging...")

    # Merge: new papers override existing by hash
    for p in papers:
        h = p.get("hash", compute_hash(p))
        if h in existing:
            # Keep pdf_path if already downloaded
            old_path = existing[h].get("pdf_path", "")
            if old_path and not p.get("pdf_path"):
                p["pdf_path"] = old_path
            # Merge sources
            if existing[h].get("source") != p.get("source"):
                p["source"] = "both"
                if "paper_id_s2" in existing[h]:
                    p["paper_id_s2"] = existing[h]["paper_id_s2"]
                if "paper_id_oa" in existing[h]:
                    p["paper_id_oa"] = existing[h]["paper_id_oa"]
        existing[h] = p

    # --- Write output ---
    final_papers = list(existing.values())
    # Sort by citation count descending
    final_papers.sort(key=lambda x: x.get("citation_count", 0), reverse=True)

    with open(papers_jsonl_path, "w", encoding="utf-8") as f:
        for p in final_papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline Complete")
    print(f"{'='*60}")
    print(f"  Total unique papers:  {len(final_papers)}")
    print(f"  With PDF:             {sum(1 for p in final_papers if p.get('pdf_path'))}")
    print(f"  S2 sourced:           {sum(1 for p in final_papers if 's2' in p.get('source', ''))}")
    print(f"  OpenAlex sourced:     {sum(1 for p in final_papers if 'oa' in p.get('source', '') or p.get('source') == 'openalex')}")
    print(f"  Both sources:         {sum(1 for p in final_papers if p.get('source') == 'both')}")
    print(f"  Output:               {papers_jsonl_path}")
    print(f"{'='*60}")

    return final_papers


def show_stats():
    """Show statistics of existing papers.jsonl."""
    config = load_config()
    output_cfg = config.get("output", {})
    papers_path = PROJECT_ROOT / output_cfg.get(
        "papers_jsonl", "data_registry/papers.jsonl")

    if not papers_path.exists():
        print("No papers.jsonl found. Run the pipeline first.")
        return

    papers = []
    with open(papers_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))

    print(f"\n📊 EH-LLM Paper Registry Stats")
    print(f"{'='*50}")
    print(f"  Total papers:     {len(papers)}")
    print(f"  With PDF:         {sum(1 for p in papers if p.get('pdf_path'))}")
    print(f"  With abstract:    {sum(1 for p in papers if p.get('abstract'))}")
    print(f"  With DOI:         {sum(1 for p in papers if p.get('doi'))}")

    # Year distribution
    years = {}
    for p in papers:
        y = p.get("year")
        if y:
            years[y] = years.get(y, 0) + 1
    if years:
        print(f"\n  Year distribution:")
        for y in sorted(years.keys()):
            bar = "█" * min(years[y], 50)
            print(f"    {y}: {bar} ({years[y]})")

    # Top venues
    venues = {}
    for p in papers:
        v = p.get("venue", "").strip()
        if v:
            venues[v] = venues.get(v, 0) + 1
    if venues:
        print(f"\n  Top 10 venues:")
        for v, c in sorted(venues.items(), key=lambda x: -x[1])[:10]:
            print(f"    {c:4d}  {v}")

    print(f"{'='*50}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="EH-LLM Paper Download Pipeline")
    parser.add_argument("--query", type=str, default=None,
                        help="Run a single query instead of all configured queries")
    parser.add_argument("--skip-pdf", action="store_true",
                        help="Skip PDF downloads, only fetch metadata")
    parser.add_argument("--stats", action="store_true",
                        help="Show statistics of existing data")
    args = parser.parse_args()

    if args.stats:
        show_stats()
        return

    config = load_config()
    run_pipeline(config, single_query=args.query, skip_pdf=args.skip_pdf)


if __name__ == "__main__":
    main()
