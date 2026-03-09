# VEHBench Local Stage1-3 Pass 01

Date: 2026-03-09

## Goal

Run the first local focused retrieval pass for the `VEHBench` workflow:

- local: focused retrieval + backfill + filter_01~03
- remote: stage4 + MinerU + extraction
- local: gold record curation + task generation

## Config

Search config:

- `pipelines/download/search_config_vehbench_seed.yaml`

Local runner:

- `scripts/run_local_stage13.sh`

## Result Funnel

- `papers.jsonl`: 1064
- `papers_stage01.jsonl`: 651
- `papers_stage02.jsonl`: 467
- `papers_stage03.jsonl`: 61

## Notes

- Retrieval used 8 focused queries centered on `piezoelectric cantilever vibration energy harvester`.
- Full abstract backfill was started, but stopped early because it was not the current critical path.
- At the time of filtering, 689 of 1064 papers already had abstracts.
- `filter_01~03` therefore ran on the currently available abstract-bearing subset.

## Interpretation

- The query family is high precision enough to produce a workable `stage03`.
- The current pass is not large enough by itself to support the final target of `150–250 gold records`.
- Additional focused retrieval passes will be needed after this pass is scored and inspected.

## Immediate Next Step

When remote connectivity is stable again:

1. sync current experiment worktree to `/root/EH-LLM-vehbench-exp`
2. run `filter_04_llm_score.py` remotely on current `papers_stage03.jsonl`
3. sync resulting stage4 corpus back if needed
4. continue with remote PDF cleanup / MinerU / extraction
