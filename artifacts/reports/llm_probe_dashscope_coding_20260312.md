# DashScope Coding LLM Probe 2026-03-12

Endpoint tested:

- `https://coding.dashscope.aliyuncs.com/v1`

Prompt suite:

- `minimal_json`
- `frequency_matching` one-task probe
- `feasibility_repair` one-task probe

## Summary

| Model | Minimal | Frequency | Repair | Frequency Feasible | Repair Feasible |
|---|---:|---:|---:|---:|---:|
| `kimi-k2.5` | `4.199s` | `1.978s` | `1.996s` | yes | no |
| `qwen3.5-plus` | `19.399s` | `89.677s` | timeout `136.632s` | no | no result |
| `glm-5` | `12.443s` | timeout `137.153s` | timeout `136.786s` | no result | no result |
| `MiniMax-M2.5` | `4.748s` | `110.394s` | timeout `136.582s` | no | no result |

## Decision

Use `kimi-k2.5` for subsequent VEHBench zero-shot experiments on the DashScope coding endpoint.

Reason:

- fastest on both structured VEHBench prompts
- only model that returned both task responses within a usable latency budget
- only model that produced a feasible `frequency_matching` candidate in the probe
- stable JSON formatting with low token overhead relative to alternatives

## Notes

- `qwen3.5-plus`, `glm-5`, and `MiniMax-M2.5` are currently too slow for the benchmark loop at this endpoint.
- `repair` remains harder than `frequency`; `kimi-k2.5` answered quickly but did not repair to feasibility in one shot.
- for future runs, prefer:
  - `VEHBENCH_LLM_BASE_URL=https://coding.dashscope.aliyuncs.com/v1`
  - `VEHBENCH_LLM_MODEL=kimi-k2.5`
