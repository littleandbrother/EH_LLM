# VEHBench Normalization Rules

Last updated: 2026-03-09

## Purpose

These rules define the canonical units and extraction policy for `VEHBench`.

The goal is not to infer missing physics.
The goal is to normalize paper-reported values into a stable representation that can be compared, filtered, and back-substituted into the verifier.

## Scope

These rules apply to:

- `vehbench_paper_extraction_v1`
- `candidate`, `silver`, and `gold` record curation
- literature back-substitution into verifier v1
- benchmark task generation

## Canonical Units

| Field | Canonical unit | Notes |
| --- | --- | --- |
| `beam_length_mm` | `mm` | Beam free length unless paper explicitly states total length only |
| `beam_width_mm` | `mm` | Use active beam width |
| `substrate_thickness_um` | `um` | Keep substrate-only thickness when separable |
| `piezo_thickness_um` | `um` | Keep active piezo layer thickness |
| `tip_mass_g` | `g` | Use attached proof mass only |
| `excitation_frequency_hz` | `Hz` | Use excitation frequency, not bandwidth |
| `resonant_frequency_hz` | `Hz` | Use experimentally reported resonance when available |
| `acceleration_g` | `g` | Preserve canonical acceleration in `g` |
| `acceleration_ms2` | `m/s^2` | Store when paper reports SI acceleration directly |
| `base_displacement_mm` | `mm` | Use vibration amplitude, not peak-to-peak unless explicitly noted |
| `load_resistance_ohm` | `ohm` | Convert kOhm and MOhm to absolute ohms |
| `power_uw` | `uW` | Prefer load power at the stated measurement condition |
| `voltage_v` | `V` | Preserve whether open-circuit, load voltage, or rectified voltage in notes |
| `current_ma` | `mA` | Preserve whether short-circuit or load current in notes |
| `stress_mpa` | `MPa` | Use root stress if explicitly stated |
| `tip_displacement_mm` | `mm` | Use tip amplitude if available |

## Conversion Rules

### Length and thickness

- Convert `m`, `cm`, and `um` to the canonical fields above.
- Do not merge substrate thickness and piezo thickness unless the paper only reports total thickness and layer separation is impossible.
- If only total beam thickness is available, store it in `beam_total_thickness_um` and leave layer-specific thicknesses null.

### Mass

- Convert `kg`, `mg`, and `g` to `tip_mass_g`.
- Only populate `tip_mass_g` when the paper clearly refers to a proof mass or tip mass, not total device mass.

### Frequency

- Convert `kHz` to `Hz`.
- Keep `excitation_frequency_hz` and `resonant_frequency_hz` separate.
- If the paper states "optimal frequency" but not "resonance", store the value in `resonant_frequency_hz` only if the context clearly indicates resonant operation.

### Acceleration

- Preserve acceleration primarily in `g`.
- If paper reports `m/s^2`, convert to `g` using `1 g = 9.81 m/s^2`.
- If acceleration is reported as peak-to-peak or RMS, keep the normalized scalar value but record the convention in `excitation_notes`.

### Resistance

- Convert `kOhm`, `MOhm`, and `GOhm` to `ohm`.
- If the paper only states "matched load", store that value in both `load_resistance_ohm` and `matched_load_resistance_ohm` when the context is clear.

### Power

- Convert `W`, `mW`, and `nW` to `uW`.
- Prefer directly reported load power.
- Do not back-compute power from voltage and resistance unless the paper explicitly ties them to the same operating condition and the computation is logged in `unit_normalization_log`.
- Keep peak power and average power distinct in `output_notes`.

### Voltage and current

- Convert voltage to `V` and current to `mA`.
- If the paper reports open-circuit voltage or short-circuit current, keep that qualifier in `output_notes`.
- Do not treat open-circuit voltage as load voltage.

### Stress and displacement

- Convert stress to `MPa`.
- Convert displacement to `mm`.
- If only strain is reported, do not synthesize stress without explicit model assumptions.

## Evidence Policy

- Every populated core field should have at least one evidence span when practical.
- Evidence can come from section text, tables, figure captions, equations, or appendices.
- Do not paraphrase numbers in the evidence quote; copy the local source phrase as-is.
- If a value is inferred by simple conversion, preserve the original text in `unit_normalization_log`.

## Missing and Uncertain Data

- If a field is not available, leave it null.
- If a field is ambiguous, leave it null and add a note instead of guessing.
- If a paper is outside scope, record the exclusion reason and do not force-fit values into cantilever fields.

## Cross-Field Consistency Checks

Before promoting a record to `candidate` or above, check:

- excitation and output metrics are tied to the same operating condition
- resistive load values are not confused with internal impedance
- geometry values are physically consistent in scale
- resonance and power values are not copied from unrelated modes or conditions
- the record can plausibly be mapped into verifier v1 inputs

## Promotion Guidance

Use these practical thresholds during curation:

- `candidate`: enough structure, excitation, and output fields to be useful for review
- `silver`: most benchmark-critical fields present, but one or more verifier-critical terms still uncertain
- `gold`: geometry, excitation, load, and key outputs are all sufficiently grounded to back-substitute into verifier v1

## Non-Goals

Do not use normalization to:

- invent missing layer dimensions
- infer nonlinear behavior from sparse text
- collapse different operating modes into one record
- convert broad performance claims into benchmark labels without evidence
