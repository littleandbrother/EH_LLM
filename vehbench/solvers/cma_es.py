from __future__ import annotations

import math

import numpy as np

from .base import BaseSolver
from ..eval.runtime import candidate_to_unit, initial_candidate, ordered_variable_keys, unit_to_candidate


class CmaEsSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="cma_es", base_seed=seed)

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        dim = len(ordered_variable_keys(session.task))
        population_size = max(4, min(session.remaining, 4 + int(3 * math.log(max(dim, 2)))))
        mu = max(2, population_size // 2)
        weights = np.log(mu + 0.5) - np.log(np.arange(1, mu + 1))
        weights = weights / np.sum(weights)

        seed_candidate = initial_candidate(session.task)
        mean = (
            np.array(candidate_to_unit(session.task, seed_candidate), dtype=float)
            if seed_candidate is not None
            else self.unit_midpoint(session.task)
        )
        sigma = 0.18
        diag_cov = np.ones(dim, dtype=float)
        best_score = None

        while not session.exhausted:
            batch = min(population_size, session.remaining)
            candidates: list[tuple[float, np.ndarray]] = []
            for _ in range(batch):
                step = rng.normal(0.0, 1.0, size=dim) * np.sqrt(diag_cov)
                genome = np.clip(mean + sigma * step, 0.0, 1.0)
                candidate = self.ensure_unique(
                    session,
                    unit_to_candidate(session.task, genome.tolist()),
                    rng,
                )
                record = session.evaluate(candidate, metadata={"strategy": "cma_es"})
                genome = np.array(candidate_to_unit(session.task, candidate), dtype=float)
                candidates.append((record["score"], genome))

            if not candidates:
                break

            candidates.sort(key=lambda item: item[0], reverse=True)
            effective_mu = min(mu, len(candidates))
            effective_weights = weights[:effective_mu]
            effective_weights = effective_weights / np.sum(effective_weights)
            top = np.array([genome for _, genome in candidates[:effective_mu]])
            top_scores = [score for score, _ in candidates[:effective_mu]]
            old_mean = mean.copy()
            mean = np.sum(top * effective_weights[:, None], axis=0)
            centered = top - old_mean
            diag_cov = 0.85 * diag_cov + 0.15 * np.average(centered**2, axis=0, weights=effective_weights)
            generation_best = top_scores[0]
            if best_score is None or generation_best > best_score:
                sigma = min(0.35, sigma * 1.05)
                best_score = generation_best
            else:
                sigma = max(0.03, sigma * 0.92)
