# Synthetic Main Comparison v3

- synthetic benchmark: `synthetic_pilot_v3_tasks.jsonl`
- matched subset: `24` tasks per family, stratified across `8` OOD anchors (`3` synthetic seeds per anchor)
- runtime setting: calibrated frequency on, task anchors off
- zero-shot / verifier-guided model: `kimi-k2.5` via DashScope coding endpoint

## Full Test-OOD Results

| Task | Solver | Success | Avg Queries Used | Avg Queries To Success | Avg Wall Clock (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| `frequency_matching` | `random_search` | `0.597` | `8.000` | `4.565` | `0.000` |
| `frequency_matching` | `genetic_algorithm` | `0.630` | `8.000` | `4.546` | `0.000` |
| `frequency_matching` | `cma_es` | `0.000` | `8.000` | `-` | `0.000` |
| `frequency_matching` | `bayesian_optimization` | `0.636` | `8.000` | `4.990` | `0.000` |
| `frequency_matching` | `zero_shot_llm` | `0.318` | `1.000` | `1.000` | `2.727` |
| `frequency_matching` | `verifier_guided_llm` | `0.487` | `7.831` | `7.653` | `5.251` |
| `feasibility_repair` | `random_search` | `0.481` | `6.000` | `4.324` | `0.000` |
| `feasibility_repair` | `genetic_algorithm` | `0.331` | `6.000` | `4.725` | `0.000` |
| `feasibility_repair` | `cma_es` | `0.000` | `6.000` | `-` | `0.000` |
| `feasibility_repair` | `bayesian_optimization` | `0.429` | `6.000` | `4.500` | `0.000` |
| `feasibility_repair` | `zero_shot_llm` | `0.156` | `1.000` | `1.000` | `2.877` |
| `feasibility_repair` | `verifier_guided_llm` | `0.734` | `4.201` | `3.664` | `1.663` |

## Matched OOD Subset (24 Tasks Per Family)

| Task | Solver | Success | Avg Queries Used | Avg Queries To Success | Avg Wall Clock (s) |
| --- | --- | ---: | ---: | ---: | ---: |
| `frequency_matching` | `random_search` | `0.625` | `8.000` | `4.467` | `0.000` |
| `frequency_matching` | `genetic_algorithm` | `0.625` | `8.000` | `4.333` | `0.000` |
| `frequency_matching` | `cma_es` | `0.000` | `8.000` | `-` | `0.000` |
| `frequency_matching` | `bayesian_optimization` | `0.500` | `8.000` | `3.667` | `0.000` |
| `frequency_matching` | `zero_shot_llm` | `0.292` | `1.000` | `1.000` | `2.850` |
| `frequency_matching` | `verifier_guided_llm` | `0.458` | `7.833` | `7.636` | `5.220` |
| `feasibility_repair` | `random_search` | `0.375` | `6.000` | `4.222` | `0.000` |
| `feasibility_repair` | `genetic_algorithm` | `0.250` | `6.000` | `4.500` | `0.000` |
| `feasibility_repair` | `cma_es` | `0.000` | `6.000` | `-` | `0.000` |
| `feasibility_repair` | `bayesian_optimization` | `0.333` | `6.000` | `4.000` | `0.000` |
| `feasibility_repair` | `zero_shot_llm` | `0.083` | `1.000` | `1.000` | `2.506` |
| `feasibility_repair` | `verifier_guided_llm` | `0.708` | `4.292` | `3.706` | `2.266` |

## Takeaways

- `synthetic v3` no longer collapses on OOD: full classical `test-ood` now separates solvers instead of pushing them all to near-zero or near-one.
- Full `test-ood` LLM runs confirm the same ordering seen in the matched subset: `verifier_guided_llm` beats `zero_shot_llm` on both task families.
- On full `feasibility_repair / test-ood`, verifier-guided reaches `0.734`, far above zero-shot (`0.156`) and above every classical baseline in the same split.
- On full `frequency_matching / test-ood`, verifier-guided reaches `0.487`, beating zero-shot (`0.318`) but still trailing the strongest classical baselines (`GA = 0.630`, `BO = 0.636`).
- On the stratified matched subset, `verifier_guided_llm` now clearly beats `zero_shot_llm` on both families.
- The biggest gain is on `feasibility_repair`: after the low-budget policy fix, verifier-guided repair rises to `0.708`, well above zero-shot (`0.083`) and the strongest matched-subset classical baseline (`random_search = 0.375`).
- On `frequency_matching`, verifier-guided improves over zero-shot (`0.458` vs `0.292`) but still trails the strongest classical baselines on the matched subset.
