from __future__ import annotations

import numpy as np

from .base import BaseSolver
from ..eval.runtime import candidate_to_unit, initial_candidate, ordered_variable_keys, unit_to_candidate


class GeneticAlgorithmSolver(BaseSolver):
    def __init__(self, seed: int = 0) -> None:
        super().__init__(name="genetic_algorithm", base_seed=seed)

    def solve(self, session, task_seed: int) -> None:
        rng = self.rng(task_seed)
        dim = len(ordered_variable_keys(session.task))
        population_size = max(6, min(12, session.budget))
        elite_count = max(2, population_size // 4)

        population: list[np.ndarray] = []
        seed_candidate = initial_candidate(session.task)
        if seed_candidate is not None:
            population.append(np.array(candidate_to_unit(session.task, seed_candidate), dtype=float))
        population.append(self.unit_midpoint(session.task))
        while len(population) < population_size:
            population.append(rng.uniform(0.0, 1.0, size=dim))

        scored_population: list[tuple[float, np.ndarray]] = []
        while population and not session.exhausted:
            genome = population.pop(0)
            candidate = self.ensure_unique(
                session,
                unit_to_candidate(session.task, genome.tolist()),
                rng,
            )
            record = session.evaluate(candidate, metadata={"strategy": "population_init"})
            scored_population.append((record["score"], np.array(candidate_to_unit(session.task, candidate), dtype=float)))

        while not session.exhausted and scored_population:
            scored_population.sort(key=lambda item: item[0], reverse=True)
            elites = [genome for _, genome in scored_population[:elite_count]]
            next_population: list[np.ndarray] = list(elites)
            while len(next_population) < population_size:
                parent_a = elites[rng.integers(0, len(elites))]
                parent_b = elites[rng.integers(0, len(elites))]
                alpha = rng.uniform(0.25, 0.75, size=dim)
                child = alpha * parent_a + (1.0 - alpha) * parent_b
                mutation_mask = rng.uniform(0.0, 1.0, size=dim) < 0.45
                child = np.clip(child + mutation_mask * rng.normal(0.0, 0.08, size=dim), 0.0, 1.0)
                next_population.append(child)

            scored_population = []
            for genome in next_population:
                if session.exhausted:
                    break
                candidate = self.ensure_unique(
                    session,
                    unit_to_candidate(session.task, genome.tolist()),
                    rng,
                )
                record = session.evaluate(candidate, metadata={"strategy": "ga_generation"})
                scored_population.append((record["score"], np.array(candidate_to_unit(session.task, candidate), dtype=float)))

