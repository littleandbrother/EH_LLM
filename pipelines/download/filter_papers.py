#!/usr/bin/env python3
"""
EH-LLM Paper Filter — LLM-based Abstract Screening
=====================================================
Uses glm-4-7-251222 via Volcengine Ark API to filter papers by relevance.

Criteria: Keep papers with concrete hardware design, output performance
testing, or self-powered system applications. Drop pure theory, pure
materials chemistry synthesis, and other peripheral papers.

Usage:
    python filter_papers.py                      # 过滤全部有摘要的论文
    python filter_papers.py --dry-run            # 仅显示统计
    python filter_papers.py --batch-size 20      # 每批处理 20 篇
    python filter_papers.py --resume             # 断点续传

Requires:
    pip install openai python-dotenv
    export ARK_API_KEY=your_key_here
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
ENV_PATH = SCRIPT_DIR / ".env"

load_dotenv(ENV_PATH)

ARK_API_KEY = os.getenv("ARK_API_KEY", "")
PAPERS_JSONL = PROJECT_ROOT / "data_registry" / "papers.jsonl"
OUTPUT_JSONL = PROJECT_ROOT / "data_registry" / "papers_filtered.jsonl"
PROGRESS_FILE = SCRIPT_DIR / ".filter_progress.json"

# LLM Configuration
LLM_MODEL = "glm-4-7-251222"
LLM_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"

FILTER_PROMPT = """你是一位振动能量采集(Vibration Energy Harvesting)领域的论文审稿专家。
请判断以下论文是否属于**核心工程论文**。

## 判定标准（满足任一即 Keep）:
1. 包含**具体的能量采集器硬件设计**（含结构参数、尺寸、材料选择）
2. 包含**输出性能测试数据**（如功率、电压、频率响应、功率密度）
3. 涉及**自供电系统/传感应用**（将能量采集器用于驱动传感器、物联网节点等）
4. 包含**能量管理电路设计**（整流、MPPT、储能等）

## 排除标准（满足任一即 Drop）:
1. 纯理论/数学推导，无实验验证
2. 纯材料化学合成，未涉及器件层面
3. 综述论文（Review/Survey），除非是重要的系统性综述
4. 仅涉及仿真而无实物验证
5. 非振动能量采集（如纯光伏、纯热电、纯风能）

## 输入
标题: {title}
摘要: {abstract}

## 输出格式（严格遵守，仅输出 JSON）
{{"decision": "Keep" 或 "Drop", "reason": "一句话理由"}}"""


# ---------------------------------------------------------------------------
# LLM Client
# ---------------------------------------------------------------------------

def create_client() -> OpenAI:
    """Create Volcengine Ark OpenAI-compatible client."""
    if not ARK_API_KEY:
        print("❌ ARK_API_KEY not set. Please set it via environment variable or .env file.")
        sys.exit(1)
    return OpenAI(base_url=LLM_BASE_URL, api_key=ARK_API_KEY)


def classify_paper(client: OpenAI, title: str, abstract: str,
                   max_retries: int = 3) -> dict:
    """Classify a single paper using the LLM.

    Returns:
        {"decision": "Keep"/"Drop", "reason": "..."}
    """
    prompt = FILTER_PROMPT.format(title=title, abstract=abstract[:1500])

    for attempt in range(max_retries):
        try:
            response = client.chat.completions.create(
                model=LLM_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.1,
                max_tokens=150,
            )
            content = response.choices[0].message.content.strip()

            # Extract JSON from response (handle markdown code blocks)
            if "```" in content:
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
                content = content.strip()

            result = json.loads(content)
            if "decision" in result:
                return result
        except json.JSONDecodeError:
            # Try to extract decision from freeform text
            content_lower = content.lower() if 'content' in dir() else ""
            if "keep" in content_lower:
                return {"decision": "Keep", "reason": content[:100]}
            elif "drop" in content_lower:
                return {"decision": "Drop", "reason": content[:100]}
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return {"decision": "Error", "reason": str(e)[:100]}

    return {"decision": "Error", "reason": "Max retries exceeded"}


# ---------------------------------------------------------------------------
# Filter Pipeline
# ---------------------------------------------------------------------------

def load_progress() -> set:
    """Load processed paper hashes from progress file."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE, "r") as f:
            data = json.load(f)
            return set(data.get("processed", []))
    return set()


def save_progress(processed: set):
    """Save processed paper hashes to progress file."""
    with open(PROGRESS_FILE, "w") as f:
        json.dump({"processed": list(processed)}, f)


def run_filter(dry_run: bool = False, resume: bool = False,
               batch_size: int = 10):
    """Run the LLM filter pipeline."""
    if not PAPERS_JSONL.exists():
        print(f"❌ {PAPERS_JSONL} not found.")
        sys.exit(1)

    # Load papers
    papers = []
    with open(PAPERS_JSONL, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                papers.append(json.loads(line))

    # Split into filterable (has abstract) and no-abstract
    with_abstract = [p for p in papers if p.get("abstract", "").strip()]
    no_abstract = [p for p in papers if not p.get("abstract", "").strip()]

    print(f"\n📊 LLM Filter Pipeline")
    print(f"{'='*55}")
    print(f"  Total papers:       {len(papers)}")
    print(f"  With abstract:      {len(with_abstract)} (filterable)")
    print(f"  Without abstract:   {len(no_abstract)} (will be dropped)")
    print(f"  Model:              {LLM_MODEL}")
    print(f"{'='*55}\n")

    if dry_run:
        est_cost = len(with_abstract) * 0.001  # rough estimate in RMB
        est_time = len(with_abstract) * 1.5 / 60  # ~1.5s per paper
        print(f"  Estimated time:  {est_time:.0f} minutes")
        print(f"  Estimated cost:  ~¥{est_cost:.2f}")
        print("  (dry-run, no API calls made)")
        return

    client = create_client()

    # Load progress for resume
    processed = load_progress() if resume else set()
    if processed:
        print(f"  Resuming: {len(processed)} papers already processed\n")

    # Load existing filtered results for resume
    keep_papers = []
    drop_papers = []
    error_papers = []

    if resume and OUTPUT_JSONL.exists():
        with open(OUTPUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    p = json.loads(line)
                    keep_papers.append(p)

    # Process papers
    to_process = [p for p in with_abstract
                  if p.get("hash", "") not in processed]

    print(f"  Papers to process: {len(to_process)}\n")

    for i, paper in enumerate(to_process):
        title = paper.get("title", "")
        abstract = paper.get("abstract", "")
        paper_hash = paper.get("hash", "")

        result = classify_paper(client, title, abstract)
        decision = result.get("decision", "Error")
        reason = result.get("reason", "")

        if decision == "Keep":
            paper["filter_decision"] = "Keep"
            paper["filter_reason"] = reason
            keep_papers.append(paper)
        elif decision == "Drop":
            drop_papers.append(paper)
        else:
            error_papers.append(paper)

        processed.add(paper_hash)

        # Progress display
        if (i + 1) % 10 == 0 or i == 0:
            print(f"  [{i+1}/{len(to_process)}] "
                  f"Keep={len(keep_papers)} Drop={len(drop_papers)} "
                  f"Error={len(error_papers)}  |  "
                  f"\"{title[:40]}...\" → {decision}")

        # Save progress periodically
        if (i + 1) % batch_size == 0:
            save_progress(processed)
            # Write intermediate results
            with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
                for p in keep_papers:
                    f.write(json.dumps(p, ensure_ascii=False) + "\n")

        # Rate limiting: ~1 req/s
        time.sleep(0.8)

    # Final save
    save_progress(processed)

    # Sort kept papers by citation count
    keep_papers.sort(key=lambda x: x.get("citation_count", 0), reverse=True)

    with open(OUTPUT_JSONL, "w", encoding="utf-8") as f:
        for p in keep_papers:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")

    # Summary
    print(f"\n{'='*55}")
    print(f"  ✅ Filter Complete")
    print(f"{'='*55}")
    print(f"  Keep:    {len(keep_papers)}")
    print(f"  Drop:    {len(drop_papers)}")
    print(f"  Error:   {len(error_papers)}")
    print(f"  No abstract (auto-drop): {len(no_abstract)}")
    print(f"  Output:  {OUTPUT_JSONL}")
    print(f"{'='*55}")

    # Clean up progress file
    if PROGRESS_FILE.exists():
        PROGRESS_FILE.unlink()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="LLM-based paper filter for EH-LLM pipeline")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show stats without making API calls")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from previous progress")
    parser.add_argument("--batch-size", type=int, default=10,
                        help="Save progress every N papers (default: 10)")
    args = parser.parse_args()

    run_filter(dry_run=args.dry_run, resume=args.resume,
               batch_size=args.batch_size)


if __name__ == "__main__":
    main()
