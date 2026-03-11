from __future__ import annotations

import numpy as np

from .base import BaseSolver
from ..eval.runtime import clamp_candidate, initial_candidate, ordered_variable_keys, unit_to_candidate


class RandomSearchSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="random_search", base_seed=seed)

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        seed_candidate = initial_candidate(session.task)
        if seed_candidate is not None and not session.exhausted:
            session.evaluate(seed_candidate, metadata={"strategy": "initial_candidate"})

        dim = len(ordered_variable_keys(session.task))
        startup = [self.unit_midpoint(session.task)]
        startup.extend(self.latin_hypercube(rng, min(6, session.remaining), session.task))
        for genome in startup:
            if session.exhausted:
                break
            candidate = self.ensure_unique(
                session,
                unit_to_candidate(session.task, genome.tolist()),
                rng,
            )
            session.evaluate(candidate, metadata={"strategy": "space_filling_start"})

        while not session.exhausted:
            candidate = unit_to_candidate(session.task, rng.uniform(0.0, 1.0, size=dim).tolist())
            candidate = self.ensure_unique(session, clamp_candidate(session.task, candidate), rng)
            session.evaluate(candidate, metadata={"strategy": "uniform_random"})
