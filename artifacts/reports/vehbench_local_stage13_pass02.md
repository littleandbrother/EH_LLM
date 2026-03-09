# VEHBench Local Stage1-3 Pass 02

Date: 2026-03-09

## Objective

Raise the local focused-retrieval candidate pool from the pass-01 result
`1064 -> 651 -> 467 -> 61` to a stage-03 pool large enough to support remote
stage-4 LLM scoring and downstream PDF parsing.

Target for this pass: `stage03 >= 200`.

## Retrieval Changes

- Added expanded pass-02 search config:
  `pipelines/download/search_config_vehbench_pass02.yaml`
- Query family expanded from 8 seed queries to 24 focused queries.
- Pass-02 queries were biased toward:
  - experimental piezoelectric cantilever VEH
  - resonant frequency / base excitation wording
  - output power / measured performance wording
  - unimorph / bimorph / proof-mass / MEMS variants
- Retrieval ran incrementally on top of existing `papers.jsonl` via:
  `scripts/run_local_stage13_incremental.sh`

## Pipeline Notes

- `papers.jsonl` expanded from `1064` to `1908`.
- Abstract coverage after retrieval remained limited:
  - total papers: `1908`
  - with abstract: `1285`
  - missing abstract: `623`
- `backfill_abstracts.py --source oa` exposed a bug:
  `source=oa` still fell through to S2 for `source=both` records.
- Fixed `backfill_abstracts.py` so source filters now respect the selected
  backend and do not trigger cross-source fallback.
- OA-only backfill remained effectively unproductive on the new missing set
  (`90 fail / 0 ok` before stop), so this pass proceeded without waiting for
  backfill completion.

## Filter Changes

The original stage-03 gate was too narrow for VEHBench candidate building.

Updated `filter_03_quantitative.py` to:

- evaluate `title + abstract` instead of abstract only
- keep strict power-unit matching
- add explicit power phrases:
  - `output power`
  - `generated power`
  - `power density`
- broaden excitation-side matching to include:
  - `acceleration`
  - `base excitation`
  - `resonant frequency`
  - `frequency range`
  - `resonance`
  - `vibration level`

This keeps stage-03 as a quantitative-signal gate while avoiding systematic
loss of experimental papers whose abstracts describe excitation conditions in
words instead of only with `Hz/g/rpm`.

## Final Funnel

- `papers.jsonl`: `1908`
- `papers_stage01.jsonl`: `1104`
- `papers_stage02.jsonl`: `820`
- `papers_stage03.jsonl`: `301`

Pass-02 result:

`1908 -> 1104 -> 820 -> 301`

Compared with pass-01:

- metadata pool: `1064 -> 1908`
- stage03: `61 -> 301`

## Interpretation

- The retrieval expansion worked.
- The larger lift came from correcting the quantitative gate to match how real
  VEH abstracts report experimental results.
- Stage-03 now comfortably exceeds the `200+` target for remote stage-4.
- The stage-03 pool still contains off-scope records; this is expected and
  should be cleaned by remote stage-4 LLM scoring.

## Immediate Next Step

Sync the updated experiment worktree to `/root/EH-LLM-vehbench-exp` and run:

- `filter_04_llm_score.py` on the `301` stage-03 candidates
- then `cleanup_pdfs.py`
- then `mineru_runner.py`
- then `extract_schema.py`
