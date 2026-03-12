# Structured Feedback Ablation

This report isolates whether the gain in repair performance comes from iterative LLM calls alone or from structured verifier feedback with local sensitivity probes and directional search.

## Single-Run Repair Comparison

### test-id

| Solver | Success Rate | Avg Queries Used | Avg Best Objective | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|
| zero_shot_llm | 0.125 | 1.000 | 0.562 | 3.017 |
| scalar_reward_llm | 0.000 | 4.000 | 0.500 | 13.764 |
| verifier_guided_llm | 1.000 | 9.125 | 1.000 | 6.115 |

### test-ood

| Solver | Success Rate | Avg Queries Used | Avg Best Objective | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|
| zero_shot_llm | 0.000 | 1.000 | 0.500 | 2.703 |
| scalar_reward_llm | 0.000 | 4.000 | 0.500 | 14.134 |
| verifier_guided_llm | 0.750 | 10.500 | 0.875 | 13.405 |

## Repeated OOD Stability (3 seeds)

| Solver | Success Rate (mean±std) | Queries To Success (mean±std) | Best Objective (mean±std) | Wall Clock (mean±std) |
|---|---:|---:|---:|---:|
| zero_shot_llm | 0.000±0.000 | - | 0.500±0.000 | 2.862±0.210 |
| scalar_reward_llm | 0.042±0.072 | 4.000±0.000 | 0.521±0.036 | 15.469±1.480 |
| verifier_guided_llm | 0.708±0.072 | 9.144±0.479 | 0.854±0.036 | 10.118±0.668 |

## Conclusion

- Zero-shot Kimi is weak on repair and collapses completely on OOD.
- Scalar-reward-only multi-step LLM remains ineffective: it improves neither success rate nor best objective in a meaningful way.
- Structured verifier feedback changes the outcome: the verifier-guided agent reaches `0.708±0.072` success on repair OOD repeats, far above zero-shot (`0.000±0.000`) and scalar-reward-only (`0.042±0.072`).
