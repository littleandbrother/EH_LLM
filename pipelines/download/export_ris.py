import json
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
INPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data_registry" / "core_corpus.ris"

def export_to_ris(input_path: Path, output_path: Path):
    if not input_path.exists():
        print(f"Error: {input_path} does not exist.")
        return

    print(f"Reading from {input_path}...")
    with open(input_path, "r", encoding="utf-8") as fin, open(output_path, "w", encoding="utf-8") as fout:
        count = 0
        for line in fin:
            if not line.strip():
                continue
            try:
                paper = json.loads(line)
            except json.JSONDecodeError:
                continue
                
            # Document Type (Journal Article)
            fout.write("TY  - JOUR\n")
            
            # Title
            if paper.get("title"):
                fout.write(f"TI  - {paper['title']}\n")
            
            # Authors
            for author in paper.get("authors", []):
                if isinstance(author, dict) and author.get("name"):
                    fout.write(f"AU  - {author['name']}\n")
                elif isinstance(author, str):
                    fout.write(f"AU  - {author}\n")
            
            # Journal/Venue
            if paper.get("venue"):
                fout.write(f"JO  - {paper['venue']}\n")
            
            # Year
            if paper.get("year"):
                fout.write(f"PY  - {paper['year']}\n")
            
            # DOI
            if paper.get("doi"):
                doi = paper['doi']
                if doi.startswith("https://doi.org/"):
                    doi = doi.replace("https://doi.org/", "")
                fout.write(f"DO  - {doi}\n")
            
            # URL (if any, although DOI usually handles everything in Zotero)
            if paper.get("pdf_url"):
                fout.write(f"UR  - {paper['pdf_url']}\n")
            elif paper.get("url"):
                fout.write(f"UR  - {paper['url']}\n")
                
            # Abstract
            if paper.get("abstract"):
                abstract = str(paper['abstract']).replace("\n", " ").replace("\r", " ")
                fout.write(f"AB  - {abstract}\n")
                
            # End of Reference
            fout.write("ER  - \n\n")
            count += 1

    print(f"✅ Successfully exported {count} references to {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Convert JSONL to RIS format for Zotero")
    parser.add_argument("--input", default=str(INPUT_FILE), help="Path to input JSONL file")
    parser.add_argument("--output", default=str(OUTPUT_FILE), help="Path to output RIS file")
    args = parser.parse_args()
    
    export_to_ris(Path(args.input), Path(args.output))

if __name__ == "__main__":
    main()
