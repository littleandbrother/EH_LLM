# VEHBench Record Tier Report

This report is a pre-verifier stratification over valid extracted records.
Final `gold` promotion still requires verifier back-substitution once verifier v1 exists.

## Counts

- valid extracted records: `186`
- scope-passing records: `104`
- candidate records: `100`
- silver records: `78`
- gold records (pre-verifier): `68`

## Promotion Rules

- `candidate`: in-scope piezoelectric cantilever vibration record with at least one geometry field, one numeric excitation field, and one output metric.
- `silver`: candidate plus load resistance, excitation frequency, resonant frequency, one electrical output, and at least two geometry fields.
- `gold`: silver plus cantilever-ready geometry (`length_mm` and one secondary geometry field) and an excitation amplitude (`acceleration_g` or `displacement_mm`).

## Top Scope Exclusions

- `non_cantilever`: `32`
- `missing_piezo_signal`: `30`
- `excluded_regime`: `29`
- `non_vibration_excitation`: `19`
- `array_structure`: `4`
- `non_piezo_domain`: `3`

## Top Candidate Blockers

- `missing_numeric_excitation`: `2`
- `missing_geometry`: `2`

## Top Silver Blockers

- `missing_load`: `15`
- `missing_excitation_frequency`: `4`
- `missing_resonant_frequency`: `3`
- `insufficient_geometry_detail`: `2`
- `missing_electrical_output`: `2`

## Top Gold Blockers

- `missing_excitation_amplitude`: `8`
- `missing_length`: `2`

## Sample Gold Records

- `10_1002_admi_202300634`: Compositional Modification of Epitaxial Pb(Zr,Ti)O3 Thin Films for High‐Performance Piezoelectric Energy Harvesters
- `10_1016_j_aej_2020_11_024`: An experimental validation of a new shape optimization technique for piezoelectric harvesting cantilever beams
- `10_1016_j_apenergy_2020_115518`: Strongly coupled piezoelectric cantilevers for broadband vibration energy harvesting
- `10_1016_j_heliyon_2017_e00377`: Design optimization of PVDF-based piezoelectric energy harvesters
- `10_1016_j_sna_2019_06_034`: A packaged piezoelectric vibration energy harvester with high power and broadband characteristics
- `10_1016_j_sna_2020_112148`: Frequency tunable, flexible and low cost piezoelectric micro-generator for energy harvesting
- `10_1049_mnl_2017_0128`: Fabrication of piezoelectric vibration energy harvester using coatable PolyVinylidene DiFluoride and its characterisation
- `10_1063_1_4737170`: Cantilever driving low frequency piezoelectric energy harvester using single crystal material 0.71Pb(Mg1/3Nb2/3)O3-0.29PbTiO3
- `10_1063_1_4929844`: Two-dimensional concentrated-stress low-frequency piezoelectric vibration energy harvesters
- `10_1063_1_4948592`: Design and analysis of a MEMS-based bifurcate-shape piezoelectric energy harvester
- `10_1063_1_4962979`: A utility piezoelectric energy harvester with low frequency and high-output voltage: Theoretical model, experimental verification and energy storage
- `10_1063_1_5034495`: Low-frequency, broadband piezoelectric vibration energy harvester with folded trapezoidal beam
- `10_1063_1_5063268`: A broadband E-shaped piezoelectric energy harvester based on vortex-shedding induced vibration from low velocity liquid flow
- `10_1063_5_0022881`: An ultralow frequency, low intensity, and multidirectional piezoelectric vibration energy harvester using liquid as energy-capturing medium
- `10_1063_5_0105103`: High output performance of piezoelectric energy harvesters using epitaxial Pb(Zr, Ti)O3 thin film grown on Si substrate
- `10_1080_03772063_2021_1913071`: Multi-perforated Energy-Efficient Piezoelectric Energy Harvester Using Improved Stress Distribution
- `10_1080_10584587_2020_1803674`: Characterization and Optimization of Piezoelectric Bimorph Cantilever Structure for Ambient Vibration-Based Energy Harvesting Application
- `10_1080_14686996_2018_1508985`: Bimorph piezoelectric vibration energy harvester with flexible 3D meshed-core structure for low frequency vibration
- `10_1088_0964_1726_22_9_095019`: Piezoelectric energy harvesting from traffic-induced bridge vibrations
- `10_1088_1361_665x_ab19d2`: Low frequency piezoelectric P(VDF-TrFE) micro-cantilevers with a novel MEMS process for vibration sensor and energy harvester applications
