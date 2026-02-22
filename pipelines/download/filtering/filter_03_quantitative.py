import json
import re
import argparse
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage02.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage03.jsonl"

# Must have power units AND excitation condition units
POWER_KEYWORDS = [
    r"\bW\b",
    r"\bmW\b",
    r"\bµW\b",
    r"\buW\b"
]

EXCITATION_KEYWORDS = [
    r"\bHz\b",
    r"\bg\b",
    r"\brpm\b",
    r"m/s²"
]

def compile_regex(keywords, ignore_case=False):
    # Notice: specific physical units are often case sensitive (W vs w), but user requested these so we'll be careful.
    # We will use exactly what they gave us.
    flags = re.IGNORECASE if ignore_case else 0
    return re.compile(r"(" + r"|".join(keywords) + r")", flags)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    args = parser.parse_args()

    # Note: we don't ignore case for units, W vs w matters, Hz vs hz matters less but usually capital H
    # However we will make power case-sensitive so it doesn't match generic words wrapping 'W' or 'w'
    power_re = compile_regex(POWER_KEYWORDS)
    excitation_re = compile_regex(EXCITATION_KEYWORDS)

    kept = 0
    total_processed = 0

    print("🚀 Stage 3: Quantitative Signal Mapping")
    
    with open(args.input, "r") as fin, open(args.output, "w") as fout:
        for line in fin:
            if not line.strip(): continue
            paper = json.loads(line)
            abstract = paper.get("abstract", "")
            
            total_processed += 1
            
            # Rule 1: Must contain at least one power unit
            if not power_re.search(abstract):
                continue
                
            # Rule 2: Must contain at least one excitation unit
            if not excitation_re.search(abstract):
                continue
                
            # Passed all filters
            fout.write(json.dumps(paper, ensure_ascii=False) + "\n")
            kept += 1

    print(f"✅ Stage 3 Complete: {total_processed} -> {kept} papers remaining")

if __name__ == "__main__":
    main()
