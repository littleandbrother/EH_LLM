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
ENV_PATH = PROJECT_ROOT / "pipelines" / "download" / ".env"

load_dotenv(ENV_PATH)

ARK_API_KEY = os.getenv("ARK_API_KEY")
client = OpenAI(
    api_key=ARK_API_KEY,
    base_url="https://ark.cn-beijing.volces.com/api/v3",
)
MODEL_ENDPOINT = "glm-4-7-251222"

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

    kept = 0
    total_processed = 0

    print("🚀 Stage 4: LLM Scientific Scoring")
    
    # Load already processed to support resuming
    processed_ids = set()
    if os.path.exists(args.output):
        with open(args.output, "r") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    processed_ids.add(p.get("paper_id_oa") or p.get("paper_id_s2") or p.get("hash"))

    with open(args.input, "r") as fin, open(args.output, "a") as fout:
        for line in fin:
            if not line.strip(): continue
            paper = json.loads(line)
            paper_id = paper.get("paper_id_oa") or paper.get("paper_id_s2") or paper.get("hash")
            
            if paper_id in processed_ids:
                total_processed += 1
                if paper.get("design_score", 0) >= 6:
                    kept += 1
                continue
                
            print(f"[{total_processed+1}] Evaluating: {paper.get('title')[:60]}...")
            
            result = evaluate_paper(paper, user_prompt)
            if not result:
                time.sleep(1) # Backoff on error
                continue
                
            # Embed the LLM's opinion
            paper["design_score"] = result.get("total_design_score", 0)
            paper["llm_reason"] = result.get("reason", "")
            paper["llm_scores"] = result.get("scores", {})
            paper["decision"] = result.get("decision", "DROP")
            
            # Save strictly if >= 6
            if paper["design_score"] >= 6:
                kept += 1
                
            fout.write(json.dumps(paper, ensure_ascii=False) + "\n")
            fout.flush()
            total_processed += 1
            time.sleep(0.5) # Rate limit protection

    print(f"✅ Stage 4 Complete: {total_processed} -> {kept} high-quality papers preserved.")

if __name__ == "__main__":
    main()
