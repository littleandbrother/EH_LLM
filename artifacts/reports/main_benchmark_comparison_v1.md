# Main Benchmark Comparison (v1)

Runtime policy:

- calibrated frequency: `on`
- task-local anchors: `off`
- zero-shot / verifier-guided model: `kimi-k2.5` via DashScope coding endpoint

## frequency_matching / test-id

- classical run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-id_all_20260311_155132_113319`
- zero_shot_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-id_20260312_061601_216713`
- verifier_guided_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-id_20260312_144951_168102`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|---:|
| Random Search | 1.000 | 2.750 | 0.780 | 0.000 | 0.001 |
| GA | 1.000 | 2.625 | 0.745 | 0.000 | 0.001 |
| CMA-ES | 1.000 | 13.125 | 0.475 | 0.000 | 0.001 |
| BO | 1.000 | 3.375 | 0.837 | 0.000 | 0.001 |
| Kimi Zero-Shot | 0.500 | 1.000 | 0.365 | 0.000 | 2.474 |
| Kimi Verifier-Guided | 1.000 | 8.000 | 0.587 | 0.000 | 4.030 |

## frequency_matching / test-ood

- classical run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_frequency_matching_test-ood_all_20260311_155132_227910`
- zero_shot_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_frequency_matching_test-ood_20260312_061601_216649`
- verifier_guided_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_frequency_matching_test-ood_20260312_145028_529382`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|---:|
| Random Search | 0.500 | 2.200 | 0.337 | 0.200 | 0.001 |
| GA | 0.500 | 4.400 | 0.338 | 0.200 | 0.001 |
| CMA-ES | 0.300 | 5.667 | 0.223 | 0.200 | 0.001 |
| BO | 0.600 | 5.833 | 0.345 | 0.200 | 0.001 |
| Kimi Zero-Shot | 0.200 | 1.000 | 0.071 | 0.200 | 2.299 |
| Kimi Verifier-Guided | 0.600 | 7.000 | 0.266 | 0.200 | 8.327 |

## feasibility_repair / test-id

- classical run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-id_all_20260311_170126_997067`
- zero_shot_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-id_20260312_062010_734271`
- verifier_guided_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-id_20260312_140513_536411`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|---:|
| Random Search | 0.750 | 3.833 | 0.875 | 0.000 | 0.002 |
| GA | 0.875 | 6.429 | 0.938 | 0.000 | 0.001 |
| CMA-ES | 0.000 | - | 0.500 | 0.000 | 0.000 |
| BO | 1.000 | 7.000 | 1.000 | 0.000 | 0.000 |
| Kimi Zero-Shot | 0.125 | 1.000 | 0.562 | 0.000 | 3.017 |
| Kimi Verifier-Guided | 1.000 | 9.125 | 1.000 | 0.000 | 6.115 |

## feasibility_repair / test-ood

- classical run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/classical_baselines/vehbench_classical_feasibility_repair_test-ood_all_20260311_170126_995736`
- zero_shot_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/zero_shot_llm/vehbench_zero_shot_llm_feasibility_repair_test-ood_20260312_062010_734255`
- verifier_guided_llm run: `/Users/depengsu/Desktop/paper_story_agnet/EH-LLM-vehbench-baselines/artifacts/runs/verifier_guided_llm/vehbench_verifier_guided_llm_feasibility_repair_test-ood_20260312_140611_768999`

| Solver | Success Rate | Avg Queries To Success | Avg Best Normalized Objective | Avg Invalid Rate | Avg Wall Clock (s) |
|---|---:|---:|---:|---:|---:|
| Random Search | 0.625 | 4.800 | 0.812 | 0.000 | 0.001 |
| GA | 0.500 | 2.750 | 0.750 | 0.000 | 0.000 |
| CMA-ES | 0.125 | 12.000 | 0.562 | 0.000 | 0.000 |
| BO | 0.750 | 6.667 | 0.875 | 0.000 | 0.000 |
| Kimi Zero-Shot | 0.000 | - | 0.500 | 0.000 | 2.703 |
| Kimi Verifier-Guided | 0.750 | 9.167 | 0.875 | 0.000 | 13.405 |

## Decision

- keep verifier-guided repair in the primary result table; it is now competitive rather than exploratory
- extend the same local sensitivity + directional search policy to `frequency_matching` in the main benchmark view
- reason: verifier-guided frequency reaches `1.000` on `test-id` and `0.600` on `test-ood`, matching the current best OOD classical success rate (`BO = 0.600`) while clearly beating Kimi zero-shot (`0.500 / 0.200`)
- reason: verifier-guided repair reaches `1.000` on `test-id` and `0.750` on `test-ood`, matching or exceeding the strongest classical baseline and decisively beating zero-shot repair

