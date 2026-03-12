# Synthetic LLM Pilot V2

## Scope

This report summarizes the first synthetic `test-ood` LLM pilot after repairing the synthetic benchmark construction.

To keep latency and API cost bounded, this pilot used a **representative subset of 24 OOD tasks per task family**:

- `frequency_matching / test-ood / limit=24`
- `feasibility_repair / test-ood / limit=24`

All runs used:

- `synthetic_pilot_v2_tasks.jsonl`
- calibrated frequency evaluation
- `--disable-task-anchors`
- provider: `DashScope coding API`
- model: `kimi-k2.5`

## Zero-Shot Kimi

### Frequency Matching

- run:
  - [vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_225921_184348](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_225921_184348)
- tasks: `24`
- success rate: `0.792`
- avg queries used: `1.0`
- avg queries to success: `1.0`
- avg best normalized objective: `0.632`
- avg wall-clock: `4.09s`

### Feasibility Repair

- run:
  - [vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_225921_351126](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_225921_351126)
- tasks: `24`
- success rate: `0.625`
- avg queries used: `1.0`
- avg queries to success: `1.0`
- avg best normalized objective: `0.813`
- avg wall-clock: `4.69s`

## Verifier-Guided Kimi

### Frequency Matching

- run:
  - [vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_230124_271767](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_230124_271767)
- tasks: `24`
- success rate: `1.000`
- avg queries used: `8.75`
- avg queries to success: `8.75`
- avg best normalized objective: `0.843`
- avg wall-clock: `6.81s`

### Feasibility Repair

- run:
  - [vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_230124_456814](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_230124_456814)
- tasks: `24`
- success rate: `1.000`
- avg queries used: `8.29`
- avg queries to success: `8.29`
- avg best normalized objective: `1.000`
- avg wall-clock: `6.90s`

## Interpretation

Three things are now clear on the repaired synthetic OOD subset:

1. `zero-shot` is no longer blocked by latency or pathological task construction.
2. `verifier-guided` clearly outperforms `zero-shot` on both task families.
3. structured feedback remains valuable even after moving from paper-grounded tasks to synthetic anchor-conditioned tasks.

The main tradeoff is now explicit:

- `zero-shot` is cheaper and faster
- `verifier-guided` is slower and query-heavier
- but `verifier-guided` is substantially more reliable

## Matched Classical Subset

For direct comparison, a matched `24-task` classical subset was also run on the same OOD slice.

### Frequency Matching

- run:
  - [vehbench_classical_frequency_matching_test-ood_all_20260312_230443_175609](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-ood_all_20260312_230443_175609)
- success:
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.917`
  - Bayesian Optimization: `1.000`

### Feasibility Repair

- run:
  - [vehbench_classical_feasibility_repair_test-ood_all_20260312_230443_175628](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-synthetic/artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-ood_all_20260312_230443_175628)
- success:
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.708`
  - Bayesian Optimization: `1.000`

## Direct Comparison

On this matched synthetic OOD subset:

- `frequency_matching`
  - classical strongest: `1.000`
  - zero-shot Kimi: `0.792`
  - verifier-guided Kimi: `1.000`
- `feasibility_repair`
  - classical strongest: `1.000`
  - zero-shot Kimi: `0.625`
  - verifier-guided Kimi: `1.000`

So the repaired synthetic benchmark already reproduces the same broad pattern seen on the paper-grounded benchmark:

- zero-shot remains meaningfully weaker than search or structured-feedback methods
- verifier-guided closes most of that gap
- CMA-ES remains the weakest classical baseline on this benchmark family

## Caveat

These are **subset** results, not full-split results. They are sufficient to validate that the repaired synthetic benchmark behaves sensibly under LLM baselines, but not yet sufficient for final paper tables.

## Recommended Next Step

If synthetic v2 is kept as the mainline synthetic benchmark, the next high-value step is:

1. expand zero-shot and verifier-guided from `24` OOD tasks to the full `test-ood` split
2. decide whether to further harden synthetic OOD, because Random / GA / BO are still near-ceiling on the full-split classical runs
3. if the benchmark is kept as-is, start building synthetic-first main tables from the v2 OOD results
