import json
import re
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage01.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage02.jsonl"

# The paper must show evidence of physical fabrication and testing
EXPERIMENT_KEYWORDS = [
    r"experiment",
    r"prototype",
    r"fabricated",
    r"measured",
    r"tested",
    r"demonstrated",
    r"output power",
    r"generated power"
]

# The paper must NOT indicate purely modeling/simulation
EXCLUDE_KEYWORDS = [
    r"purely simulation",
    r"modeling only",
    r"theoretical analysis"
]

def compile_regex(keywords):
    return re.compile(r"(" + r"|".join(keywords) + r")", re.IGNORECASE)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    exp_re = compile_regex(EXPERIMENT_KEYWORDS)
    exclude_re = compile_regex(EXCLUDE_KEYWORDS)

    kept = 0
    total_processed = 0

    print("🚀 Stage 2: Experimental Evidence Mapping")
    
    with open(args.input, "r") as fin, open(args.output, "w") as fout:
        for line in fin:
            if not line.strip(): continue
            paper = json.loads(line)
            abstract = paper.get("abstract", "")
            
            total_processed += 1
            
            # Rule 1: Exclude purely theoretical/simulation abstracts
            if exclude_re.search(abstract):
                continue
                
            # Rule 2: Must contain at least one experiment keyword
            if not exp_re.search(abstract):
                continue
                
            # Passed all filters
            fout.write(json.dumps(paper, ensure_ascii=False) + "\n")
            kept += 1

    print(f"✅ Stage 2 Complete: {total_processed} -> {kept} papers remaining")

if __name__ == "__main__":
    main()
