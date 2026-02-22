import json
import re
import argparse
from pathlib import Path

# Setup paths
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data_registry" / "papers.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage01.jsonl"

CORE_KEYWORDS = [
    r"energy harvesting",
    r"energy harvester",
    r"self-powered",
    r"energy scavenging"
]

MECH_KEYWORDS = [
    r"vibration",
    r"piezoelectric",
    r"triboelectric",
    r"teng\b",
    r"electromagnetic",
    r"rotational",
    r"human motion"
]

EXCLUDE_KEYWORDS = [
    r"review",
    r"overview",
    r"survey",
    r"machine learning prediction",
    r"fault diagnosis",
    r"sensor only",
    r"battery management",
    r"photovoltaic",
    r"thermoelectric"
]

def compile_regex(keywords):
    # Compile with word boundaries where appropriate, case insensitive
    return re.compile(r"(" + r"|".join(keywords) + r")", re.IGNORECASE)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    core_re = compile_regex(CORE_KEYWORDS)
    mech_re = compile_regex(MECH_KEYWORDS)
    exclude_re = compile_regex(EXCLUDE_KEYWORDS)

    kept = 0
    total_processed = 0

    print("🚀 Stage 1: Topic Filtering")
    
    with open(args.input, "r") as fin, open(args.output, "w") as fout:
        for line in fin:
            if not line.strip(): continue
            paper = json.loads(line)
            abstract = paper.get("abstract", "")
            
            # Skip papers without abstracts for now since we can't filter them
            if not abstract.strip():
                continue
                
            total_processed += 1
            
            # Rule 1: Must NOT have exclusion keywords
            if exclude_re.search(abstract) or exclude_re.search(paper.get("title", "")):
                continue
                
            # Rule 2: Must have at least one CORE keyword
            if not core_re.search(abstract) and not core_re.search(paper.get("title", "")):
                continue
                
            # Rule 3: Must have at least one MECHANISM keyword
            if not mech_re.search(abstract) and not mech_re.search(paper.get("title", "")):
                continue
                
            # Passed all filters
            fout.write(json.dumps(paper, ensure_ascii=False) + "\n")
            kept += 1

    print(f"✅ Stage 1 Complete: {total_processed} -> {kept} papers remaining")

if __name__ == "__main__":
    main()
