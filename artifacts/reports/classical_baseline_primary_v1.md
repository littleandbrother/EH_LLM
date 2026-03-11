# Classical Baseline Primary Results (v1)

Benchmark runtime mode:

- calibrated frequency: `on`
- task-local anchors: `off`
- solver suite: `Random Search`, `GA`, `CMA-ES`, `BO`

Task difficulty audit after regeneration:

- `frequency_matching` midpoint feasible: `9 / 55`
- `constrained_power_maximization` midpoint feasible: `0 / 55`
- `feasibility_repair` initial candidate feasible: `0 / 52`

## frequency_matching / test-id

- run dir: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-id_all_20260311_155132_113319`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate |
|---|---:|---:|---:|---:|
| random_search | 1.000 | 2.75 | 0.780 | 0.000 |
| genetic_algorithm | 1.000 | 2.62 | 0.745 | 0.000 |
| cma_es | 1.000 | 13.12 | 0.475 | 0.000 |
| bayesian_optimization | 1.000 | 3.38 | 0.837 | 0.000 |

## frequency_matching / test-ood

- run dir: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-ood_all_20260311_155132_227910`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate |
|---|---:|---:|---:|---:|
| random_search | 0.500 | 2.20 | 0.337 | 0.200 |
| genetic_algorithm | 0.500 | 4.40 | 0.338 | 0.200 |
| cma_es | 0.300 | 5.67 | 0.223 | 0.200 |
| bayesian_optimization | 0.600 | 5.83 | 0.345 | 0.200 |

## feasibility_repair / test-id

- run dir: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-id_all_20260311_155132_244915`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate |
|---|---:|---:|---:|---:|
| random_search | 1.000 | 3.75 | 1.000 | 0.000 |
| genetic_algorithm | 1.000 | 3.75 | 1.000 | 0.000 |
| cma_es | 1.000 | 3.50 | 1.000 | 0.000 |
| bayesian_optimization | 1.000 | 4.38 | 1.000 | 0.000 |

## feasibility_repair / test-ood

- run dir: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-ood_all_20260311_155132_909356`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate |
|---|---:|---:|---:|---:|
| random_search | 0.625 | 4.80 | 0.812 | 0.000 |
| genetic_algorithm | 0.500 | 2.75 | 0.750 | 0.000 |
| cma_es | 0.625 | 6.00 | 0.812 | 0.000 |
| bayesian_optimization | 0.750 | 6.33 | 0.875 | 0.000 |

## Interpretation

- `frequency_matching / test-id` is now solvable but no longer one-step trivial; BO currently has the best normalized objective, while CMA-ES is much less query-efficient.
- `frequency_matching / test-ood` now shows real separation: BO is strongest, CMA-ES is weakest, and all solvers degrade relative to ID.
- `feasibility_repair / test-id` is still comparatively easy; all four classical solvers eventually repair all 8 tasks.
- `feasibility_repair / test-ood` shows useful spread: BO is best, GA is weakest, and success is no longer saturated.

Immediate implication:

- keep the current `frequency-first / no-task-anchor` runtime policy for baseline comparison
- use the OOD splits as the main discriminative benchmark view in the next report draft
- consider one more round of repair-task hardening on ID if stronger separation is needed
