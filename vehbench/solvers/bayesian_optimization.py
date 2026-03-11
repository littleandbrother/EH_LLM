from __future__ import annotations

import math

import numpy as np

from .base import BaseSolver
from ..eval.runtime import candidate_to_unit, initial_candidate, ordered_variable_keys, unit_to_candidate


def _rbf_kernel(x_a: np.ndarray, x_b: np.ndarray, length_scale: float = 0.22) -> np.ndarray:
    diff = x_a[:, None, :] - x_b[None, :, :]
    sqdist = np.sum(diff * diff, axis=2)
    return np.exp(-0.5 * sqdist / max(length_scale**2, 1e-12))


def _normal_pdf(z: np.ndarray) -> np.ndarray:
    return np.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)


def _normal_cdf(z: np.ndarray) -> np.ndarray:
    erf = np.vectorize(math.erf)
    return 0.5 * (1.0 + erf(z / math.sqrt(2.0)))


class BayesianOptimizationSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="bayesian_optimization", base_seed=seed)

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        dim = len(ordered_variable_keys(session.task))
        observed_x: list[np.ndarray] = []
        observed_y: list[float] = []

        starters: list[np.ndarray] = []
        seed_candidate = initial_candidate(session.task)
        if seed_candidate is not None:
            starters.append(np.array(candidate_to_unit(session.task, seed_candidate), dtype=float))
        starters.append(self.unit_midpoint(session.task))
        initial_count = min(max(4, dim + 1), session.budget)
        while len(starters) < initial_count:
            starters.append(rng.uniform(0.0, 1.0, size=dim))

        for genome in starters:
            if session.exhausted:
                break
            candidate = self.ensure_unique(
                session,
                unit_to_candidate(session.task, genome.tolist()),
                rng,
            )
            record = session.evaluate(candidate, metadata={"strategy": "bo_init"})
            observed_x.append(np.array(candidate_to_unit(session.task, candidate), dtype=float))
            observed_y.append(record["score"])

        while not session.exhausted and observed_x:
            x = np.vstack(observed_x)
            y = np.array(observed_y, dtype=float)
            y_mean = float(np.mean(y))
            y_std = float(np.std(y))
            y_scaled = (y - y_mean) / max(y_std, 1e-9)

            try:
                kernel = _rbf_kernel(x, x) + np.eye(len(x)) * 1e-6
                kernel_inv = np.linalg.inv(kernel)
            except np.linalg.LinAlgError:
                pool = rng.uniform(0.0, 1.0, size=(128, dim))
                next_genome = pool[rng.integers(0, len(pool))]
            else:
                pool = rng.uniform(0.0, 1.0, size=(192, dim))
                cross_kernel = _rbf_kernel(pool, x)
                mu = cross_kernel @ kernel_inv @ y_scaled
                var = 1.0 - np.sum((cross_kernel @ kernel_inv) * cross_kernel, axis=1)
                sigma = np.sqrt(np.maximum(var, 1e-9))
                best = float(np.max(y_scaled))
                z = (mu - best) / sigma
                acquisition = (mu - best) * _normal_cdf(z) + sigma * _normal_pdf(z)
                next_genome = pool[int(np.argmax(acquisition))]

            candidate = self.ensure_unique(
                session,
                unit_to_candidate(session.task, next_genome.tolist()),
                rng,
            )
            record = session.evaluate(candidate, metadata={"strategy": "bo_ei"})
            observed_x.append(np.array(candidate_to_unit(session.task, candidate), dtype=float))
            observed_y.append(record["score"])

