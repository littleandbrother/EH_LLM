# VEHBench Synthetic v4 Protocol

## Goal

Synthetic v4 upgrades the current synthetic line from a small pilot into a
**paper-anchored, high-fidelity-first benchmark build**.

The protocol has five explicit rules:

1. Keep the current `ready` paper-grounded seeds as the realism anchors.
2. Expand those anchors into a larger synthetic design population with explicit
   split inheritance and OOD tagging.
3. Label `frequency`, `stress`, and `displacement` with an independent Python
   beam-FEM stack rather than the benchmark runtime.
4. Label `power` and `matched-load` with an electromechanical surrogate driven
   by FEM section properties and excitation settings, and record that provenance
   separately.
5. Keep the benchmark runtime decoupled from the label stack, so later verifier
   calibration can be evaluated instead of silently baked in.

## Why v4 Exists

The paper-grounded line proved the benchmark skeleton, but it is too small for
CCF-A benchmark expectations.

The synthetic v1-v3 line scaled the benchmark, but it still mixed:

- task-generation labels
- runtime verifier behavior
- anchor-conditioned priors

Synthetic v4 fixes that by treating the synthetic data generator as its own
artifact with explicit label provenance.

## Anchor Set

Input anchors come from:

- `data_registry/benchmark/paper_grounded_task_seeds.jsonl`

Keep only:

- `mapping_status == "ready"`
- anchors with complete geometry, excitation, and load for verifier mapping

At the current checkpoint this is expected to remain `52` anchors.

## Synthetic Population Targets

Two scales are defined up front:

- `pilot_1k`
  - `1000` synthetic seeds
  - `~3000` tasks
- `full_10k`
  - `10000` synthetic seeds
  - `~30000` tasks

This branch implements `pilot_1k` first, but the file structure and configs are
set so the same pipeline can be extended to `full_10k`.

## Sampling Policy

Synthetic v4 samples around each anchor using deterministic policies:

- `local_gaussian`
  - small in-family perturbation around the anchor
- `wide_gaussian`
  - broader family exploration
- `geometry_edge_push`
  - pushes geometry variables toward boundary regimes
- `thickness_exchange`
  - trades substrate and piezo thickness against each other
- `load_sweep`
  - emphasizes large resistive-load changes

Sampling is deterministic given:

- parent anchor id
- sample index
- sampling policy
- protocol version

## Label Stack

### Frequency / Stress / Displacement

Source:

- `vehbench_fem_cantilever_v1`

Mechanism:

- Euler-Bernoulli beam FEM
- composite-section reconstruction
- point tip-mass support
- dynamic response under sinusoidal base excitation

### Power / Voltage / Matched Load

Source:

- `vehbench_electromech_surrogate_v4`

Mechanism:

- FEM-derived section properties
- estimated quality factor
- piezo capacitance model
- matched-load and user-load power estimation

This is still not COMSOL-truth, but it is a cleaner and more explicit label
path than the previous runtime-coupled surrogate.

## Split Policy

Every synthetic seed inherits the split of its parent anchor:

- `train`
- `val`
- `test-id`
- `test-ood`

OOD tags are inherited and then extended by synthetic sampling policy tags such
as:

- `synthetic_geometry_edge_push`
- `synthetic_load_sweep`
- `synthetic_thickness_exchange`

No synthetic children from the same anchor may cross splits.

## Task Reconstruction

Each synthetic seed is expanded into up to three tasks:

- `frequency_matching`
- `constrained_power_maximization`
- `feasibility_repair`

Task construction goals:

- `frequency`
  - harder than v2, but not collapsed
- `repair`
  - multi-variable infeasible starts, not only frequency nudges
- `power`
  - now based on the synthetic label stack, not directly on paper metadata

## Acceptance Criteria for Pilot 1k

The pilot is considered usable if:

- seed generation succeeds for at least `900 / 1000` requested samples
- every seed has explicit label provenance
- all three task families are generated
- `test-ood` is not collapsed to near-zero or near-one success for all classical solvers
- runtime-vs-label mismatch is explicitly measurable instead of hidden

## Planned Next Step After Pilot 1k

1. calibrate a v4 verifier against the high-fidelity label stack
2. rebuild full synthetic benchmark tasks
3. rerun classical / zero-shot / verifier-guided baselines
4. scale to `full_10k`

## Files

- schema: `schemas/vehbench_anchor_conditioned_synthetic_seed_v2.json`
- generation spec: `configs/synthetic_v4_generation_spec.json`
- ladder spec: `configs/synthetic_v4_baseline_ladder.json`
- FEM labeler: `vehbench/fem/cantilever.py`
- pilot builder: `scripts/build_anchor_conditioned_synthetic_v4_pilot.py`
- task reconstruction: `scripts/generate_synthetic_v4_tasks.py`
