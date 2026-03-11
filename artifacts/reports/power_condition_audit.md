# Power Condition Audit

This audit keeps only records where `power / load / excitation frequency / acceleration` are judged to refer to the same operating condition with conservative evidence rules.

- ready mappings audited: `52`
- kept in power-gold subset: `18`
- rejected: `34`

## Rejection Reasons

- `comparison_table_or_review_context`: `2`
- `missing_acceleration_evidence`: `2`
- `mixed_condition_sections`: `25`
- `modeling_or_simulation_dominant_context`: `2`
- `table_condition_not_fully_locked`: `2`
- `theoretical_or_simulated_load_not_condition_locked`: `1`

## Kept Papers

- `10_1002_admi_202300634`: all power/load/frequency/acceleration evidence is locked to the same performance section
- `10_1016_j_apenergy_2020_115518`: power quote is explicitly conditioned on the same load, excitation frequency, and acceleration that appear in the support quote
- `10_1016_j_heliyon_2017_e00377`: all four fields are extracted from the same experimental results section
- `10_1016_j_sna_2019_06_034`: abstract-level summary states power, load, frequency, and acceleration together as one operating point
- `10_1049_mnl_2017_0128`: power and load come from the same quote and the frequency/acceleration evidence refers to the same characterization run
- `10_1063_1_4737170`: all four fields are aligned in the same paper-level experimental summary
- `10_1063_1_4929844`: power, load, and frequency are tied in the same quote and acceleration is from the same device context
- `10_1063_1_4948592`: power/load/frequency/acceleration are all extracted from the same article-level condition statement
- `10_1063_5_0105103`: abstract-level summary gives one coherent operating condition for power, load, frequency, and acceleration
- `10_1080_14686996_2018_1508985`: all four fields are grounded in the same results section
- `10_1088_1742_6596_1052_1_012038`: all four fields are grounded in the same micro-harvester performance section
- `10_1109_icsens_2016_7808560`: abstract-level summary provides a single measured power condition
- `10_1109_sensor_2009_5285375`: abstract-level summary provides one consistent power/load/frequency/acceleration tuple
- `10_1186_s40486_017_0054_x`: abstract-level summary provides one consistent power/load/frequency/acceleration tuple
- `10_12913_22998624_110175`: abstract-level summary provides one consistent power/load/frequency/acceleration tuple
- `10_3390_mi12070772`: all four fields are grounded in the same prototype performance analysis section
- `10_3390_s21144747`: all four fields are grounded in the same output performance section
- `10_7567_jjap_55_06gp14`: all four fields are grounded in the same fabrication and measurement section
