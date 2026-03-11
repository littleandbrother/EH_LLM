from __future__ import annotations

from .bayesian_optimization import BayesianOptimizationSolver
from .cma_es import CmaEsSolver
from .genetic_algorithm import GeneticAlgorithmSolver
from .random_search import RandomSearchSolver

CLASSICAL_SOLVERS = (
    "random_search",
    "genetic_algorithm",
    "cma_es",
    "bayesian_optimization",
)

AVAILABLE_SOLVERS = CLASSICAL_SOLVERS + ("zero_shot_llm", "verifier_guided_llm")


def build_solver(name: str, seed: int = 0):
    if name == "random_search":
        return RandomSearchSolver(seed=seed)
    if name == "genetic_algorithm":
        return GeneticAlgorithmSolver(seed=seed)
    if name == "cma_es":
        return CmaEsSolver(seed=seed)
    if name == "bayesian_optimization":
        return BayesianOptimizationSolver(seed=seed)
    if name == "zero_shot_llm":
        from .zero_shot_llm import ZeroShotLlmSolver

        return ZeroShotLlmSolver(seed=seed)
    if name == "verifier_guided_llm":
        from .verifier_guided_llm import VerifierGuidedLlmSolver

        return VerifierGuidedLlmSolver(seed=seed)
    raise ValueError(f"unknown solver: {name}")
