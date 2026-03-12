# Synthetic Baseline Ladder v1

This file defines the execution order for the first synthetic VEHBench pilot.

## Why a ladder

The synthetic pilot is larger than the paper-grounded set, but the labels are hybrid:

- frequency labels come from `beam_fem_1d_v1`
- electromechanical labels come from `vehbench_verifier_surrogate_v1`

So the solver rollout should not treat every task family the same way.

## Stage 1: Classical Core

Run first:

- `random_search`
- `genetic_algorithm`
- `cma_es`
- `bayesian_optimization`

Task families:

- `frequency_matching`
- `feasibility_repair`

Reason:

- these are the two highest-confidence task families in the synthetic pilot
- they also connect directly to the current paper-grounded mainline

## Stage 2: Zero-Shot LLM

Run next:

- `zero_shot_llm`

Task families:

- `frequency_matching`
- `feasibility_repair`

Reason:

- preserve comparability with the current paper-grounded benchmark
- quantify whether the larger synthetic regime changes the zero-shot gap

## Stage 3: Structured-Feedback Ablation

Run next:

- `scalar_reward_llm`
- `verifier_guided_llm`

Task family:

- `feasibility_repair`

Reason:

- this is where structured feedback was most valuable on the paper-grounded set
- the synthetic pilot should test whether that effect scales

## Stage 4: Power Gate

Run only after a small label audit:

- `random_search`
- `bayesian_optimization`
- `verifier_guided_llm`

Task family:

- `constrained_power_maximization`

Reason:

- the power labels are currently surrogate-generated, not high-fidelity FEM truth
- power should not become a main benchmark axis until the synthetic pilot confirms that those labels are stable enough

## Stage 5: Future Surrogate Models

Not yet implemented, but now clearly scoped:

- `surrogate_mlp`
- `operator_model`

Reason:

- once the synthetic pilot is large enough, learned surrogates become a meaningful baseline class
- this is the right place to add AI4Science-style model baselines later

## Immediate Recommendation

Start with:

1. `frequency_matching / train+val+test-id+test-ood`
2. `feasibility_repair / train+val+test-id+test-ood`
3. only then audit the synthetic power labels

Config source:

- `configs/synthetic_baseline_ladder_v1.json`
