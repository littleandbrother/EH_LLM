# Repeated OOD Benchmark Summary

We repeat the most discriminative OOD evaluations over seeds `7, 17, 27` to estimate result stability.

## Frequency Matching / test-ood

| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |
|---|---:|---:|---:|---:|
| random_search | 0.467±0.058 | 2.633±0.513 | 0.316±0.018 | 0.001±0.001 |
| genetic_algorithm | 0.433±0.058 | 3.300±1.212 | 0.339±0.012 | 0.004±0.005 |
| cma_es | 0.367±0.115 | 8.378±3.862 | 0.268±0.041 | 0.001±0.001 |
| bayesian_optimization | 0.600±0.000 | 5.222±0.585 | 0.340±0.004 | 0.001±0.000 |
| zero_shot_llm | 0.233±0.153 | 1.000±0.000 | 0.121±0.038 | 2.945±0.347 |
| verifier_guided_llm | 0.600±0.000 | 7.111±0.096 | 0.267±0.010 | 10.259±2.289 |

## Feasibility Repair / test-ood

| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |
|---|---:|---:|---:|---:|
| random_search | 0.583±0.072 | 4.233±0.666 | 0.792±0.036 | 0.000±0.000 |
| genetic_algorithm | 0.542±0.072 | 3.333±0.629 | 0.771±0.036 | 0.000±0.000 |
| cma_es | 0.083±0.072 | 6.500±7.778 | 0.542±0.036 | 0.000±0.000 |
| bayesian_optimization | 0.667±0.072 | 5.756±0.844 | 0.833±0.036 | 0.000±0.000 |
| zero_shot_llm | 0.000±0.000 | - | 0.500±0.000 | 2.862±0.210 |
| scalar_reward_llm | 0.042±0.072 | 4.000±0.000 | 0.521±0.036 | 15.469±1.480 |
| verifier_guided_llm | 0.708±0.072 | 9.144±0.479 | 0.854±0.036 | 10.118±0.668 |

## Takeaways

- BO remains the strongest classical OOD baseline.
- Verifier-guided Kimi matches BO on frequency OOD (`0.600±0.000`) and slightly exceeds it on repair OOD (`0.708±0.072` vs `0.667±0.072`).
- Zero-shot Kimi remains unstable and weak on OOD, especially on repair.
