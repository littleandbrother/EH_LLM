# EH-LLM Project Handoff

Last updated: 2026-03-09

## Scope

This document is the operational handoff for `EH-LLM`.
It is written for both humans and AI agents.
It focuses on the real, current state of the repository rather than the aspirational README.

The primary use case of this project today is:

1. Search and curate vibration energy harvesting (VEH) papers.
2. Build a core literature corpus.
3. Parse PDFs with MinerU.
4. Normalize parsed content into machine-usable JSON.
5. Extract structured EH knowledge with an LLM.

## Important Reality Check

The top-level [README.md](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/README.md) is high-level and partially aspirational.
The codebase currently operates as a practical literature pipeline, not yet as a complete polished "EH-GPT system OS".

If there is a conflict between `README.md` and the code/scripts described below, trust the code and this handoff.

For the benchmark-paper build plan, read:

- `docs/VEHBENCH_MASTER_EXECUTION_PLAN.md`

That file is the execution source of truth for the `VEHBench` paper track.

## Repository Role

`EH-LLM` is the active git repository.

There is also a sibling directory named `EH-LLM-dev` outside this repo.
It was used as a development copy, but the current maintained code changes have been synchronized into `EH-LLM`.
Treat `EH-LLM` as the source of truth unless explicitly told otherwise.

## Current High-Level Pipeline

The practical end-to-end workflow is:

1. `pipelines/download/search_papers.py`
   Purpose: query Semantic Scholar and OpenAlex for VEH-related papers, merge results into `data_registry/papers.jsonl`.

2. `pipelines/download/backfill_abstracts.py`
   Purpose: fill missing abstracts in the registry.

3. Filtering stages under `pipelines/download/filtering/`
   - `filter_01_topic.py`
   - `filter_02_experiment.py`
   - `filter_03_quantitative.py`
   - `filter_04_llm_score.py`

4. `pipelines/download/cleanup_pdfs.py`
   Purpose: align/copy existing PDFs into `data_registry/raw` and update `pdf_path`.

5. `ingestion/mineru_runner.py`
   Purpose: run MinerU on PDFs and generate:
   - `parsed_docs/`
   - `normalized_docs/`
   - `provenance_docs/`

6. `pipelines/extract/extract_schema.py`
   Purpose: run LLM extraction over normalized docs into `data_registry/extracted/`.

## Current Artifact Counts

Current local counts in `data_registry` and downstream outputs:

- `papers.jsonl`: 2144
- `papers_stage01.jsonl`: 1181
- `papers_stage02.jsonl`: 795
- `papers_stage03.jsonl`: 150
- `papers_stage04_core_corpus.jsonl`: 150
- `data_registry/raw/` files: 104
- `normalized_docs/` files: 1
- `provenance_docs/` files: 100
- `data_registry/extracted/` files: 3

Interpretation:

- Upstream search/filter artifacts exist and are non-trivial.
- Downstream parse/extract artifacts are inconsistent with each other.
- This is expected given earlier ingestion state-machine bugs and partial historical runs.

## Current Data State vs Code State

Code state and data state are not fully aligned.

Examples:

- `filter_04_llm_score.py` has been fixed so that reruns only preserve `design_score >= 6` papers in stage 4 output.
- However, the current checked-in `papers_stage04_core_corpus.jsonl` is still a legacy output with 150 rows, and 6 of them are still `decision != KEEP` or `design_score < 6`.

This means:

- The code is better than the current artifacts.
- A clean rerun is still needed to make the data match the code.

## Completed Engineering Fixes

The following code fixes have already been applied in this repo:

### 1. Search registry dedup/merge

File:
- [search_papers.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/search_papers.py)

What was fixed:

- Dedup/merge logic was strengthened so DOI/title normalization is more stable.
- The registry is now much closer to being idempotent across reruns.

Why it matters:

- Previously, repeated search runs could accumulate duplicate DOI entries.

### 2. Stage 4 write logic

File:
- [filter_04_llm_score.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/filtering/filter_04_llm_score.py)

What was fixed:

- Stage 4 now rewrites output so only kept papers remain in `papers_stage04_core_corpus.jsonl`.
- Progress tracking was added so already processed papers do not have to be re-scored.

Why it matters:

- Previously, dropped papers still leaked into the "core corpus".

### 3. PDF cleanup/import script

File:
- [cleanup_pdfs.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/cleanup_pdfs.py)

What was fixed:

- Removed hardcoded dependence on `EH-LLM-dev`.
- Added parameterized PDF import behavior.
- Added registry `pdf_path` backfill/update support.

Why it matters:

- The old script was brittle and did not make downstream status accounting trustworthy.

### 4. MinerU processing state machine

File:
- [mineru_runner.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/ingestion/mineru_runner.py)

What was fixed:

- Parsing success/failure accounting was corrected.
- Failed output directories are no longer treated as successful completion.
- Processing now uses safer success checks.
- MinerU invocation has been updated to use the correct module entrypoint pattern.

Why it matters:

- Earlier status could report impossible numbers or permanently skip failed papers.

### 5. Remote deployment workflow

Files:
- [deploy_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/deploy_remote.sh)
- [run_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/run_remote.sh)
- [fetch_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/fetch_remote.sh)
- [\.remote.env.example](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/.remote.env.example)

What was added/fixed:

- Local-to-remote deploy via `rsync`.
- Remote execution via `ssh + tmux`.
- Fetch-back script for logs/results.
- Port support.
- `.remote.env` support.
- Multi-requirements bootstrap support.
- Bootstrap now upgrades `pip`, `setuptools`, `wheel`.

Why it matters:

- The project can now be edited locally and run remotely with repeatable commands.

### 6. Dependency declarations for extraction and MinerU

Files:
- [pipelines/extract/requirements.txt](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/extract/requirements.txt)
- [ingestion/requirements.txt](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/ingestion/requirements.txt)

What was added:

- Extract chain requirements now explicitly include `openai`.
- Ingestion requirements now explicitly include `mineru[pipeline]`.

Why it matters:

- The repository now declares key runtime dependencies instead of relying on manual memory.

## Remote Environment Status

The remote dependency installation has been completed and validated.

Validated remote environment:

- remote venv path: `/root/ehllm-venv`
- temporary install dir for large pip unpack/build operations: `/dev/shm/ehllm-tmp`

Validated package status on remote:

- `openai` import works
- `mineru` import works
- `mineru` version is `2.7.6`
- `openai` version is `2.26.0`

Important implementation note:

- The final stable arrangement is:
  - install environment on `/root/ehllm-venv`
  - use `/dev/shm/ehllm-tmp` as `TMPDIR`
- Do not place the final venv itself under `/dev/shm`, because that mount is `noexec` and native extension modules will fail to load.

## Current Background Job State

As of this handoff:

- no long-running project job is active on the remote server
- no `search_papers.py`, `mineru_runner.py`, or `extract_schema.py` process is currently running
- no active `tmux` session is required for the project at this moment

In other words, the environment is prepared, but a new operator still needs to launch the next pipeline stage.

## Work Completed vs In Progress vs Next

### Completed

- Search/dedup code improved.
- Stage 4 logic fixed in code.
- PDF cleanup/import script fixed in code.
- MinerU runner state machine fixed in code.
- Remote deploy/run/fetch tooling added.
- Remote extraction-chain dependencies installed and validated.
- `openai` and `mineru` imports verified on the remote host.

### In Progress / Partially Complete

- The code fixes exist, but the data products have not all been rebuilt from scratch.
- Current stage 4 output is still a legacy artifact and needs rerun.
- Current parse/normalized/provenance/extracted outputs are historically inconsistent.
- `papers.jsonl` should still be regenerated once under the new dedup logic to make the registry match the fixed code.

### Next Recommended Steps

Recommended next actions, in order:

1. Regenerate `papers.jsonl` with the fixed search logic.
2. Re-run stages 1 to 4 cleanly.
3. Rebuild the raw PDF registry and ensure `pdf_path` is correct.
4. Re-run `mineru_runner.py` from the corrected stage 4 corpus.
5. Rebuild `normalized_docs/` and `provenance_docs/`.
6. Run a small extraction smoke test with `extract_schema.py --limit 1`.
7. Only after smoke success, run the full extraction batch.

## Known Problems Still Remaining

These are not code regressions from today; they are remaining operational/data tasks:

1. Legacy stage 4 data is not yet regenerated.
2. Downstream artifacts are inconsistent:
   - `normalized_docs/` count is much lower than `provenance_docs/`
   - `extracted/` is only partially populated
3. The current repository contains uncommitted local changes.
4. The remote workflow depends on a local ignored `.remote.env`.

## Current Uncommitted Local Changes

At the time of writing, local git status includes uncommitted changes in:

- [\.gitignore](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/.gitignore)
- [search_papers.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/search_papers.py)
- [cleanup_pdfs.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/cleanup_pdfs.py)
- [filter_04_llm_score.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/filtering/filter_04_llm_score.py)
- [mineru_runner.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/ingestion/mineru_runner.py)
- [ingestion/requirements.txt](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/ingestion/requirements.txt)
- [pipelines/extract/requirements.txt](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/extract/requirements.txt)
- [scripts/deploy_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/deploy_remote.sh)
- [scripts/run_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/run_remote.sh)
- [scripts/fetch_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/fetch_remote.sh)
- [\.remote.env.example](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/.remote.env.example)
- [VEHBENCH_NEURIPS_DB_EXECUTION_BLUEPRINT.md](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/VEHBENCH_NEURIPS_DB_EXECUTION_BLUEPRINT.md)

This handoff file is also a new local change until committed.

## Reproduction / Restart Checklist

If a new operator wants to continue from this point:

1. Read this file first.
2. Check current git status.
3. Inspect `.remote.env` locally.
4. Confirm remote connectivity works.
5. Confirm remote venv works:

```bash
ssh -p <PORT> <HOST> 'source /root/ehllm-venv/bin/activate && python - <<\"PY\"
import openai, mineru
print(openai.__version__)
print(getattr(mineru, \"__version__\", \"imported\"))
PY'
```

6. Rebuild upstream registry/filter artifacts before trusting downstream outputs.

## Typical Remote Workflow

From the local repo root:

```bash
cd /Users/depengsu/Desktop/paper_story_agnet/EH-LLM
scripts/deploy_remote.sh
```

Run a remote command in `tmux`:

```bash
cd /Users/depengsu/Desktop/paper_story_agnet/EH-LLM
scripts/run_remote.sh --command "python ingestion/mineru_runner.py --status"
```

Fetch outputs back:

```bash
cd /Users/depengsu/Desktop/paper_story_agnet/EH-LLM
scripts/fetch_remote.sh
```

For large installs on constrained disks, the working pattern that succeeded was:

```bash
TMPDIR=/dev/shm/ehllm-tmp
source /root/ehllm-venv/bin/activate
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r pipelines/extract/requirements.txt -r ingestion/requirements.txt
```

## Suggested Clean Rebuild Sequence

If you want the repository state to become coherent again, use this sequence:

1. Back up current `data_registry/`, `parsed_docs/`, `normalized_docs/`, `provenance_docs/`, `runs/`.
2. Re-run `search_papers.py`.
3. Re-run `backfill_abstracts.py` if needed.
4. Re-run filter stages 1 to 4.
5. Re-run `cleanup_pdfs.py`.
6. Verify `pdf_path` population.
7. Re-run `mineru_runner.py`.
8. Verify normalized/provenance counts align.
9. Run `extract_schema.py --limit 1`.
10. Run full extraction only after the smoke test succeeds.

## Key Entry Files

Use these files as the main entry points for future analysis:

- [README.md](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/README.md)
- [PROJECT_HANDOFF.md](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/docs/PROJECT_HANDOFF.md)
- [search_papers.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/search_papers.py)
- [filter_04_llm_score.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/filtering/filter_04_llm_score.py)
- [cleanup_pdfs.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/download/cleanup_pdfs.py)
- [mineru_runner.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/ingestion/mineru_runner.py)
- [extract_schema.py](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/pipelines/extract/extract_schema.py)
- [deploy_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/deploy_remote.sh)
- [run_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/run_remote.sh)
- [fetch_remote.sh](/Users/depengsu/Desktop/paper_story_agnet/EH-LLM/scripts/fetch_remote.sh)

## Final Summary

The repository is operational but not yet cleanly rebuilt.

The good news:

- the critical code bugs identified in search, stage 4, cleanup, MinerU status handling, and remote execution have been fixed
- the remote environment can now import both `openai` and `mineru`

The remaining work is mainly operational:

- rerun the pipeline so data products catch up with the corrected code
- then validate parse/extract outputs end to end
