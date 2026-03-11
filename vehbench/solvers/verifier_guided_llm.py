from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from typing import Any

from .base import BaseSolver
from .zero_shot_llm import _extract_json_object, _llm_request_worker
from ..eval.runtime import clamp_candidate, initial_candidate, midpoint_candidate, ordered_variable_keys
from ..llm import get_llm_client, get_llm_config

SYSTEM_PROMPT = """Return JSON only.
You are repairing or improving a VEHBench design using verifier feedback.
Prioritize feasibility first, then objective quality.
Use exact variable names.
Keep any explanation extremely short.
Response format:
{"analysis_summary":"short","candidate":{"variable_name": number},"expected_effect":"short"}"""


class VerifierGuidedLlmSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="verifier_guided_llm", base_seed=seed)
        self.client, self.config = get_llm_client()
        self.temperature = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_TEMPERATURE", "0.0"))
        self.max_attempts = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_ATTEMPTS", "4"))
        self.hard_timeout_s = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_HARD_TIMEOUT_S", "15"))
        self.max_tokens = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_TOKENS", "220"))

    def _default_candidate(self, task: dict) -> dict:
        if task.get("task_type") == "feasibility_repair":
            seed_candidate = initial_candidate(task)
            if seed_candidate is not None:
                return seed_candidate
        return midpoint_candidate(task)

    def _coerce_candidate(self, task: dict, payload: dict[str, Any], fallback: dict) -> dict:
        candidate = dict(fallback)
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

    def _trend_hint(self, session) -> str | None:
        if len(session.records) < 2:
            return None
        target = (session.task.get("fixed_conditions") or {}).get("target_resonant_frequency_hz")
        if target is None:
            return None
        first = session.records[0]
        last = session.records[-1]
        first_freq = ((first.get("interaction") or {}).get("response") or {}).get("outputs", {}).get("resonant_frequency_hz")
        last_freq = ((last.get("interaction") or {}).get("response") or {}).get("outputs", {}).get("resonant_frequency_hz")
        if first_freq is None or last_freq is None:
            return None
        changed = []
        for key in ordered_variable_keys(session.task):
            old = float(first["candidate"][key])
            new = float(last["candidate"][key])
            if abs(new - old) > 1e-9:
                changed.append(f"{key}:{old:.4g}->{new:.4g}")
        if not changed:
            return None
        return (
            f"From the first tried candidate to the latest one, "
            f"resonant_frequency_hz changed {first_freq:.4f}->{last_freq:.4f} "
            f"with target {float(target):.4f}. "
            f"Changed variables: {', '.join(changed[:4])}. "
            f"If the same violation persists, do not only repeat the same directional move."
        )

    def _build_prompt(self, session, attempt_index: int) -> str:
        task = session.task
        fixed_conditions = task.get("fixed_conditions") or {}
        hard_constraints = task.get("hard_constraints") or {}
        last_record = session.records[-1]
        best_record = session.best_record or last_record

        def summarize(record: dict) -> dict:
            response = record["interaction"]["response"]
            diagnostics = response.get("diagnostics") or {}
            return {
                "candidate": record["candidate"],
                "feasible": response.get("is_feasible"),
                "violations": response.get("violations") or [],
                "normalized_objective": response.get("normalized_objective"),
                "feedback": diagnostics.get("solver_visible_message"),
            }

        payload = {
            "task": task["task_type"],
            "attempt": attempt_index,
            "bounds": {
                key: [value.get("min"), value.get("max"), value.get("unit")]
                for key, value in (task.get("variable_bounds") or {}).items()
            },
            "target_hz": fixed_conditions.get("target_resonant_frequency_hz"),
            "excitation_hz": fixed_conditions.get("excitation_frequency_hz"),
            "accel_g": fixed_conditions.get("acceleration_g"),
            "freq_tol_pct": hard_constraints.get("frequency_error_tolerance_pct"),
            "current": summarize(last_record),
            "best": summarize(best_record),
        }
        last_violations = ((last_record.get("interaction") or {}).get("response") or {}).get("violations") or []
        if "frequency_too_low" in last_violations:
            payload["repair_direction"] = "increase_resonant_frequency_hz"
        elif "frequency_too_high" in last_violations:
            payload["repair_direction"] = "decrease_resonant_frequency_hz"
        if task.get("task_type") == "feasibility_repair":
            payload["goal"] = "Repair the current design to satisfy the frequency constraint."
        else:
            payload["goal"] = "Use verifier feedback to improve the design and match target_hz."

        if len(session.records) > 1:
            payload["recent"] = [summarize(record) for record in session.records[-2:]]
        trend_hint = self._trend_hint(session)
        if trend_hint is not None:
            payload["trend_hint"] = trend_hint
        return json.dumps(payload, ensure_ascii=True, separators=(",", ":"))

    def _call_llm(self, prompt: str) -> tuple[dict[str, Any], dict | None, str | None, float]:
        api_started = time.perf_counter()
        payload: dict[str, Any] = {}
        usage = None
        model_error = None
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
                    self.max_tokens,
                ),
            )
            proc.start()
            proc.join(self.hard_timeout_s)
            if proc.is_alive():
                proc.terminate()
                proc.join()
                raise TimeoutError(f"verifier-guided hard timeout after {self.hard_timeout_s}s")
            result = queue.get_nowait() if not queue.empty() else {"ok": False, "error": "empty llm response"}
            if not result.get("ok"):
                raise RuntimeError(result.get("error") or "unknown llm error")
            usage = result.get("usage")
            payload = _extract_json_object(result.get("content") or "")
        except Exception as exc:
            model_error = f"{type(exc).__name__}: {exc}"
        api_wall_time_s = round(time.perf_counter() - api_started, 6)
        return payload, usage, model_error, api_wall_time_s

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        bootstrap = self.ensure_unique(session, self._default_candidate(session.task), rng)
        bootstrap_record = session.evaluate(
            bootstrap,
            metadata={"strategy": "verifier_guided_bootstrap"},
        )
        if bootstrap_record["interaction"]["response"]["is_feasible"]:
            return

        while not session.exhausted and len(session.records) < min(session.budget, self.max_attempts + 1):
            prompt = self._build_prompt(session, attempt_index=len(session.records))
            payload, usage, model_error, api_wall_time_s = self._call_llm(prompt)
            fallback = session.best_record["candidate"] if session.best_record is not None else bootstrap
            candidate = self._coerce_candidate(session.task, payload, fallback=fallback)
            candidate = self.ensure_unique(session, candidate, rng)
            record = session.evaluate(
                candidate,
                metadata={
                    "strategy": "verifier_guided_llm",
                    "solver_wall_time_s": api_wall_time_s,
                    "analysis_summary": payload.get("analysis_summary"),
                    "expected_effect": payload.get("expected_effect"),
                    "model": self.config["model"],
                    "model_error": model_error,
                    "usage": usage,
                },
            )
            if record["interaction"]["response"]["is_feasible"]:
                break
