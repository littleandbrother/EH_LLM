#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from openai import OpenAI

from vehbench.eval import build_request_from_task, load_tasks
from vehbench.solvers.zero_shot_llm import SYSTEM_PROMPT, ZeroShotLlmSolver, _extract_json_object
from vehbench.verifier.v1.calibration import load_frequency_profile
from vehbench.verifier.v1.evaluator import evaluate_request


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Probe candidate LLMs on VEHBench prompts.")
    parser.add_argument("--base-url", required=True, help="OpenAI-compatible base URL.")
    parser.add_argument("--api-key-env", default="VEHBENCH_PROBE_API_KEY", help="Environment variable containing API key.")
    parser.add_argument(
        "--models",
        nargs="+",
        required=True,
        help="Model IDs to probe.",
    )
    parser.add_argument("--timeout-s", type=float, default=40.0, help="Client timeout per request.")
    parser.add_argument("--max-tokens", type=int, default=160, help="Completion token cap.")
    parser.add_argument(
        "--output",
        default="artifacts/reports/llm_probe_results.json",
        help="Path to write JSON results.",
    )
    return parser.parse_args()


def build_cases() -> list[dict]:
    solver = object.__new__(ZeroShotLlmSolver)
    frequency_task = load_tasks(
        "data_registry/benchmark/tasks_paper_grounded.jsonl",
        task_type="frequency_matching",
        split="test-id",
        limit=1,
    )[0]
    repair_task = load_tasks(
        "data_registry/benchmark/tasks_paper_grounded.jsonl",
        task_type="feasibility_repair",
        split="test-id",
        limit=1,
    )[0]
    return [
        {
            "name": "minimal_json",
            "prompt": '{"task":"ping","goal":"Return {\\"candidate\\":{\\"x\\":1}} only."}',
            "task": None,
        },
        {
            "name": "frequency_matching",
            "prompt": ZeroShotLlmSolver._prompt(solver, frequency_task, 1, []),
            "task": frequency_task,
        },
        {
            "name": "feasibility_repair",
            "prompt": ZeroShotLlmSolver._prompt(solver, repair_task, 1, []),
            "task": repair_task,
        },
    ]


def probe_case(client: OpenAI, model: str, case: dict, max_tokens: int, calibration_profile: dict) -> dict:
    started = time.perf_counter()
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": case["prompt"]},
            ],
            temperature=0.0,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        elapsed = round(time.perf_counter() - started, 3)
        content = response.choices[0].message.content or ""
        parsed = _extract_json_object(content)
        usage = None
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        result = {
            "status": "ok",
            "elapsed_s": elapsed,
            "usage": usage,
            "response_excerpt": content[:400],
            "parsed_keys": sorted(parsed.keys()),
        }
        task = case["task"]
        if task is not None:
            from vehbench.solvers.zero_shot_llm import ZeroShotLlmSolver as _Solver

            solver = object.__new__(_Solver)
            candidate = _Solver._coerce_candidate(solver, task, parsed)
            verifier_request = build_request_from_task(task, candidate, candidate_id=f"probe::{model}::{case['name']}")
            interaction = evaluate_request(
                verifier_request,
                task=task,
                apply_frequency_calibration=True,
                calibration_profile=calibration_profile,
                use_task_anchors=False,
            )
            result["candidate"] = candidate
            result["verifier"] = {
                "is_valid_request": interaction["response"]["is_valid_request"],
                "is_feasible": interaction["response"]["is_feasible"],
                "violations": interaction["response"].get("violations") or [],
                "normalized_objective": interaction["response"].get("normalized_objective"),
                "objective_value": interaction["response"].get("objective_value"),
                "outputs": interaction["response"].get("outputs") or {},
            }
        return result
    except Exception as exc:
        return {
            "status": "error",
            "elapsed_s": round(time.perf_counter() - started, 3),
            "error": f"{type(exc).__name__}: {exc}",
        }


def main() -> None:
    args = parse_args()
    import os

    api_key = os.getenv(args.api_key_env, "")
    if not api_key:
        raise SystemExit(f"missing API key in env var: {args.api_key_env}")

    client = OpenAI(
        base_url=args.base_url,
        api_key=api_key,
        timeout=args.timeout_s,
    )
    calibration_profile = load_frequency_profile()
    cases = build_cases()

    results: dict[str, dict] = {
        "base_url": args.base_url,
        "timeout_s": args.timeout_s,
        "max_tokens": args.max_tokens,
        "cases": {},
    }
    for model in args.models:
        model_results = {}
        for case in cases:
            model_results[case["name"]] = probe_case(client, model, case, args.max_tokens, calibration_profile)
        results["cases"][model] = model_results

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
    print(json.dumps(results, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
