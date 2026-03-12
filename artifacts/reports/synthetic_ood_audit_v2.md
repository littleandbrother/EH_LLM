# Synthetic OOD Audit V2

## Scope

This audit revisited the synthetic `test-ood` task construction for:

- boundary push strength
- frequency retarget magnitude
- repair initial-candidate degradation

The goal was to move OOD difficulty back into a usable regime:

- classical baselines should separate
- OOD should not collapse to near-zero success for every solver

## Root Cause

The first-round synthetic OOD collapse was not primarily caused by a larger fraction of `boundary_push` samples. The actual failure mode was a label-space mismatch:

- synthetic seeds stored **raw 1D beam FEM frequency** as the task target
- runtime evaluation used the **calibrated verifier frequency**
- in OOD, the raw-vs-runtime frequency gap became extreme

As a result, the generated `frequency_matching` and `feasibility_repair` tasks were often inconsistent with the evaluator that later judged them.

## What Changed in V2

### 1. Runtime-consistent synthetic frequency labels

Synthetic seeds now keep both:

- `raw_fem_frequency_hz`
- `runtime_calibrated_frequency_hz`

The benchmark-facing `observed_outputs.resonant_frequency_hz` now uses the runtime-consistent calibrated frequency rather than the raw FEM frequency.

### 2. Excitation consistency

Synthetic tasks are postprocessed so that:

- `fixed_conditions.excitation_frequency_hz`
- `fixed_conditions.acceleration_g`

are forced to match the synthetic seed's verifier excitation settings. This prevents calibration drift caused by silently changing excitation context between seed generation and runtime evaluation.

### 3. Softer boundary push

Boundary push no longer drives dimensions almost fully to `0.04 / 0.96` in unit space. V2 uses a softer `0.10 / 0.90` push with smaller noise, reducing pathological OOD excursions.

### 4. Synthetic split-aware difficulty profiles

Synthetic retarget and repair profiles were recalibrated to the *actually reachable* local frequency variation under the calibrated verifier:

- `frequency_matching`: approximately `1%` to `4%` target shifts
- `feasibility_repair`: approximately `2.2%` to `5.0%` initial frequency error bands

This replaced the earlier `8%` to `18%` style targets, which were unrealistic under the synthetic runtime frequency landscape.

## Audit Findings After V2 Rebuild

### Seed-level sanity

- `test-id` runtime-vs-excitation frequency gap:
  - median: `6.706%`
  - p90: `13.983%`
- `test-ood` runtime-vs-excitation frequency gap:
  - median: `4.926%`
  - p90: `18.670%`

This is now in a physically reasonable range for synthetic perturbations.

### Frequency tasks

- `test-id`
  - reference solution feasible rate: `1.000`
  - midpoint feasible rate: `0.000`
- `test-ood`
  - reference solution feasible rate: `1.000`
  - midpoint feasible rate: `0.000`

Interpretation:

- the synthetic target is now consistent with the evaluator
- the midpoint is no longer trivially feasible
- OOD is no longer "impossible by construction"

### Repair tasks

- `test-id`
  - initial feasible rate: `0.000`
  - median initial frequency error: `3.387%`
  - p90 initial frequency error: `3.520%`
  - dominant violation: `frequency_too_low`
- `test-ood`
  - initial feasible rate: `0.000`
  - median initial frequency error: `4.005%`
  - p90 initial frequency error: `4.132%`
  - dominant violation: `frequency_too_low`

Interpretation:

- repair tasks are now consistently infeasible at the start
- OOD repair starts are slightly harder than ID
- failure patterns are clean and interpretable rather than chaotic

## Second-Round Synthetic Classical Results

All runs used:

- `synthetic_pilot_v2_tasks.jsonl`
- calibrated frequency evaluation
- `--disable-task-anchors`

### Frequency Matching

- `test-id`
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.876`
  - Bayesian Optimization: `1.000`
- `test-ood`
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.883`
  - Bayesian Optimization: `1.000`

### Feasibility Repair

- `test-id`
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.908`
  - Bayesian Optimization: `1.000`
- `test-ood`
  - Random Search: `1.000`
  - Genetic Algorithm: `1.000`
  - CMA-ES: `0.617`
  - Bayesian Optimization: `1.000`

## Current Interpretation

V2 successfully fixed the original OOD collapse:

- OOD is no longer near-zero for every solver
- task construction is now evaluator-consistent
- repair starts are controlled and reproducible

But V2 also exposed a new issue:

- the synthetic OOD benchmark is now **near-ceiling** for Random / GA / BO
- only CMA-ES is strongly separated

So the current synthetic pilot is usable, but not yet ideal as a final OOD benchmark if the goal is to separate *all* classical solvers cleanly.

## Immediate Next Step

Proceed with synthetic LLM baselines on this repaired V2 benchmark:

- zero-shot LLM on synthetic `test-ood`
- verifier-guided LLM on synthetic `test-ood`

If LLM methods also saturate, the next adjustment should be a third-round hardening pass focused on:

- tighter query budgets
- slightly larger OOD repair degradation
- task families that require multi-variable coordinated moves rather than single-frequency nudges
