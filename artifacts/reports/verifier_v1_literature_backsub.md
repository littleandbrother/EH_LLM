# Verifier v1 Literature Back-Substitution

This report evaluates the executable `vehbench/verifier/v1` evaluator on the ready paper-grounded verifier requests.

## Batch Coverage

- total requests executed: `156`
- valid requests: `156`
- feasible requests: `105`

### By Task Type

- `frequency_matching`: count=`52`, valid=`52`, feasible=`52`
- `constrained_power_maximization`: count=`52`, valid=`52`, feasible=`52`
- `feasibility_repair`: count=`52`, valid=`52`, feasible=`1`

## Canonical Literature Back-Substitution

Canonical rows use the `reference_solution` / `frequency_matching` design for each ready seed so synthetic repair candidates do not contaminate the literature comparison.
The benchmark evaluator itself is task-aware; the metrics below are computed from the raw physics path without task-local anchoring.

- canonical papers evaluated: `52`
- raw frequency MAE (Hz): `1594.027`
- raw frequency MAPE (%): `759.845`
- raw frequency median APE (%): `194.972`
- raw power MAPE (%): `199.486`
- raw power median APE (%): `99.991`
- raw power median |log10(pred/obs)|: `3.860`
- raw frequency decision consistency: `0.000`

### Calibrated Raw Frequency

- calibrated frequency MAPE (%): `7.115`
- calibrated frequency median APE (%): `4.329`
- calibrated frequency decision consistency: `0.577`

### Task-Aware Benchmark Evaluator

- task-aware frequency MAPE (%): `0.000`
- task-aware frequency decision consistency: `1.000`
- task-aware power MAPE (%): `0.004`
- task-aware power median APE (%): `0.000`

## Notes

- This is a fast approximate verifier, not FEM.
- The current v1 uses composite-cantilever stiffness, modal mass approximation, and RC load transfer.
- Benchmark execution is task-aware: when task context is available, the evaluator applies local frequency/power anchoring around the paper-grounded reference design.
- Stress decision accuracy is not reported yet because the extracted literature set does not consistently contain explicit stress labels or limits.
