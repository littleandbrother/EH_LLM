from __future__ import annotations

import json
import multiprocessing as mp
import os
import re
import time
from typing import Any

from .base import BaseSolver
from ..eval.runtime import clamp_candidate, initial_candidate, midpoint_candidate, ordered_variable_keys
from ..llm import get_llm_client, get_llm_config

SYSTEM_PROMPT = """Return JSON only.
Choose one in-bounds candidate for the VEHBench task.
Prioritize feasibility first.
Use exact variable names.
Response format: {"candidate":{"variable_name": number}}"""


def _extract_json_object(text: str) -> dict[str, Any]:
    text = text.strip()
    if not text:
        raise ValueError("empty model response")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model response")
    payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("model response JSON is not an object")
    return payload


def _llm_request_worker(
    queue,
    config: dict[str, str],
    system_prompt: str,
    prompt: str,
    temperature: float,
    max_tokens: int,
) -> None:
    try:
        from openai import OpenAI

        client = OpenAI(
            base_url=config["base_url"],
            api_key=config["api_key"],
            timeout=float(config["timeout_s"]),
        )
        response = client.chat.completions.create(
            model=config["model"],
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        usage = None
        if response.usage is not None:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
        queue.put(
            {
                "ok": True,
                "content": response.choices[0].message.content or "",
                "usage": usage,
            }
        )
    except Exception as exc:
        queue.put(
            {
                "ok": False,
                "error": f"{type(exc).__name__}: {exc}",
            }
        )


class ZeroShotLlmSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="zero_shot_llm", base_seed=seed)
        self.client, self.config = get_llm_client()
        self.temperature = float(self.config.get("temperature", 0.0) or 0.0)
        self.max_attempts = int(os.getenv("VEHBENCH_ZERO_SHOT_MAX_ATTEMPTS", "1"))
        self.hard_timeout_s = float(os.getenv("VEHBENCH_ZERO_SHOT_HARD_TIMEOUT_S", "20"))

    def _default_candidate(self, task: dict) -> dict:
        if task.get("task_type") == "feasibility_repair":
            seed_candidate = initial_candidate(task)
            if seed_candidate is not None:
                return seed_candidate
        return midpoint_candidate(task)

    def _prompt(self, task: dict, attempt_index: int, prior_candidates: list[dict]) -> str:
        variable_bounds = {
            key: [value.get("min"), value.get("max"), value.get("unit")]
            for key, value in (task.get("variable_bounds") or {}).items()
        }
        fixed_conditions = task.get("fixed_conditions") or {}
        hard_constraints = task.get("hard_constraints") or {}
        payload = {
            "task": task["task_type"],
            "bounds": variable_bounds,
            "target_hz": fixed_conditions.get("target_resonant_frequency_hz"),
            "excitation_hz": fixed_conditions.get("excitation_frequency_hz"),
            "accel_g": fixed_conditions.get("acceleration_g"),
            "freq_tol_pct": hard_constraints.get("frequency_error_tolerance_pct"),
        }
        if task.get("task_type") == "feasibility_repair":
            payload["start"] = task.get("initial_candidate")
            payload["goal"] = "Repair the infeasible start by moving resonance toward target_hz."
        else:
            payload["goal"] = "Match target_hz."
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    def _coerce_candidate(self, task: dict, payload: dict[str, Any]) -> dict:
        candidate = dict(self._default_candidate(task))
        proposed = payload.get("candidate")
        if not isinstance(proposed, dict):
            proposed = {
                key: payload[key]
                for key in ordered_variable_keys(task)
                if key in payload
            }
        for key in ordered_variable_keys(task):
            value = proposed.get(key)
            if value is None:
                continue
            candidate[key] = float(value)
        return clamp_candidate(task, candidate)

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        prior_candidates: list[dict] = []
        budget = session.budget if self.max_attempts <= 0 else min(session.budget, self.max_attempts)

        while not session.exhausted and len(prior_candidates) < budget:
            prompt = self._prompt(
                session.task,
                attempt_index=len(prior_candidates) + 1,
                prior_candidates=prior_candidates,
            )
            api_started = time.perf_counter()
            payload: dict[str, Any] = {}
            model_error = None
            usage = None
            try:
                ctx = mp.get_context("spawn")
                queue = ctx.Queue()
                proc = ctx.Process(
                    target=_llm_request_worker,
                    args=(
                        queue,
                        get_llm_config(),
                        SYSTEM_PROMPT,
                        prompt,
                        self.temperature,
                        160,
                    ),
                )
                proc.start()
                proc.join(self.hard_timeout_s)
                if proc.is_alive():
                    proc.terminate()
                    proc.join()
                    raise TimeoutError(f"zero-shot hard timeout after {self.hard_timeout_s}s")
                result = queue.get_nowait() if not queue.empty() else {"ok": False, "error": "empty llm response"}
                if not result.get("ok"):
                    raise RuntimeError(result.get("error") or "unknown llm error")
                usage = result.get("usage")
                payload = _extract_json_object(result.get("content") or "")
                candidate = self._coerce_candidate(session.task, payload)
            except Exception as exc:
                model_error = f"{type(exc).__name__}: {exc}"
                candidate = self._default_candidate(session.task)
            api_wall_time_s = round(time.perf_counter() - api_started, 6)
            candidate = self.ensure_unique(session, candidate, rng)
            prior_candidates.append(candidate)
            record = session.evaluate(
                candidate,
                metadata={
                    "strategy": "zero_shot_llm",
                    "solver_wall_time_s": api_wall_time_s,
                    "model": self.config["model"],
                    "model_error": model_error,
                    "usage": usage,
                },
            )
            if record["interaction"]["response"]["is_feasible"]:
                break
