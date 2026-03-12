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

## Kimi Repair Zero-Shot

- `test-id` run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-id_20260312_062010_734271`
  - success `0.125`
  - avg best normalized objective `0.5625`
  - avg wall clock `3.017s`
- `test-ood` run: `artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_062010_734255`
  - success `0.000`
  - avg best normalized objective `0.500`
  - avg wall clock `2.703s`

### Repair Interpretation

- Kimi repair is now operational and low-latency enough for benchmark runs
- current failure mode is narrow: almost all failed cases are still single frequency violations (`frequency_too_low` or `frequency_too_high`)
- compared with classical repair baselines, Kimi is currently much weaker:
  - `test-id`: Kimi `0.125` vs random `0.750`, GA `0.875`, BO `1.000`
  - `test-ood`: Kimi `0.000` vs random `0.625`, GA `0.500`, BO `0.750`
- this makes zero-shot repair a useful lower baseline, but not yet a competitive solver

## Verifier-Guided LLM Agent (Initial Build)

- solver added: `vehbench/solvers/verifier_guided_llm.py`
- runner added: `scripts/run_verifier_guided_llm.py`
- current policy:
  - bootstrap from midpoint or provided infeasible start
  - show verifier feedback plus recent history to Kimi
  - allow up to 3 LLM-guided repair iterations after bootstrap

### Smoke

- `frequency/test-id` single-task smoke: no success
- `repair/test-id` single-task smoke: success in `3` queries

### Full repair runs

- `test-id` run: `artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-id_20260312_062543_470594`
  - success `0.000`
  - avg best normalized objective `0.500`
  - avg wall clock `14.397s`
- `test-ood` run: `artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_062543_470496`
  - success `0.000`
  - avg best normalized objective `0.500`
  - avg wall clock `13.894s`

### Agent Interpretation

- the verifier-guided agent is now fully wired and runnable
- latency is acceptable and there were no provider errors
- however, the current prompting policy is not yet extracting useful directional information from the verifier
- across full repair runs, every task remained stuck at a single frequency violation
- this means the agent implementation is a valid baseline scaffold, but not yet a competitive repair solver

## Verifier-Guided LLM Agent (Local Sensitivity + Direction Search)

- upgraded policy:
  - perform an explicit local sensitivity scan with verifier queries before the first LLM step
  - include empirically measured `local_probes` in the Kimi prompt
  - perform a boundary-seeking directional search along the best observed improvement directions
  - include `load_resistance_ohm` in probe priority because electromechanical coupling can shift calibrated frequency

### Updated repair runs

- `test-id` run: `artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-id_20260312_140513_536411`
  - success `1.000`
  - avg queries to success `9.125`
  - avg best normalized objective `1.000`
  - avg wall clock `6.115s`
- `test-ood` run: `artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_140611_768999`
  - success `0.750`
  - avg queries to success `9.167`
  - avg best normalized objective `0.875`
  - avg wall clock `13.405s`

### Updated Interpretation

- this is no longer just a scaffold; the agent is now competitive on repair
- compared with zero-shot repair, verifier-guided policy is materially stronger:
  - `test-id`: `1.000` vs `0.125`
  - `test-ood`: `0.750` vs `0.000`
- compared with classical repair:
  - `test-id`: matches BO and exceeds random / GA on success rate
  - `test-ood`: matches BO and exceeds random / GA
- the decisive change was not a larger model or longer prompt; it was exposing local verifier sensitivity and using explicit directional search before each LLM repair decision
