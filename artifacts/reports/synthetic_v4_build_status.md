# Synthetic v4 Build Status

## What Was Added

- `docs/SYNTHETIC_V4_PROTOCOL.md`
- `configs/synthetic_v4_generation_spec.json`
- `configs/synthetic_v4_baseline_ladder.json`
- `schemas/vehbench_anchor_conditioned_synthetic_seed_v2.json`
- `vehbench/fem/cantilever.py`
- `scripts/build_anchor_conditioned_synthetic_v4_pilot.py`
- `scripts/generate_synthetic_v4_tasks.py`
- `scripts/audit_synthetic_v4_tasks.py`

## Generated Artifacts

- seeds:
  - `data_registry/benchmark/synthetic_v4_pilot_1k_seeds.jsonl`
- tasks:
  - `data_registry/benchmark/synthetic_v4_pilot_1k_tasks.jsonl`
  - per-type and per-split task files
- reports:
  - `artifacts/reports/synthetic_v4_pilot_1k.md`
  - `artifacts/reports/synthetic_v4_pilot_1k_tasks.md`
  - `artifacts/reports/synthetic_v4_pilot_1k_task_audit.md`

## Current Counts

- synthetic seeds generated: `1000`
- dropped seeds: `0`
- total tasks: `3000`
  - `1000` frequency
  - `1000` power
  - `1000` repair
- split counts:
  - `train = 1677`
  - `val = 402`
  - `test-id = 459`
  - `test-ood = 462`

## Task Audit

- frequency midpoint feasibility:
  - `train: 6 / 559`
  - `val: 0 / 134`
  - `test-id: 0 / 153`
  - `test-ood: 0 / 154`
- repair initial-candidate feasibility:
  - `train: 0 / 559`
  - `val: 0 / 134`
  - `test-id: 0 / 153`
  - `test-ood: 0 / 154`

This confirms that v4 is not trivially easy.

## Smoke Baseline Result

Ran a classical smoke on:

- task family: `frequency_matching`
- split: `test-ood`
- limit: `20`
- runtime mode: `disable-task-anchors`

Observed:

- random search: `0.0`
- GA: `0.0`
- CMA-ES: `0.0`
- BO: `0.0`

## Interpretation

This is the expected consequence of synthetic v4's main design change:

- the synthetic label stack is now produced by the new FEM/electromechanical
  generator
- the benchmark runtime still uses the old verifier v1

So the current blocker is no longer "task generation quality". The blocker is
now:

- **verifier-v1 is not calibrated to synthetic-v4 labels**

That is exactly the separation we wanted. The generator and evaluator are now
different artifacts instead of one silently reusing the other.

## Immediate Next Step

Build `verifier-v4 calibration` against the synthetic-v4 seed set:

1. compare runtime verifier outputs vs v4 synthetic labels
2. fit frequency calibration on v4 labels
3. fit stress / displacement / power correction where defensible
4. rerun classical baselines only after that calibration step
