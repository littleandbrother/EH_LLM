from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, field
from pathlib import Path

from ..verifier.v1.calibration import load_frequency_profile
from ..verifier.v1.evaluator import evaluate_request

LOG_SCALE_KEYS = {"load_resistance_ohm"}


def ordered_variable_keys(task: dict) -> tuple[str, ...]:
    return tuple((task.get("variable_bounds") or {}).keys())


def load_tasks(
    tasks_file: str | Path,
    task_type: str | None = None,
    split: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    tasks: list[dict] = []
    with Path(tasks_file).open() as handle:
        for line in handle:
            task = json.loads(line)
            if task_type and task.get("task_type") != task_type:
                continue
            if split and (task.get("split") or {}).get("name") != split:
                continue
            tasks.append(task)
            if limit is not None and len(tasks) >= limit:
                break
    return tasks


def _bound_config(task: dict, key: str) -> dict:
    return dict((task.get("variable_bounds") or {})[key])


def _uses_log_scale(task: dict, key: str) -> bool:
    if key not in LOG_SCALE_KEYS:
        return False
    bound = _bound_config(task, key)
    low = float(bound["min"])
    high = float(bound["max"])
    return low > 0 and high / low >= 50.0


def midpoint_candidate(task: dict) -> dict:
    candidate = {}
    for key in ordered_variable_keys(task):
        bound = _bound_config(task, key)
        candidate[key] = (float(bound["min"]) + float(bound["max"])) / 2.0
    return candidate


def clamp_candidate(task: dict, candidate: dict) -> dict:
    clamped = {}
    for key in ordered_variable_keys(task):
        bound = _bound_config(task, key)
        value = candidate.get(key)
        if value is None:
            value = (float(bound["min"]) + float(bound["max"])) / 2.0
        value = float(value)
        clamped[key] = min(float(bound["max"]), max(float(bound["min"]), value))
    return clamped


def candidate_to_unit(task: dict, candidate: dict) -> list[float]:
    values: list[float] = []
    for key in ordered_variable_keys(task):
        bound = _bound_config(task, key)
        low = float(bound["min"])
        high = float(bound["max"])
        value = float(candidate.get(key, (low + high) / 2.0))
        if _uses_log_scale(task, key):
            low_log = math.log(low)
            high_log = math.log(high)
            unit = (math.log(max(value, low)) - low_log) / max(high_log - low_log, 1e-12)
        else:
            unit = (value - low) / max(high - low, 1e-12)
        values.append(min(1.0, max(0.0, unit)))
    return values


def unit_to_candidate(task: dict, vector: list[float]) -> dict:
    candidate = {}
    for key, unit in zip(ordered_variable_keys(task), vector):
        bound = _bound_config(task, key)
        low = float(bound["min"])
        high = float(bound["max"])
        clipped = min(1.0, max(0.0, float(unit)))
        if _uses_log_scale(task, key):
            value = math.exp(math.log(low) + clipped * (math.log(high) - math.log(low)))
        else:
            value = low + clipped * (high - low)
        candidate[key] = float(value)
    return candidate


def initial_candidate(task: dict) -> dict | None:
    if task.get("task_type") != "feasibility_repair":
        return None
    seed = task.get("initial_candidate") or {}
    if not seed:
        return None
    return clamp_candidate(task, seed)


def build_request_from_task(task: dict, candidate: dict, candidate_id: str) -> dict:
    fixed = task.get("fixed_conditions") or {}
    hard = task.get("hard_constraints") or {}
    candidate = clamp_candidate(task, candidate)
    load_value = candidate.get("load_resistance_ohm")
    return {
        "task_id": task["task_id"],
        "candidate_id": candidate_id,
        "design_parameters": candidate,
        "material_parameters": {
            "structure_class": fixed.get("structure_class"),
            "piezo_material": fixed.get("piezo_material"),
            "substrate_material": fixed.get("substrate_material"),
        },
        "excitation_settings": {
            "excitation_type": fixed.get("excitation_type", "sinusoidal_base_excitation"),
            "frequency_hz": fixed.get("excitation_frequency_hz"),
            "acceleration_g": fixed.get("acceleration_g"),
            "base_displacement_mm": fixed.get("base_displacement_mm"),
            "motion_source": fixed.get("motion_source", "shaker"),
        },
        "load_settings": {
            "load_type": fixed.get("load_type", "resistive"),
            "load_resistance_ohm": load_value,
        },
        "constraint_context": {
            "target_resonant_frequency_hz": fixed.get("target_resonant_frequency_hz"),
            "stress_limit_mpa": hard.get("stress_limit_mpa"),
            "displacement_limit_mm": hard.get("displacement_limit_mm"),
            "power_target_uw": hard.get("power_target_uw"),
        },
    }


def latin_hypercube_units(rng, sample_count: int, dim: int) -> list[list[float]]:
    if sample_count <= 0:
        return []
    matrix = []
    for column in range(dim):
        perm = rng.permutation(sample_count)
        values = (perm + rng.uniform(0.0, 1.0, size=sample_count)) / sample_count
        matrix.append(values.tolist())
    return [[matrix[col][row] for col in range(dim)] for row in range(sample_count)]


def score_interaction(task: dict, interaction: dict) -> float:
    response = interaction["response"]
    outputs = response.get("outputs") or {}
    violations = response.get("violations") or []
    if not response.get("is_valid_request"):
        return -10.0 - len(violations)

    task_type = task.get("task_type")
    target_frequency = (task.get("fixed_conditions") or {}).get("target_resonant_frequency_hz")
    frequency = outputs.get("resonant_frequency_hz")
    frequency_score = 0.0
    if target_frequency is not None and frequency is not None:
        error_pct = abs(float(frequency) - float(target_frequency)) / max(abs(float(target_frequency)), 1e-9) * 100.0
        frequency_score = 1.0 / (1.0 + error_pct)

    if task_type == "frequency_matching":
        score = frequency_score
        if response.get("is_feasible"):
            score += 1.0
        return score - 0.02 * len(violations)

    if task_type == "constrained_power_maximization":
        score = float(response.get("normalized_objective") or 0.0)
        score += 0.2 * frequency_score
        if response.get("is_feasible"):
            score += 1.0
        return score - 0.05 * len(violations)

    if task_type == "feasibility_repair":
        score = 1.0 / (1.0 + len(violations))
        score += 0.5 * frequency_score
        if response.get("is_feasible"):
            score += 1.0
        return score

    score = response.get("normalized_objective")
    if score is None:
        score = -float(len(violations))
    return float(score)


@dataclass
class TaskSession:
    task: dict
    solver_name: str
    apply_frequency_calibration: bool = True
    use_task_anchors: bool = True
    calibration_profile: dict | None = None
    records: list[dict] = field(default_factory=list)
    _seen: set[tuple[float, ...]] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.calibration_profile is None and self.apply_frequency_calibration:
            self.calibration_profile = load_frequency_profile()

    @property
    def budget(self) -> int:
        return int((self.task.get("budget") or {}).get("max_queries") or 0)

    @property
    def remaining(self) -> int:
        return self.budget - len(self.records)

    @property
    def exhausted(self) -> bool:
        return self.remaining <= 0

    @property
    def best_record(self) -> dict | None:
        if not self.records:
            return None
        return max(self.records, key=lambda record: record["score"])

    def has_seen(self, candidate: dict) -> bool:
        key = tuple(round(float(candidate[name]), 8) for name in ordered_variable_keys(self.task))
        return key in self._seen

    def evaluate(self, candidate: dict, metadata: dict | None = None) -> dict:
        if self.exhausted:
            raise RuntimeError(f"query budget exhausted for {self.task['task_id']}")
        started = time.perf_counter()
        candidate = clamp_candidate(self.task, candidate)
        request = build_request_from_task(
            self.task,
            candidate,
            candidate_id=f"{self.task['task_id']}::{self.solver_name}::{len(self.records) + 1}",
        )
        interaction = evaluate_request(
            request,
            task=self.task if self.use_task_anchors else None,
            apply_frequency_calibration=self.apply_frequency_calibration,
            calibration_profile=self.calibration_profile,
        )
        score = score_interaction(self.task, interaction)
        key = tuple(round(float(candidate[name]), 8) for name in ordered_variable_keys(self.task))
        self._seen.add(key)
        record = {
            "task_id": self.task["task_id"],
            "task_type": self.task["task_type"],
            "split": (self.task.get("split") or {}).get("name"),
            "solver_name": self.solver_name,
            "query_index": len(self.records) + 1,
            "candidate": candidate,
            "score": score,
            "interaction": interaction,
            "wall_time_s": round(time.perf_counter() - started, 6),
            "metadata": metadata or {},
        }
        self.records.append(record)
        return record


def summarize_task_session(session: TaskSession) -> dict:
    best = session.best_record
    success_indices = [
        record["query_index"]
        for record in session.records
        if record["interaction"]["response"]["is_feasible"]
    ]
    invalid_count = sum(
        1 for record in session.records if not record["interaction"]["response"]["is_valid_request"]
    )
    return {
        "task_id": session.task["task_id"],
        "task_type": session.task["task_type"],
        "split": (session.task.get("split") or {}).get("name"),
        "solver_name": session.solver_name,
        "query_budget": session.budget,
        "queries_used": len(session.records),
        "success": bool(success_indices),
        "queries_to_success": success_indices[0] if success_indices else None,
        "invalid_proposal_rate": 0.0 if not session.records else invalid_count / len(session.records),
        "best_score": None if best is None else round(best["score"], 6),
        "best_normalized_objective": None
        if best is None
        else best["interaction"]["response"]["normalized_objective"],
        "best_objective_value": None if best is None else best["interaction"]["response"]["objective_value"],
        "best_candidate": None if best is None else best["candidate"],
        "best_response": None if best is None else best["interaction"]["response"],
        "total_wall_clock_s": round(sum(record["wall_time_s"] for record in session.records), 6),
    }
