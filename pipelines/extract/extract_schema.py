#!/usr/bin/env python3
"""
EH-LLM Extraction Pipeline (GLM Phase)
=======================================
Reads normalized JSON docs from MinerU and extracts EH structured data
using Volcengine Ark GLM-4 model according to eh_schema_v1.yaml.

Usage:
    python extract_schema.py                 # Process all un-extracted docs
    python extract_schema.py --paper-id X    # Process specific paper
    python extract_schema.py --limit N       # Process max N papers
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

import yaml
from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Config & Paths
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
ENV_PATH = PROJECT_ROOT / "pipelines" / "download" / ".env"

load_dotenv(ENV_PATH)
ARK_API_KEY = os.getenv("ARK_API_KEY", "")

NORMALIZED_DIR = PROJECT_ROOT / "normalized_docs"
EXTRACTED_DIR = PROJECT_ROOT / "data_registry" / "extracted"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "eh_schema_v1.yaml"

if not EXTRACTED_DIR.exists():
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# LLM Client setup
# ---------------------------------------------------------------------------

LLM_MODEL = "glm-4-7-251222"
LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

def create_client() -> OpenAI:
    if not ARK_API_KEY:
        print("❌ ARK_API_KEY not set.")
        sys.exit(1)
    return OpenAI(base_url=LLM_BASE_URL, api_key=ARK_API_KEY)


def build_system_prompt(schema: dict) -> str:
    # A bit crude, but dumps the YAML directly to LLM
    yaml_schema = yaml.dump(schema, allow_unicode=True, sort_keys=False)
    return f"""You are an expert materials science and electrical engineering AI assistant specialized in Energy Harvesting.
Your task is to extract structured knowledge from the provided scientific paper content according to the following strict schema.

TARGET SCHEMA (YAML):
{yaml_schema}

INSTRUCTIONS:
1. Extract data faithfully to the text. Do not hallucinate or guess.
2. Output your response as valid, parseable JSON matching the target schema exactly.
3. If information is not available in the text, omit the field or use null.
4. Always provide evidence tracking information (e.g., section, paragraph, verbatim text) under the 'evidence' object if applicable to the claim.
5. All physical quantities MUST use the units specified in the schema.
6. Make sure performance metrics are bound to measured_at conditions.
"""

def extract_paper(client: OpenAI, sys_prompt: str, doc: dict) -> dict:
    # Build text representation from sections
    content_parts = []
    
    # Title & authors
    content_parts.append(f"TITLE: {doc.get('title', '')}")
    if doc.get('venue'):
        content_parts.append(f"VENUE: {doc.get('venue', '')}")
        
    for sec in doc.get("sections", []):
        heading = sec.get("heading", "")
        text = sec.get("text", "")
        # Very rough thresholding to avoid giant prompts
        if len(text) > 50:
            content_parts.append(f"--- SECTION: {heading} ---\n{text}")
            
    # Include tables
    for tab in doc.get("tables", []):
        content_parts.append(f"--- TABLE (Page {tab.get('page')}) ---\n{tab.get('content')}")
        
    full_text = "\n\n".join(content_parts)
    
    # Truncate if insanely long (GLM context limit is usually high but let's be safe)
    if len(full_text) > 60000:
        full_text = full_text[:60000]

    user_prompt = f"Extract structured data from the following paper content:\n\n{full_text}"

    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.1,
                max_tokens=4000,
            )
            content = response.choices[0].message.content.strip()
            
            # Extract JSON
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()
                
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            if attempt < 2:
                time.sleep(2)
                continue
            return {"error": f"JSON Decode: {e}", "raw_output": content}
        except Exception as e:
            if attempt < 2:
                time.sleep(5)
                continue
            return {"error": str(e)}

def run(limit: int = None, paper_id: str = None):
    # Load schema
    if not SCHEMA_PATH.exists():
        print(f"❌ Schema not found: {SCHEMA_PATH}")
        sys.exit(1)
        
    with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = yaml.safe_load(f)
        
    sys_prompt = build_system_prompt(schema)
    client = create_client()

    docs_to_process = []
    for f in NORMALIZED_DIR.glob("*.json"):
        if paper_id and paper_id not in f.stem:
            continue
        out_f = EXTRACTED_DIR / f.name
        if not out_f.exists():
            docs_to_process.append(f)

    if limit:
        docs_to_process = docs_to_process[:limit]

    print(f"\n▶️ Starting extraction for {len(docs_to_process)} documents...\n")
    
    success_count = 0
    fail_count = 0

    for idx, doc_path in enumerate(docs_to_process, 1):
        print(f"[{idx}/{len(docs_to_process)}] Processing {doc_path.stem}...")
        
        try:
            doc = json.loads(doc_path.read_text(encoding="utf-8", errors="replace"))
        except Exception as e:
            print(f"  ❌ Failed to parse {doc_path.name}: {e}")
            fail_count += 1
            continue
            
        start = time.time()
        result = extract_paper(client, sys_prompt, doc)
        dur = time.time() - start
        
        if "error" in result:
            print(f"  ❌ LLM Extraction failed ({dur:.1f}s): {result['error'][:100]}")
            fail_count += 1
        else:
            print(f"  ✅ Extracted successfully ({dur:.1f}s)")
            success_count += 1
            
            # Save
            out_file = EXTRACTED_DIR / doc_path.name
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*50}")
    print(f"  ✅ Extraction Complete")
    print(f"  Success: {success_count} | Failed: {fail_count}")
    print(f"{'='*50}\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--paper-id", type=str, default=None)
    args = parser.parse_args()
    run(limit=args.limit, paper_id=args.paper_id)
