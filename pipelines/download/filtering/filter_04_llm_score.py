import json
import os
import argparse
import time
from pathlib import Path
from dotenv import load_dotenv

from openai import OpenAI

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent
INPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage03.jsonl"
OUTPUT_FILE = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.jsonl"
PROGRESS_FILE = PROJECT_ROOT / "data_registry" / "papers_stage04_core_corpus.progress.json"
ENV_PATH = PROJECT_ROOT / "pipelines" / "download" / ".env"

load_dotenv(ENV_PATH)

ARK_API_KEY = os.getenv("ARK_API_KEY")
client = OpenAI(
    api_key=ARK_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)
MODEL_ENDPOINT = "glm-4-7-251222"


def load_progress(progress_path: Path) -> set[str]:
    """Load processed paper IDs for resume support."""
    if not progress_path.exists():
        return set()
    try:
        data = json.loads(progress_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return set()
    return set(data.get("processed_ids", []))


def save_progress(progress_path: Path, processed_ids: set[str]):
    """Persist processed paper IDs so dropped papers are not re-scored."""
    progress_path.write_text(
        json.dumps({"processed_ids": sorted(processed_ids)},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_existing_kept(output_path: Path) -> dict[str, dict]:
    """Load already-kept papers from the stage 4 output."""
    kept = {}
    if not output_path.exists():
        return kept
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            paper = json.loads(line)
            paper_id = paper.get("paper_id_oa") or paper.get(
                "paper_id_s2") or paper.get("hash")
            if paper_id and (paper.get("design_score", 0) or 0) >= 6:
                kept[paper_id] = paper
    return kept


def load_existing_processed_ids(output_path: Path) -> set[str]:
    """Load processed paper IDs from a legacy stage 4 output file."""
    processed = set()
    if not output_path.exists():
        return processed
    with open(output_path, "r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            paper = json.loads(line)
            paper_id = paper.get("paper_id_oa") or paper.get(
                "paper_id_s2") or paper.get("hash")
            if paper_id:
                processed.add(paper_id)
    return processed


def write_kept(output_path: Path, kept_papers: dict[str, dict]):
    """Rewrite the stage 4 output so it only contains the kept corpus."""
    ordered = sorted(
        kept_papers.values(),
        key=lambda p: (
            -(p.get("design_score", 0) or 0),
            -(p.get("citation_count", 0) or 0),
            p.get("title", ""),
        ),
    )
    with open(output_path, "w", encoding="utf-8") as fout:
        for paper in ordered:
            fout.write(json.dumps(paper, ensure_ascii=False) + "\n")

def evaluate_paper(paper: dict, user_prompt: str) -> dict:
    # Build text to evaluate (Title + Abstract) to give the LLM full context
    text_to_eval = f"Title: {paper.get('title', 'Unknown')}\nAbstract: {paper.get('abstract', '')}"
    
    prompt = user_prompt.replace("{abstract_text}", text_to_eval)
    
    try:
        response = client.chat.completions.create(
            model=MODEL_ENDPOINT,
            messages=[
                {"role": "system", "content": "You are an expert reviewer in Energy Harvesting materials and devices. You evaluate papers based on strict scientific data criteria and output purely strictly compliant JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1
        )
        content = response.choices[0].message.content
        return json.loads(content)
    except Exception as e:
        print(f"Error evaluating paper {paper.get('doi', 'unknown')}: {e}")
        return None

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", default=str(INPUT_FILE))
    parser.add_argument("--output", default=str(OUTPUT_FILE))
    # We will pass the user's prompt as an argument or from a file later
    parser.add_argument("--prompt-file", help="Path to the txt file containing the LLM prompt.", required=True)
    args = parser.parse_args()

    with open(args.prompt_file, 'r') as f:
        user_prompt = f.read()

    output_path = Path(args.output)
    processed_ids = load_progress(PROGRESS_FILE)
    if not processed_ids:
        processed_ids = load_existing_processed_ids(output_path)
    kept_papers = load_existing_kept(output_path)
    total_processed = len(processed_ids)
    kept = len(kept_papers)

    print("🚀 Stage 4: LLM Scientific Scoring")
    if processed_ids:
        print(f"  Resuming from {len(processed_ids)} processed papers")

    with open(args.input, "r", encoding="utf-8") as fin:
        for line in fin:
            if not line.strip():
                continue
            paper = json.loads(line)
            paper_id = paper.get("paper_id_oa") or paper.get("paper_id_s2") or paper.get("hash")
            if not paper_id:
                continue

            if paper_id in processed_ids:
                continue

            print(f"[{total_processed + 1}] Evaluating: {paper.get('title')[:60]}...")

            result = evaluate_paper(paper, user_prompt)
            if not result:
                time.sleep(1)
                continue

            paper["design_score"] = result.get("total_design_score", 0)
            paper["llm_reason"] = result.get("reason", "")
            paper["llm_scores"] = result.get("scores", {})
            paper["decision"] = result.get("decision", "DROP")

            if paper["design_score"] >= 6:
                kept_papers[paper_id] = paper
            else:
                kept_papers.pop(paper_id, None)

            processed_ids.add(paper_id)
            total_processed += 1
            kept = len(kept_papers)

            write_kept(output_path, kept_papers)
            save_progress(PROGRESS_FILE, processed_ids)
            time.sleep(0.5) # Rate limit protection

    print(f"✅ Stage 4 Complete: {total_processed} -> {kept} high-quality papers preserved.")

if __name__ == "__main__":
    main()
