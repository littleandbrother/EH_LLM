# Silver Targeted Repair

This pass focused on exact `tier == silver` records after reclassification.

- exact silver before repair: `11`
- exact silver after repair: `10`
- records promoted to gold: `1` (`10_1063_1_5063268`)

## Promoted Record

- `10_1063_1_5063268`: filled `excitation.acceleration_g = 0.02` from explicit text evidence.

## Remaining Silver Records

- `10_1016_j_energy_2020_118752`: An experimental study on a novel cylinder harvester made of L-shaped piezoelectric coupled beams with a high efficiency
  blocker: `missing_excitation_amplitude`
  note: No explicit base acceleration/displacement found; the paper uses an excitation magnet brick and experimental frequency sweeps.
- `10_1088_0964_1726_20_2_025015`: The realization and performance of vibration energy harvesting MEMS devices based on an epitaxial piezoelectric thin film
  blocker: `missing_excitation_amplitude`
  note: Only an acceleration range (0.1 g to 1 g) is stated while outputs are normalized per g, so no single operating amplitude was added.
- `10_1108_cw_11_2017_0067`: Design and analysis of cantilever based piezoelectric vibration energy harvester
  blocker: `missing_excitation_amplitude`
  note: Paper is tip-excitation oriented and no explicit base acceleration/displacement value was found in the extracted text.
- `10_1115_smasis2010_3708`: An Experimental Performance Evaluation of DC Power Generation and Power Loss in Full-Bridge Rectifier of Cantilever Type of Piezoelectric Vibration Energy Harvester
  blocker: `missing_excitation_amplitude`
  note: The available operating condition is vibration velocity RMS, not direct acceleration/displacement in schema units.
- `10_1115_smasis2018_8022`: The Reliability Testing and Fatigue Behavior Study of Micro Piezoelectric Energy Harvester
  blocker: `missing_length`
  note: Still missing explicit beam length; only overall device area (~1 cm^2) is stated.
- `10_1299_jsmedmc_2010__607_1_`: 607 Power Generation Performance Evaluation of Vibration Energy Harvester with Piezocomposite and Power Loss Evaluation of a Full-Bridge Rectifier
  blocker: `missing_excitation_amplitude`
  note: The available operating condition is vibration velocity RMS, not direct acceleration/displacement in schema units.
- `10_3390_app5041942`: A Novel Piezoelectric Energy Harvester Using the Macro Fiber Composite Cantilever with a Bicylinder in Water
  blocker: `missing_excitation_amplitude`
  note: Flow-induced water excitation paper; amplitude is tied to water velocity rather than standard base acceleration/displacement.
- `10_3390_jcs4020039`: A Novel Design and Performance Results of An Electrically Tunable Piezoelectric Vibration Energy Harvester (TPVEH)
  blocker: `missing_excitation_amplitude`
  note: Electrically tunable harvester; no stable single excitation amplitude was found for the extracted operating point.
- `10_5539_jmsr_v6n4p5`: Modeling, Simulation and Optimization of Piezoelectric Bimorph Transducer for Broadband Vibration Energy Harvesting
  blocker: `missing_excitation_amplitude`
  note: Modeling/optimization paper; no explicit experimental base acceleration/displacement was found.
- `10_7567_jjap_56_04cc03`: High-efficiency MOSFET bridge rectifier for AlN MEMS cantilever vibration energy harvester
  blocker: `missing_length`
  note: Still missing explicit cantilever length from the parsed text.
