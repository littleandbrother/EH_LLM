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

- status: implementation complete, but single-task API latency is still too high for reliable interactive smoke
- current blocker: `feasibility_repair` prompt path is much slower than `frequency_matching`
- next action: compress repair prompt further or switch to a lighter model / lower-latency config before full LLM benchmark runs
