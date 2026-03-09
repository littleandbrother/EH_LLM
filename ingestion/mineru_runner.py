#!/usr/bin/env python3
"""
EH-LLM MinerU PDF Extraction Pipeline
=======================================
Batch-process PDFs through MinerU to produce structured markdown,
layout JSON, images, normalized JSON, and provenance traces.

Usage:
    python mineru_runner.py                       # Process all unprocessed PDFs
    python mineru_runner.py --limit 10            # Process max 10 PDFs
    python mineru_runner.py --paper-id <doi>      # Process specific paper
    python mineru_runner.py --status              # Show processing status
    python mineru_runner.py --device mps          # Use Apple Silicon GPU
    python mineru_runner.py --backend pipeline    # Use CPU-only pipeline backend

Workflow:
    papers.jsonl → (PDF) → MinerU → parsed_docs/ → normalized_docs/ → provenance_docs/
"""

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent

PAPERS_JSONL = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.jsonl"
PDF_DIR = PROJECT_ROOT / "data_registry" / "raw"
PARSED_DIR = PROJECT_ROOT / "parsed_docs"
NORMALIZED_DIR = PROJECT_ROOT / "normalized_docs"
PROVENANCE_DIR = PROJECT_ROOT / "provenance_docs"
DEFAULT_MINERU_SOURCE = os.getenv("MINERU_MODEL_SOURCE", "modelscope")


def detect_default_device() -> str:
    """Choose a sensible default device for the current platform."""
    if sys.platform == "darwin":
        return "mps"
    if sys.platform.startswith("linux"):
        return "cuda"
    return "cpu"


DEFAULT_DEVICE = detect_default_device()

# Ensure dirs exist
for d in [PARSED_DIR, NORMALIZED_DIR, PROVENANCE_DIR]:
    d.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Paper ID Generation
# ---------------------------------------------------------------------------

def make_paper_id(paper: dict) -> str:
    """Generate a stable, filesystem-safe paper ID from DOI or hash."""
    doi = paper.get("doi", "").strip()
    if doi:
        safe = re.sub(r'[^a-zA-Z0-9]', '_', doi)
        return safe[:80]
    # Fallback to hash
    h = paper.get("hash", "")
    if not h:
        key = paper.get("title", "") + str(paper.get("year", ""))
        h = hashlib.md5(key.encode()).hexdigest()[:12]
    return f"noid_{h}"


# ---------------------------------------------------------------------------
# MinerU Invocation
# ---------------------------------------------------------------------------

def run_mineru(pdf_path: Path, output_dir: Path,
               device: str = DEFAULT_DEVICE,
               backend: str = "pipeline",
               lang: str = "en",
               source: str = DEFAULT_MINERU_SOURCE) -> dict:
    """
    Run MinerU CLI on a single PDF.

    Returns:
        dict with keys: success, content_md_path, layout_json_path,
                        images_dir, duration_s, error
    """
    result = {
        "success": False,
        "content_md_path": "",
        "layout_json_path": "",
        "images_dir": "",
        "duration_s": 0.0,
        "error": "",
    }

    # Build command
    cmd = [
        sys.executable,
        "-m", "mineru.cli.client",
        "-p", str(pdf_path),
        "-o", str(output_dir),
        "-l", lang,
        "-b", backend,
        "-d", device,
        "--source", source,
    ]

    start = time.time()
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=1800,  # 30 min timeout per PDF
        )
        result["duration_s"] = round(time.time() - start, 2)

        if proc.returncode != 0:
            err_msg = proc.stderr[-1000:] if proc.stderr else (proc.stdout[-1000:] if proc.stdout else "No output")
            result["error"] = f"exit code {proc.returncode} | {err_msg}"
            return result

    except subprocess.TimeoutExpired:
        result["duration_s"] = round(time.time() - start, 2)
        result["error"] = "timeout (1800s)"
        return result
    except FileNotFoundError:
        result["error"] = ("MinerU module not found. Install with: "
                           "pip install 'mineru[pipeline]'")
        return result

    # Locate outputs — MinerU creates a subdir named after the PDF
    pdf_stem = pdf_path.stem
    # MinerU may put output in output_dir/<pdf_stem>/
    # or directly in output_dir/. Let's search for the .md file.
    md_files = list(output_dir.rglob("*.md"))
    json_files = list(output_dir.rglob("*layout*.json")) + \
                 list(output_dir.rglob("*content_list*.json")) + \
                 list(output_dir.rglob("*.json"))
    img_dirs = [d for d in output_dir.rglob("images") if d.is_dir()]

    if md_files:
        # Pick the main content markdown (usually <stem>.md or content.md)
        main_md = None
        for mf in md_files:
            if mf.stem == pdf_stem or mf.name == "content.md":
                main_md = mf
                break
        if not main_md:
            main_md = md_files[0]

        # Rename to standard name
        target_md = output_dir / "content.md"
        if main_md != target_md:
            shutil.copy2(main_md, target_md)
        result["content_md_path"] = str(target_md)

    if json_files:
        # Find layout JSON
        layout_json = None
        for jf in json_files:
            if "layout" in jf.name.lower() or "content_list" in jf.name.lower():
                layout_json = jf
                break
        if not layout_json:
            layout_json = json_files[0]

        target_json = output_dir / "layout.json"
        if layout_json != target_json and layout_json.name != "layout.json":
            shutil.copy2(layout_json, target_json)
            layout_json = target_json
        result["layout_json_path"] = str(layout_json)

    if img_dirs:
        result["images_dir"] = str(img_dirs[0])

    result["success"] = bool(md_files)
    if not result["success"]:
        result["error"] = result.get("error") or f"MinerU exited 0 but no output files found. STDOUT: {proc.stdout[-5000:] if proc.stdout else ''} STDERR: {proc.stderr[-5000:] if proc.stderr else ''}"
    return result


# ---------------------------------------------------------------------------
# Post-processing: Normalized JSON
# ---------------------------------------------------------------------------

def build_normalized_doc(paper: dict, paper_id: str,
                         parsed_dir: Path) -> dict:
    """
    Build a normalized document JSON from parsed MinerU output.
    This is a lightweight structure for downstream LLM processing.
    """
    content_md = parsed_dir / "content.md"
    layout_json = parsed_dir / "layout.json"

    doc = {
        "paper_id": paper_id,
        "doi": paper.get("doi", ""),
        "title": paper.get("title", ""),
        "year": paper.get("year"),
        "venue": paper.get("venue", ""),
        "authors": [a.get("name", "") for a in paper.get("authors", [])],
        "citation_count": paper.get("citation_count", 0),
        "sections": [],
        "tables": [],
        "figures": [],
        "metadata": {
            "source": paper.get("source", ""),
            "pdf_url": paper.get("pdf_url", ""),
            "parsed_at": datetime.now(timezone.utc).isoformat(),
        }
    }

    # Parse markdown into sections
    if content_md.exists():
        text = content_md.read_text(encoding="utf-8", errors="replace")
        sections = _split_markdown_sections(text)
        doc["sections"] = sections

    # Parse layout JSON for tables/figures
    if layout_json.exists():
        try:
            layout = json.loads(layout_json.read_text(
                encoding="utf-8", errors="replace"))
            if isinstance(layout, list):
                for item in layout:
                    item_type = item.get("type", "")
                    if "table" in item_type.lower():
                        doc["tables"].append({
                            "page": item.get("page", -1),
                            "content": item.get("text", item.get("content", "")),
                        })
                    elif "figure" in item_type.lower() or "image" in item_type.lower():
                        doc["figures"].append({
                            "page": item.get("page", -1),
                            "caption": item.get("text", item.get("content", "")),
                            "path": item.get("img_path", ""),
                        })
        except (json.JSONDecodeError, KeyError):
            pass

    return doc


def _split_markdown_sections(text: str) -> list[dict]:
    """Split markdown text into sections by headings."""
    sections = []
    current_heading = "Preamble"
    current_level = 0
    current_lines = []

    for line in text.split("\n"):
        heading_match = re.match(r'^(#{1,6})\s+(.*)', line)
        if heading_match:
            # Save previous section
            if current_lines:
                body = "\n".join(current_lines).strip()
                if body:
                    sections.append({
                        "heading": current_heading,
                        "level": current_level,
                        "text": body,
                    })
            current_heading = heading_match.group(2).strip()
            current_level = len(heading_match.group(1))
            current_lines = []
        else:
            current_lines.append(line)

    # Last section
    if current_lines:
        body = "\n".join(current_lines).strip()
        if body:
            sections.append({
                "heading": current_heading,
                "level": current_level,
                "text": body,
            })

    return sections


# ---------------------------------------------------------------------------
# Provenance Trace
# ---------------------------------------------------------------------------

def build_provenance_trace(paper: dict, paper_id: str,
                           mineru_result: dict,
                           normalized_path: str) -> dict:
    """Build a provenance trace document for full traceability."""
    return {
        "paper_id": paper_id,
        "doi": paper.get("doi", ""),
        "title": paper.get("title", ""),
        "source_apis": [paper.get("source", "")],
        "pdf_url": paper.get("pdf_url", ""),
        "pdf_local_path": paper.get("pdf_path", ""),
        "processing": {
            "tool": "MinerU",
            "version": _get_mineru_version(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "duration_s": mineru_result.get("duration_s", 0),
            "success": mineru_result.get("success", False),
            "error": mineru_result.get("error", ""),
        },
        "outputs": {
            "content_md": mineru_result.get("content_md_path", ""),
            "layout_json": mineru_result.get("layout_json_path", ""),
            "images_dir": mineru_result.get("images_dir", ""),
            "normalized_json": normalized_path,
        },
        "data_lineage": {
            "papers_jsonl_hash": paper.get("hash", ""),
            "pipeline_step": "ingestion/mineru_runner.py",
        }
    }


def _get_mineru_version() -> str:
    """Get installed MinerU version."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "mineru.cli.client", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.stdout.strip() or "unknown"
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# Status Report
# ---------------------------------------------------------------------------

def show_status():
    """Show processing status summary."""
    if not PAPERS_JSONL.exists():
        print("❌ No papers.jsonl found.")
        return

    papers = _load_papers()
    paper_ids_with_pdf = {
        make_paper_id(p) for p in papers if _paper_has_pdf(p)
    }
    processed = _load_successful_processed_ids()
    failed = _load_failed_processed_ids() - processed
    remaining = paper_ids_with_pdf - processed

    print(f"\n📊 MinerU Processing Status")
    print(f"{'='*50}")
    print(f"  Total papers:          {len(papers)}")
    print(f"  Papers with PDF:       {len(paper_ids_with_pdf)}")
    print(f"  Successfully parsed:   {len(processed)}")
    print(f"  Failed:                {len(failed)}")
    print(f"  Remaining:             {len(remaining)}")
    print(f"{'='*50}")

    if processed:
        # Count sections, tables, figures across all normalized docs
        total_sections = 0
        total_tables = 0
        total_figures = 0
        for nf in NORMALIZED_DIR.glob("*.json"):
            try:
                doc = json.loads(nf.read_text())
                total_sections += len(doc.get("sections", []))
                total_tables += len(doc.get("tables", []))
                total_figures += len(doc.get("figures", []))
            except Exception:
                pass
        print(f"\n  📑 Parsed Content Summary:")
        print(f"    Sections:  {total_sections}")
        print(f"    Tables:    {total_tables}")
        print(f"    Figures:   {total_figures}")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_papers() -> list[dict]:
    """Load papers from papers.jsonl."""
    papers = []
    with open(PAPERS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                papers.append(json.loads(line))
    return papers


def _resolve_pdf_path(paper: dict) -> Path:
    """Resolve the PDF path from registry metadata or the canonical raw path."""
    stored_path = paper.get("pdf_path", "")
    if stored_path:
        candidate = PROJECT_ROOT / stored_path
        if candidate.exists():
            return candidate
    return PDF_DIR / f"{make_paper_id(paper)}.pdf"


def _paper_has_pdf(paper: dict) -> bool:
    """Return True when a paper PDF can be resolved locally."""
    return _resolve_pdf_path(paper).exists()


def _load_trace_statuses() -> dict[str, bool]:
    """Load success flags from provenance traces."""
    statuses = {}
    for trace_path in PROVENANCE_DIR.glob("*.trace.json"):
        try:
            trace = json.loads(trace_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        paper_id = trace.get("paper_id") or trace_path.stem.replace(".trace", "")
        statuses[paper_id] = bool(trace.get("processing", {}).get("success", False))
    return statuses


def _load_successful_processed_ids() -> set[str]:
    """Return paper IDs with successful normalized output."""
    success_ids = {f.stem for f in NORMALIZED_DIR.glob("*.json")}
    for paper_id, status in _load_trace_statuses().items():
        if status:
            success_ids.add(paper_id)
    return success_ids


def _load_failed_processed_ids() -> set[str]:
    """Return paper IDs with failed provenance traces."""
    return {
        paper_id for paper_id, status in _load_trace_statuses().items()
        if not status
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(limit: int = None, paper_id_filter: str = None,
        device: str = DEFAULT_DEVICE, backend: str = "pipeline",
        lang: str = "en", source: str = DEFAULT_MINERU_SOURCE,
        force: bool = False):
    """Run the MinerU extraction pipeline."""
    print(f"\n{'='*60}")
    print(f"  EH-LLM MinerU PDF Extraction Pipeline")
    print(f"  Device:  {device}  |  Backend: {backend}  |  Lang: {lang}")
    print(f"  Model source: {source}")
    print(f"{'='*60}\n")

    if not PAPERS_JSONL.exists():
        print("❌ No papers.jsonl found. Run search_papers.py first.")
        return

    papers = _load_papers()
    papers_with_pdf = [p for p in papers if _paper_has_pdf(p)]

    if paper_id_filter:
        papers_with_pdf = [
            p for p in papers_with_pdf
            if paper_id_filter.lower() in make_paper_id(p).lower()
            or paper_id_filter.lower() in p.get("doi", "").lower()
        ]

    print(f"📚 Papers with PDF: {len(papers_with_pdf)}")

    # Filter already processed (unless forcing)
    if not force:
        already_done = _load_successful_processed_ids()
        papers_with_pdf = [
            p for p in papers_with_pdf
            if make_paper_id(p) not in already_done
        ]
        print(f"📋 Remaining to process: {len(papers_with_pdf)}")

    if limit:
        papers_with_pdf = papers_with_pdf[:limit]
        print(f"🔢 Limit: {limit}")

    if not papers_with_pdf:
        print("\n✅ All papers already processed (or none have PDFs).")
        print("   To download PDFs first: python pipelines/download/search_papers.py")
        return

    print(f"\n▶️  Starting processing of {len(papers_with_pdf)} papers...\n")

    success_count = 0
    fail_count = 0

    for i, paper in enumerate(papers_with_pdf, 1):
        pid = make_paper_id(paper)
        title = paper.get("title", "Unknown")[:60]
        pdf_path = _resolve_pdf_path(paper)

        print(f"[{i}/{len(papers_with_pdf)}] {pid}")
        print(f"  📄 {title}...")

        if not pdf_path.exists():
            print(f"  ❌ PDF not found: {pdf_path}")
            fail_count += 1
            continue

        paper_parsed_dir = PARSED_DIR / pid
        tmp_output_dir = Path(
            tempfile.mkdtemp(prefix=f"{pid}_", dir=str(PARSED_DIR)))

        # Step 1: Run MinerU
        print(f"  🔍 Running MinerU...", end=" ", flush=True)
        mineru_result = run_mineru(
            pdf_path, tmp_output_dir,
            device=device, backend=backend, lang=lang, source=source
        )

        if mineru_result["success"]:
            print(f"✅ ({mineru_result['duration_s']}s)")
            if paper_parsed_dir.exists():
                shutil.rmtree(paper_parsed_dir)
            shutil.move(str(tmp_output_dir), str(paper_parsed_dir))
        else:
            print(f"❌ {mineru_result['error'][:80]}")
            fail_count += 1
            shutil.rmtree(tmp_output_dir, ignore_errors=True)
            # Still write provenance trace for failures
            trace = build_provenance_trace(paper, pid, mineru_result, "")
            trace_path = PROVENANCE_DIR / f"{pid}.trace.json"
            trace_path.write_text(
                json.dumps(trace, ensure_ascii=False, indent=2))
            continue

        # Step 2: Build normalized doc
        print(f"  📝 Normalizing...", end=" ", flush=True)
        norm_doc = build_normalized_doc(paper, pid, paper_parsed_dir)
        norm_path = NORMALIZED_DIR / f"{pid}.json"
        norm_path.write_text(
            json.dumps(norm_doc, ensure_ascii=False, indent=2))
        n_sections = len(norm_doc.get("sections", []))
        n_tables = len(norm_doc.get("tables", []))
        print(f"✅ ({n_sections} sections, {n_tables} tables)")

        # Step 3: Write provenance trace
        trace = build_provenance_trace(
            paper, pid, mineru_result, str(norm_path))
        trace_path = PROVENANCE_DIR / f"{pid}.trace.json"
        trace_path.write_text(
            json.dumps(trace, ensure_ascii=False, indent=2))

        success_count += 1
        print()

    # Summary
    print(f"\n{'='*60}")
    print(f"  ✅ Pipeline Complete")
    print(f"{'='*60}")
    print(f"  Processed:  {success_count + fail_count}")
    print(f"  Success:    {success_count}")
    print(f"  Failed:     {fail_count}")
    print(f"  Output:     {PARSED_DIR}/")
    print(f"              {NORMALIZED_DIR}/")
    print(f"              {PROVENANCE_DIR}/")
    print(f"{'='*60}")


def main():
    parser = argparse.ArgumentParser(
        description="EH-LLM MinerU PDF Extraction Pipeline")
    parser.add_argument("--limit", type=int, default=None,
                        help="Max number of PDFs to process")
    parser.add_argument("--paper-id", type=str, default=None,
                        help="Process specific paper (DOI or ID substring)")
    parser.add_argument("--device", type=str, default=DEFAULT_DEVICE,
                        help=f"Inference device: cpu/cuda/mps (default: {DEFAULT_DEVICE})")
    parser.add_argument("--backend", type=str, default="pipeline",
                        help="MinerU backend: pipeline/hybrid-auto-engine "
                             "(default: pipeline)")
    parser.add_argument("--lang", type=str, default="en",
                        help="Document language (default: en)")
    parser.add_argument("--source", type=str, default=DEFAULT_MINERU_SOURCE,
                        choices=["huggingface", "modelscope", "local"],
                        help="MinerU model source (default: env MINERU_MODEL_SOURCE or modelscope)")
    parser.add_argument("--force", action="store_true",
                        help="Re-process already parsed papers")
    parser.add_argument("--status", action="store_true",
                        help="Show processing status")
    args = parser.parse_args()

    if args.status:
        show_status()
        return

    run(
        limit=args.limit,
        paper_id_filter=args.paper_id,
        device=args.device,
        backend=args.backend,
        lang=args.lang,
        source=args.source,
        force=args.force,
    )


if __name__ == "__main__":
    main()
