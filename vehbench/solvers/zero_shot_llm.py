from __future__ import annotations

import json
import os
import re
from typing import Any

from .base import BaseSolver
from ..eval.runtime import clamp_candidate, initial_candidate, midpoint_candidate, ordered_variable_keys
from ..llm import get_llm_client

SYSTEM_PROMPT = """You are solving a structured vibration energy harvester inverse-design task.

Rules:
- Return JSON only.
- Propose one candidate design within the provided variable bounds.
- Prioritize feasibility first, then objective quality.
- Do not reference hidden verifier outputs.
- Use the exact variable names from the task schema.

Response schema:
{
  "analysis_summary": "short rationale",
  "candidate": {
    "variable_name": numeric_value
  }
}
"""


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


class ZeroShotLlmSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="zero_shot_llm", base_seed=seed)
        self.client, self.config = get_llm_client()
        self.temperature = float(self.config.get("temperature", 0.0) or 0.0)
        self.max_attempts = int(os.getenv("VEHBENCH_ZERO_SHOT_MAX_ATTEMPTS", "6"))

    def _default_candidate(self, task: dict) -> dict:
        if task.get("task_type") == "feasibility_repair":
            seed_candidate = initial_candidate(task)
            if seed_candidate is not None:
                return seed_candidate
        return midpoint_candidate(task)

    def _prompt(self, task: dict, attempt_index: int, prior_candidates: list[dict]) -> str:
        variable_bounds = {
            key: {
                "min": value.get("min"),
                "max": value.get("max"),
                "unit": value.get("unit"),
            }
            for key, value in (task.get("variable_bounds") or {}).items()
        }
        fixed_conditions = task.get("fixed_conditions") or {}
        hard_constraints = task.get("hard_constraints") or {}
        objective = task.get("objective") or {}
        payload = {
            "task_id": task["task_id"],
            "task_type": task["task_type"],
            "attempt_index": attempt_index,
            "variable_bounds": variable_bounds,
            "target_resonant_frequency_hz": fixed_conditions.get("target_resonant_frequency_hz"),
            "excitation_frequency_hz": fixed_conditions.get("excitation_frequency_hz"),
            "acceleration_g": fixed_conditions.get("acceleration_g"),
            "load_type": fixed_conditions.get("load_type"),
            "frequency_error_tolerance_pct": hard_constraints.get("frequency_error_tolerance_pct"),
            "objective": {
                "name": objective.get("name"),
                "direction": objective.get("direction"),
                "target_value": objective.get("target_value"),
                "target_unit": objective.get("target_unit"),
            },
            "initial_candidate": task.get("initial_candidate"),
            "prior_candidates": prior_candidates[-2:],
        }
        if task.get("task_type") == "feasibility_repair":
            payload["instruction"] = (
                "Starting from the infeasible initial candidate, return one repaired candidate "
                "that moves resonance toward the target while staying within bounds."
            )
        return (
            "Solve the following VEHBench task.\n"
            "Return JSON only and keep `analysis_summary` to one sentence.\n\n"
            f"{json.dumps(payload, ensure_ascii=True, indent=2)}"
        )

    def _coerce_candidate(self, task: dict, payload: dict[str, Any]) -> dict:
        candidate = dict(self._default_candidate(task))
        proposed = payload.get("candidate") or {}
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
            response = self.client.chat.completions.create(
                model=self.config["model"],
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                temperature=self.temperature,
                max_tokens=400,
            )
            content = response.choices[0].message.content or ""
            payload = _extract_json_object(content)
            candidate = self._coerce_candidate(session.task, payload)
            candidate = self.ensure_unique(session, candidate, rng)
            prior_candidates.append(candidate)
            record = session.evaluate(
                candidate,
                metadata={
                    "strategy": "zero_shot_llm",
                    "analysis_summary": payload.get("analysis_summary"),
                    "model": self.config["model"],
                    "usage": None
                    if response.usage is None
                    else {
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens,
                    },
                },
            )
            if record["interaction"]["response"]["is_feasible"]:
                break
