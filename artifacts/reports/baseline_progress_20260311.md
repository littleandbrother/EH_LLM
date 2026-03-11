# Baseline Progress 2026-03-11

## Repair Task Hardening

- change: `feasibility_repair` now uses split-aware difficulty profiles during task generation
- change: `test-id` repair tasks use `frequency_error_tolerance_pct = 1.0`
- effect: `test-id` repair is no longer trivial under calibrated frequency / no task anchors

### Repair test-id classical baseline

Run: `artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-id_all_20260311_170126_997067`

- `random_search`: success `0.750`, avg queries to success `3.83`
- `genetic_algorithm`: success `0.875`, avg queries to success `6.43`
- `cma_es`: success `0.000`
- `bayesian_optimization`: success `1.000`, avg queries to success `7.00`

### Repair test-ood classical baseline

Run: `artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-ood_all_20260311_170126_995736`

- `random_search`: success `0.625`
- `genetic_algorithm`: success `0.500`
- `cma_es`: success `0.125`
- `bayesian_optimization`: success `0.750`

## Zero-Shot LLM

- added solver: `vehbench/solvers/zero_shot_llm.py`
- added runner: `scripts/run_zero_shot_llm.py`
- runtime config:
  - Ark client from `../EH-LLM/pipelines/download/.env`
  - default timeout `60s`
  - controllable with `VEHBENCH_ZERO_SHOT_MAX_ATTEMPTS`

### Frequency smoke

Run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-id_20260311_170727_645764`

- tasks: `1`
- attempts per task: `1`
- result: `success_rate = 0.0`
- observation: chain is working end-to-end; model proposed a valid in-bounds candidate but missed target frequency

### Repair smoke

- status: stable under watchdog
- run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-id_20260311_181013_751265`
- configuration:
  - `VEHBENCH_ZERO_SHOT_MAX_ATTEMPTS=1`
  - `VEHBENCH_ZERO_SHOT_HARD_TIMEOUT_S=20`
- result: `success_rate = 0.0`, `avg_best_normalized_objective = 0.5`
- observation: run now terminates reliably, but current model latency still exceeds watchdog budget and falls back to the default repair candidate

## Frequency Classical vs Zero-Shot

### test-id

- classical reference:
  - `random_search`: success `1.000`
  - `genetic_algorithm`: success `1.000`
  - `cma_es`: success `1.000`
  - `bayesian_optimization`: success `1.000`
- zero-shot run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-id_20260311_181045_464068`
  - success `0.125`
  - avg best normalized objective `0.027`
  - avg invalid rate `0.000`
  - avg wall clock `20.018s`

### test-ood

- classical reference:
  - `random_search`: success `0.500`
  - `genetic_algorithm`: success `0.500`
  - `cma_es`: success `0.300`
  - `bayesian_optimization`: success `0.600`
- zero-shot run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260311_181045_464064`
  - success `0.200`
  - avg best normalized objective `0.121`
  - avg invalid rate `0.200`
  - avg wall clock `20.017s`

### Interpretation

- the harness is stable enough to run zero-shot frequency end-to-end
- every zero-shot frequency task in this run hit the `20s` hard timeout and therefore used the fallback candidate path
- the resulting comparison is useful as an engineering checkpoint, but it is not yet a fair estimate of the LLM's actual one-shot capability
- before any paper-facing comparison, switch to a lower-latency model or a different API path that returns within the watchdog budget

## DashScope Coding Replacement

- replacement endpoint: `https://coding.dashscope.aliyuncs.com/v1`
- selected model: `kimi-k2.5`
- supporting probe report: [llm_probe_dashscope_coding_20260312.md](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/reports/llm_probe_dashscope_coding_20260312.md)

### Why Kimi

- `minimal_json`: `4.199s`
- `frequency_matching` probe: `1.978s`, feasible
- `feasibility_repair` probe: `1.996s`, non-feasible but valid
- other tested models were much slower or timed out on task prompts

### Kimi Frequency Zero-Shot

- `test-id` run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-id_20260312_061601_216713`
  - success `0.500`
  - avg best normalized objective `0.365`
  - avg wall clock `2.474s`
- `test-ood` run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_061601_216649`
  - success `0.200`
  - avg best normalized objective `0.071`
  - avg wall clock `2.299s`

### Updated Interpretation

- these Kimi runs are real model outputs, not watchdog fallbacks
- `frequency/test-id`: Kimi is clearly below the classical solvers, but no longer degenerate
- `frequency/test-ood`: Kimi matches the prior zero-shot level numerically, but now the result reflects actual one-shot model behavior
- this is a valid first `classical vs zero-shot` comparison for the benchmark
