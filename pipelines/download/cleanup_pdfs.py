import os
import json
import re
import shutil
from pathlib import Path

PDF_SOURCE_DIR = Path("/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-dev/pdf")
JSONL_FILE = Path("/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/data_registry/papers_stage04_core_corpus.jsonl")
PDF_DEST_DIR = Path("/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/data_registry/raw")

def make_paper_id(paper: dict) -> str:
    doi = paper.get("doi", "").strip()
    if doi:
        # Strip "https://doi.org/" if it exists
        if doi.startswith("https://doi.org/"):
            doi = doi.replace("https://doi.org/", "")
        safe = re.sub(r'[^a-zA-Z0-9]', '_', doi)
        return safe[:80]
    
    import hashlib
    h = paper.get("hash", "")
    if not h:
        key = paper.get("title", "") + str(paper.get("year", ""))
        h = hashlib.md5(key.encode()).hexdigest()[:12]
    return f"noid_{h}"

def normalize_title(title: str) -> str:
    # Lowercase and remove all non-alphanumeric characters
    return re.sub(r'[^a-z0-9]', '', title.lower())

def main():
    PDF_DEST_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load core papers
    papers = []
    with open(JSONL_FILE, "r") as f:
        for line in f:
            if not line.strip(): continue
            papers.append(json.loads(line))
            
    print(f"Loaded {len(papers)} core papers.")
    
    # Pre-compute normalized titles
    for p in papers:
        p["norm_title"] = normalize_title(p.get("title", ""))
        
    # Find all PDFs
    pdf_files = list(PDF_SOURCE_DIR.rglob("*.pdf"))
    print(f"Found {len(pdf_files)} PDFs in source directory.")
    
    matched_count = 0
    
    for pdf_path in pdf_files:
        filename = pdf_path.name
        
        # Zotero format is usually "Author - Year - Title.pdf"
        # We can try to extract the title part
        parts = filename.replace(".pdf", "").split(" - ")
        if len(parts) >= 3:
            # Rejoin in case title has " - "
            pdf_title = " ".join(parts[2:])
        else:
            pdf_title = filename.replace(".pdf", "")
            
        norm_pdf_title = normalize_title(pdf_title)
        
        # In Zotero, the title might be truncated (e.g. max 50-100 chars).
        # We should check if norm_pdf_title is a substring of the paper's normalized title
        # or vice-versa (just in case).
        matched_paper = None
        for p in papers:
            # If the PDF title is at least 15 characters and matches
            if len(norm_pdf_title) > 15 and (norm_pdf_title in p["norm_title"] or p["norm_title"] in norm_pdf_title):
                matched_paper = p
                break
                
        if not matched_paper:
            # Try a looser match: check if the first 30 alphanumeric chars match
            prefix = norm_pdf_title[:30]
            for p in papers:
                if len(prefix) >= 15 and p["norm_title"].startswith(prefix):
                    matched_paper = p
                    break
        
        if matched_paper:
            paper_id = make_paper_id(matched_paper)
            dest_path = PDF_DEST_DIR / f"{paper_id}.pdf"
            shutil.copy2(pdf_path, dest_path)
            matched_count += 1
            # print(f"Matched: {filename} -> {dest_path.name}")
        else:
            print(f"FAILED TO MATCH: {filename}")
            
    print(f"\nCleanup complete. Matched and copied {matched_count} out of {len(pdf_files)} PDFs.")

if __name__ == "__main__":
    main()
