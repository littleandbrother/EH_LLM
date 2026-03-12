# Synthetic Hardening V3

## Goal

V2 fixed the original OOD collapse, but left the synthetic benchmark too easy:

- `frequency / test-ood`: Random, GA, and BO were all near ceiling
- `repair / test-ood`: Random, GA, and BO were still too strong

V3 was designed to harden the synthetic benchmark without reintroducing the `v1`/`v2` label-space mismatch bug.

## What Changed

### Frequency Matching

- widened synthetic variable bounds by split, especially on `test-id` and `test-ood`
- tightened frequency tolerance:
  - `train`: `1.5%`
  - `val`: `1.25%`
  - `test-id`: `1.0%`
  - `test-ood`: `0.8%`
- reduced query budgets:
  - `test-id`: `10`
  - `test-ood`: `8`
- required edge-oriented reference solutions during synthetic retargeting

### Feasibility Repair

- widened bounds further for OOD
- tightened repair tolerance:
  - `test-id`: `1.2%`
  - `test-ood`: `1.0%`
- reduced repair budgets:
  - `test-id`: `8`
  - `test-ood`: `6`
- added stress and displacement limits derived from the reference synthetic seed
- changed repair candidate selection to prefer:
  - multi-variable changes
  - multi-violation starts
  - non-frequency violations when available

## Sanity Audit

### Frequency

- `test-id`
  - reference feasible rate: `1.000`
  - midpoint feasible rate: `0.000`
  - midpoint dominant violation: `frequency_too_low`
- `test-ood`
  - reference feasible rate: `1.000`
  - midpoint feasible rate: `0.000`
  - midpoint dominant violation: `frequency_too_low`

### Repair

- `test-id`
  - initial feasible rate: `0.000`
  - median initial frequency error: `4.680%`
  - p90 initial frequency error: `5.088%`
  - multi-violation rate: `0.980`
- `test-ood`
  - initial feasible rate: `0.000`
  - median initial frequency error: `5.129%`
  - p90 initial frequency error: `5.740%`
  - multi-violation rate: `0.740`

This is substantially harder than V2 and much closer to a useful synthetic benchmark regime.

## Classical Baselines on V3

All runs used:

- `synthetic_pilot_v3_tasks.jsonl`
- calibrated frequency evaluation
- `--disable-task-anchors`

### Frequency Matching

- `test-id`
  - Random Search: `0.797`
  - Genetic Algorithm: `0.810`
  - CMA-ES: `0.013`
  - Bayesian Optimization: `0.758`
- `test-ood`
  - Random Search: `0.597`
  - Genetic Algorithm: `0.630`
  - CMA-ES: `0.000`
  - Bayesian Optimization: `0.636`

### Feasibility Repair

- `test-id`
  - Random Search: `0.745`
  - Genetic Algorithm: `0.732`
  - CMA-ES: `0.000`
  - Bayesian Optimization: `0.712`
- `test-ood`
  - Random Search: `0.481`
  - Genetic Algorithm: `0.331`
  - CMA-ES: `0.000`
  - Bayesian Optimization: `0.429`

## Interpretation

V3 finally moves the synthetic benchmark into the intended regime:

- OOD does not collapse to zero for every solver
- Random / GA / BO are no longer all at `1.0`
- classical methods now separate on both `frequency` and `repair`
- `repair / test-ood` shows the cleanest spread

This is the first synthetic variant that behaves like a real benchmark instead of either:

- an impossible benchmark
- or a near-ceiling benchmark

## Synthetic LLM Pilot on V3

Matched `24-task` OOD subset:

### Zero-Shot Kimi

- `frequency_matching / test-ood / 24 tasks`
  - success: `0.375`
  - run: [vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_232311_918794](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_232311_918794)
- `feasibility_repair / test-ood / 24 tasks`
  - success: `0.208`
  - run: [vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_232312_234240](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_232312_234240)

### Verifier-Guided Kimi

- `frequency_matching / test-ood / 24 tasks`
  - previous pre-v3-hardening-policy run: `0.458`
  - run: [vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_232444_838266](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_232444_838266)
- `feasibility_repair / test-ood / 24 tasks`
  - original low-budget-unaware run: `0.000`
  - budget-aware rerun: `0.167`
  - run: [vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_232718_892544](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_232718_892544)

## Takeaway

V3 accomplished the main benchmark-design goal:

- the synthetic benchmark is now hard enough to separate classical solvers
- zero-shot Kimi drops sharply relative to V2, which confirms the hardening is real
- verifier-guided repair is no longer trivially broken by budget starvation, but still needs a stronger low-budget policy to recover the margin seen on the paper-grounded benchmark

## Next Step

The highest-value next step is:

1. keep `synthetic_pilot_v3_tasks.jsonl` as the new main synthetic benchmark
2. improve the verifier-guided low-budget policy specifically for repair
3. once that stabilizes, rebuild a clean synthetic main table from:
   - full-split classical
   - matched-subset zero-shot
   - matched-subset verifier-guided
