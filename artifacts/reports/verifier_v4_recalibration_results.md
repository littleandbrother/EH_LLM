# Verifier v4 Recalibration Results

## Frequency Calibration

Using:

- `data_registry/benchmark/synthetic_v4_pilot_1k_seeds.jsonl`
- script: `scripts/fit_verifier_v4_calibration.py`

Observed:

- row count: `1000`
- raw frequency MAPE: `0.901%`
- calibrated frequency MAPE: `0.268%`
- raw frequency median APE: `1.404%`
- calibrated frequency median APE: `0.231%`

Output profile:

- `data_registry/benchmark/verifier_v4_frequency_calibration_profile.json`

## Output Correction Audit

- displacement:
  - raw MAPE: `8.231%`
  - log-bias MAPE: `2.308%`
  - recommendation: `worth adding later`
- power:
  - raw MAPE: `34.346%`
  - log-bias MAPE: `4.600%`
  - recommendation: `worth adding later`
- stress:
  - raw MAPE: `355127.087%`
  - log-bias MAPE: `370703.469%`
  - recommendation: `do not add correction`

Interpretation:

- frequency is already clean enough to use now
- displacement and power look promising for a later correction layer
- stress is too unstable and should stay uncorrected for now

## Classical Baseline Rerun

Runtime mode:

- `disable-task-anchors`
- `frequency_profile_path = data_registry/benchmark/verifier_v4_frequency_calibration_profile.json`

### Frequency Matching (`1000` tasks, all splits)

- random search: `0.503`
- genetic algorithm: `0.531`
- CMA-ES: `0.506`
- bayesian optimization: `0.548`

### Feasibility Repair (`1000` tasks, all splits)

- random search: `0.455`
- genetic algorithm: `0.459`
- CMA-ES: `0.358`
- bayesian optimization: `0.480`

## Main Takeaway

Synthetic v4 is now in the right state:

- labels are decoupled from the old runtime
- the runtime can be explicitly recalibrated to the v4 label stack
- classical baselines no longer collapse to zero

This makes the next step straightforward:

1. keep the new frequency profile for synthetic-v4 runs
2. decide whether to add displacement / power correction into runtime
3. rerun synthetic-v4 LLM baselines on the recalibrated benchmark
