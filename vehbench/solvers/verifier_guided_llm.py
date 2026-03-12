from __future__ import annotations

import json
import multiprocessing as mp
import os
import time
from typing import Any

import numpy as np

from .base import BaseSolver
from .zero_shot_llm import _extract_json_object, _llm_request_worker
from ..eval.runtime import (
    candidate_to_unit,
    clamp_candidate,
    initial_candidate,
    midpoint_candidate,
    ordered_variable_keys,
    unit_to_candidate,
)
from ..llm import get_llm_client, get_llm_config

SYSTEM_PROMPT = """Return JSON only.
You are repairing or improving a VEHBench design using verifier feedback.
Prioritize feasibility first, then objective quality.
Use exact variable names.
Keep any explanation extremely short.
Response format:
{"analysis_summary":"short","candidate":{"variable_name": number},"expected_effect":"short"}"""


class VerifierGuidedLlmSolver(BaseSolver):
    def __init__(self, seed: int = 0, feedback_mode: str = "structured", name: str | None = None) -> None:
        super().__init__(name=name or "verifier_guided_llm", base_seed=seed)
        self.client, self.config = get_llm_client()
        self.feedback_mode = feedback_mode
        self.temperature = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_TEMPERATURE", "0.0"))
        self.max_attempts = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_ATTEMPTS", "4"))
        self.hard_timeout_s = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_HARD_TIMEOUT_S", "15"))
        self.max_tokens = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_TOKENS", "220"))
        self.max_probe_keys = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_PROBE_KEYS", "4"))
        self.probe_step = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_PROBE_STEP", "0.12"))
        self.directional_scale = float(os.getenv("VEHBENCH_VERIFIER_GUIDED_DIRECTIONAL_SCALE", "1.8"))
        self.max_directional_dims = int(os.getenv("VEHBENCH_VERIFIER_GUIDED_MAX_DIRECTIONAL_DIMS", "2"))

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

    def _target_frequency(self, task: dict) -> float | None:
        fixed = task.get("fixed_conditions") or {}
        value = fixed.get("target_resonant_frequency_hz")
        return None if value is None else float(value)

    def _record_frequency(self, record: dict | None) -> float | None:
        if record is None:
            return None
        outputs = ((record.get("interaction") or {}).get("response") or {}).get("outputs") or {}
        value = outputs.get("resonant_frequency_hz")
        return None if value is None else float(value)

    def _frequency_gap(self, task: dict, frequency_hz: float | None) -> float | None:
        target = self._target_frequency(task)
        if target is None or frequency_hz is None:
            return None
        return abs(float(frequency_hz) - target)

    def _priority_probe_keys(self, task: dict) -> list[str]:
        available = set(ordered_variable_keys(task))
        priority = [
            "beam_length_mm",
            "tip_mass_g",
            "load_resistance_ohm",
            "substrate_thickness_um",
            "piezo_thickness_um",
            "beam_width_mm",
        ]
        ordered = [key for key in priority if key in available]
        ordered.extend([key for key in ordered_variable_keys(task) if key not in ordered])
        return ordered[: self.max_probe_keys]

    def _shift_candidate(self, task: dict, candidate: dict, key: str, unit_delta: float) -> dict:
        unit = np.array(candidate_to_unit(task, candidate), dtype=float)
        keys = ordered_variable_keys(task)
        index = keys.index(key)
        unit[index] = float(np.clip(unit[index] + unit_delta, 0.0, 1.0))
        shifted = unit_to_candidate(task, unit.tolist())
        return clamp_candidate(task, shifted)

    def _probe_rank(self, probe: dict) -> tuple[float, float, float]:
        feasible_bonus = 1.0 if probe.get("feasible") else 0.0
        gap_improvement = float(probe.get("gap_improvement_hz") or 0.0)
        score = float(probe.get("score") or 0.0)
        return feasible_bonus, gap_improvement, score

    def _compact_probe_summary(self, probe: dict) -> dict[str, Any]:
        summary = {
            "key": probe["key"],
            "direction": probe["direction_label"],
            "freq_hz": probe.get("frequency_hz"),
            "freq_delta_hz": probe.get("frequency_delta_hz"),
            "gap_improvement_hz": probe.get("gap_improvement_hz"),
            "violations": probe.get("violations"),
            "feasible": probe.get("feasible"),
        }
        if probe.get("solver_feedback"):
            summary["feedback"] = probe["solver_feedback"]
        return summary

    def _initial_local_probe_scan(self, session, base_record: dict, rng: np.random.Generator) -> list[dict[str, Any]]:
        if session.exhausted:
            return []
        base_candidate = base_record["candidate"]
        base_frequency = self._record_frequency(base_record)
        base_gap = self._frequency_gap(session.task, base_frequency)
        probe_summaries: list[dict[str, Any]] = []

        for key in self._priority_probe_keys(session.task):
            for direction_sign, direction_label in ((-1.0, "down"), (1.0, "up")):
                if session.exhausted:
                    break
                candidate = self._shift_candidate(session.task, base_candidate, key, direction_sign * self.probe_step)
                if all(abs(float(candidate[name]) - float(base_candidate[name])) <= 1e-9 for name in ordered_variable_keys(session.task)):
                    continue
                candidate = self.ensure_unique(session, candidate, rng)
                if session.has_seen(candidate):
                    continue
                record = session.evaluate(
                    candidate,
                    metadata={
                        "strategy": "verifier_guided_local_probe",
                        "probe_key": key,
                        "probe_direction": direction_label,
                    },
                )
                frequency_hz = self._record_frequency(record)
                gap = self._frequency_gap(session.task, frequency_hz)
                response = (record.get("interaction") or {}).get("response") or {}
                diagnostics = response.get("diagnostics") or {}
                probe_summaries.append(
                    {
                        "key": key,
                        "direction_sign": direction_sign,
                        "direction_label": direction_label,
                        "candidate": record["candidate"],
                        "frequency_hz": frequency_hz,
                        "frequency_delta_hz": None if frequency_hz is None or base_frequency is None else round(frequency_hz - base_frequency, 6),
                        "gap_improvement_hz": None if gap is None or base_gap is None else round(base_gap - gap, 6),
                        "violations": response.get("violations") or [],
                        "feasible": bool(response.get("is_feasible")),
                        "score": record["score"],
                        "solver_feedback": diagnostics.get("solver_visible_message"),
                    }
                )
                if response.get("is_feasible"):
                    break
            if session.best_record and session.best_record["interaction"]["response"]["is_feasible"]:
                break

        probe_summaries.sort(key=self._probe_rank, reverse=True)
        return probe_summaries

    def _directional_search(self, session, base_record: dict, probe_summaries: list[dict[str, Any]], rng: np.random.Generator) -> dict[str, Any] | None:
        if session.exhausted or not probe_summaries:
            return None
        selected: list[dict[str, Any]] = []
        for probe in probe_summaries:
            if (probe.get("gap_improvement_hz") or 0.0) <= 0.0:
                continue
            if any(existing["key"] == probe["key"] for existing in selected):
                continue
            selected.append(probe)
            if len(selected) >= self.max_directional_dims:
                break
        if not selected:
            return None

        unit = np.array(candidate_to_unit(session.task, base_record["candidate"]), dtype=float)
        keys = ordered_variable_keys(session.task)
        applied_moves: list[dict[str, Any]] = []
        for probe in selected:
            index = keys.index(probe["key"])
            bound_target = 0.0 if probe["direction_sign"] < 0 else 1.0
            unit[index] = float(np.clip(unit[index] + self.directional_scale * (bound_target - unit[index]), 0.0, 1.0))
            applied_moves.append(
                {
                    "key": probe["key"],
                    "direction": probe["direction_label"],
                    "source_gap_improvement_hz": probe.get("gap_improvement_hz"),
                }
            )
        candidate = unit_to_candidate(session.task, unit.tolist())
        candidate = self.ensure_unique(session, candidate, rng)
        if session.has_seen(candidate):
            return None
        record = session.evaluate(
            candidate,
            metadata={
                "strategy": "verifier_guided_directional_search",
                "applied_moves": applied_moves,
            },
        )
        response = (record.get("interaction") or {}).get("response") or {}
        diagnostics = response.get("diagnostics") or {}
        return {
            "candidate": record["candidate"],
            "feasible": bool(response.get("is_feasible")),
            "violations": response.get("violations") or [],
            "frequency_hz": self._record_frequency(record),
            "normalized_objective": response.get("normalized_objective"),
            "feedback": diagnostics.get("solver_visible_message"),
            "applied_moves": applied_moves,
        }

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

    def _build_prompt(
        self,
        session,
        attempt_index: int,
        local_probe_summaries: list[dict[str, Any]] | None = None,
        directional_summary: dict[str, Any] | None = None,
    ) -> str:
        task = session.task
        fixed_conditions = task.get("fixed_conditions") or {}
        hard_constraints = task.get("hard_constraints") or {}
        last_record = session.records[-1]
        best_record = session.best_record or last_record

        def summarize(record: dict) -> dict:
            response = record["interaction"]["response"]
            diagnostics = response.get("diagnostics") or {}
            payload = {
                "candidate": record["candidate"],
                "feasible": response.get("is_feasible"),
                "normalized_objective": response.get("normalized_objective"),
            }
            if self.feedback_mode == "structured":
                payload["violations"] = response.get("violations") or []
                payload["feedback"] = diagnostics.get("solver_visible_message")
            return payload

        payload = {
            "task": task["task_type"],
            "feedback_mode": self.feedback_mode,
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
        if task.get("task_type") == "feasibility_repair":
            payload["goal"] = "Repair the current design to satisfy the frequency constraint."
        else:
            payload["goal"] = "Use verifier feedback to improve the design and match target_hz."

        if len(session.records) > 1:
            payload["recent"] = [summarize(record) for record in session.records[-2:]]
        if self.feedback_mode == "structured":
            last_violations = ((last_record.get("interaction") or {}).get("response") or {}).get("violations") or []
            if "frequency_too_low" in last_violations:
                payload["repair_direction"] = "increase_resonant_frequency_hz"
            elif "frequency_too_high" in last_violations:
                payload["repair_direction"] = "decrease_resonant_frequency_hz"
            trend_hint = self._trend_hint(session)
            if trend_hint is not None:
                payload["trend_hint"] = trend_hint
            if local_probe_summaries:
                payload["local_probes"] = [self._compact_probe_summary(probe) for probe in local_probe_summaries[:4]]
                payload["agent_rule"] = (
                    "Prefer directions that empirically reduced |resonant_frequency_hz-target_hz| in local_probes. "
                    "Avoid repeating moves that worsened the gap."
                )
            if directional_summary is not None:
                payload["latest_directional_search"] = directional_summary
        else:
            payload["agent_rule"] = (
                "You only observe scalar reward and feasibility. Improve reward while staying in bounds. "
                "No structured violation labels are available."
            )
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

        local_probe_summaries = []
        if self.feedback_mode == "structured":
            local_probe_summaries = self._initial_local_probe_scan(session, bootstrap_record, rng)
            if session.best_record and session.best_record["interaction"]["response"]["is_feasible"]:
                return
        directional_summary = None

        llm_attempt_index = 0
        while not session.exhausted and llm_attempt_index < self.max_attempts:
            prompt = self._build_prompt(
                session,
                attempt_index=llm_attempt_index + 1,
                local_probe_summaries=local_probe_summaries,
                directional_summary=directional_summary,
            )
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
            llm_attempt_index += 1
            if record["interaction"]["response"]["is_feasible"]:
                break
            if self.feedback_mode == "structured":
                directional_summary = self._directional_search(
                    session,
                    base_record=session.best_record or record,
                    probe_summaries=local_probe_summaries,
                    rng=rng,
                )
                if session.best_record and session.best_record["interaction"]["response"]["is_feasible"]:
                    break
