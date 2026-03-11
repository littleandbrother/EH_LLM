from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ..eval.runtime import (
    clamp_candidate,
    candidate_to_unit,
    initial_candidate,
    midpoint_candidate,
    ordered_variable_keys,
    unit_to_candidate,
)


@dataclass
class BaseSolver:
    name: str
    base_seed: int = 0

    def solve(self, session, task_seed: int) -> None:
        raise NotImplementedError

    def rng(self, task_seed: int) -> np.random.Generator:
        return np.random.default_rng(self.base_seed + task_seed)

    def midpoint(self, task: dict) -> dict:
        return midpoint_candidate(task)

    def unit_midpoint(self, task: dict) -> np.ndarray:
        return np.array(candidate_to_unit(task, midpoint_candidate(task)), dtype=float)

    def task_initial_candidate(self, task: dict) -> dict | None:
        return initial_candidate(task)

    def ensure_unique(self, session, candidate: dict, rng: np.random.Generator) -> dict:
        candidate = clamp_candidate(session.task, candidate)
        if not session.has_seen(candidate):
            return candidate
        for _ in range(8):
            jitter = rng.normal(0.0, 0.03, size=len(ordered_variable_keys(session.task)))
            unit = np.array(candidate_to_unit(session.task, candidate), dtype=float)
            candidate = unit_to_candidate(session.task, np.clip(unit + jitter, 0.0, 1.0).tolist())
            candidate = clamp_candidate(session.task, candidate)
            if not session.has_seen(candidate):
                return candidate
        return candidate

