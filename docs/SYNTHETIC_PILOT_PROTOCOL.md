# VEHBench Synthetic Pilot v1 Protocol

## Goal

Turn the current curated paper-grounded anchors into a larger **anchor-conditioned synthetic benchmark** without pretending that the synthetic labels are all equally trustworthy.

The pilot has four rules:

1. Use the existing `ready` paper-grounded seeds as anchors.
2. Generate synthetic geometry/load candidates around those anchors in a deterministic, reproducible way.
3. Label **frequency** with an independent 1D beam FEM.
4. Label **power / voltage / stress / displacement** with the current verifier surrogate, and mark that provenance explicitly.

This keeps the current project honest:

- frequency gets a more independent label path
- electromechanical outputs stay available
- power is still not claimed as high-fidelity FEM truth

## Anchor Set

The pilot uses `paper_grounded_task_seeds.jsonl` and keeps only anchors with:

- `mapping_status == "ready"`
- complete verifier-ready geometry / excitation / load mapping

At the current checkpoint this yields `52` anchors.

## Sampling Policy

The synthetic pilot generates exactly `1000` synthetic seeds from those anchors.

Allocation:

- equal base allocation across anchors
- deterministic remainder assignment by sorted anchor id

Each synthetic seed is sampled in one of three modes:

- `local_gaussian`
  - small perturbation around the anchor in normalized design space
- `wide_gaussian`
  - broader in-family perturbation
- `boundary_push`
  - pushes one or two variables close to regime boundaries to increase OOD pressure

All sampling is deterministic given:

- anchor id
- sample index
- protocol version

## Label Sources

Each synthetic seed stores explicit label provenance:

- `frequency_label_source = "beam_fem_1d_v1"`
- `electromechanical_label_source = "vehbench_verifier_surrogate_v1"`

Meaning:

- `resonant_frequency_hz` is taken from the independent 1D beam FEM when available
- `load_power_w`, `open_circuit_voltage_v`, `tip_displacement_mm`, and `root_stress_mpa` come from the current verifier runtime

Fallback rule:

- if FEM frequency fails, the seed is dropped from the pilot rather than silently replaced

## Split Policy

To avoid family leakage, every synthetic seed inherits the split of its parent anchor:

- `train`
- `val`
- `test-id`
- `test-ood`

OOD tags are inherited from the anchor and extended with:

- `synthetic_boundary_push` when applicable

This means:

- the synthetic pilot is larger than the paper-grounded set
- but it still respects anchor-level split isolation

## Task Reconstruction

Each synthetic seed is converted into up to three synthetic tasks:

- `frequency_matching`
- `constrained_power_maximization`
- `feasibility_repair`

The synthetic task generator follows the same philosophy as the paper-grounded one:

- start from a reference labeled design
- retarget frequency tasks so midpoint is not trivially feasible
- generate explicitly infeasible repair starts
- preserve exact split inheritance

## Interpretation Rules

This pilot should be used for:

- scaling the benchmark from `55` paper anchors to `1000` synthetic seeds
- stress-testing solver ladders
- building a stronger statistical story for frequency and repair

This pilot should **not** yet be used to claim:

- high-fidelity power truth
- complete electromechanical external validation
- hardware-faithful deployment transfer

## Files

- schema: `schemas/vehbench_anchor_conditioned_synthetic_seed_v1.json`
- pilot seeds: `data_registry/benchmark/synthetic_pilot_v1_seeds.jsonl`
- pilot tasks: `data_registry/benchmark/synthetic_pilot_v1_tasks.jsonl`
- generator script: `scripts/build_anchor_conditioned_synthetic_pilot.py`
- task reconstruction script: `scripts/generate_synthetic_benchmark_tasks.py`
