# VEHBench Master Execution Plan

Last updated: 2026-03-09

## 1. Document Purpose

This is the execution master plan for the `VEHBench` paper and project track inside `EH-LLM`.

This document is not a pitch deck.
It is the operational source of truth for:

- project scope
- benchmark definition
- implementation phases
- current status
- acceptance gates
- experiment plan
- handoff and reproducibility

Use this document to decide what to build next and what to reject.

Core decision rule:

> Does this work increase benchmark credibility, or does it distract from the paper?

If it increases benchmark credibility, do it.
If it distracts from the main paper line, cut it.

## 2. Paper Goal

The paper goal is:

Build a physics-grounded benchmark and verifier-based evaluation environment for piezoelectric cantilever vibration energy harvester inverse design, then use it to compare classical optimizers, LLMs, and verifier-guided agents under a unified protocol.

This paper is not trying to claim:

- a new harvester structure
- a giant new foundation model
- full CAD automation
- full circuit synthesis
- a complicated multi-agent system

It must prove five things:

1. VEH inverse design can be turned into a standardized, reproducible benchmark.
2. A fast, interpretable physics verifier can serve as the common evaluation environment.
3. Under the same budget and protocol, classical optimizers and language agents have different capability boundaries.
4. Structured physical feedback helps iterative design more than scalar reward alone.
5. The benchmark can produce traces that are useful for low-cost distilled solvers.

## 3. One-Sentence Positioning

`VEHBench` is a physics-grounded benchmark and verifier-based evaluation environment for piezoelectric cantilever vibration energy harvester inverse design.

## 4. Strict Scope

### 4.1 In Scope

Only build v1 for:

- piezoelectric cantilever VEH
- linear small-amplitude regime
- unimorph and bimorph
- optional tip mass
- sinusoidal base excitation
- resistive load
- inverse design tasks
- query-budgeted evaluation
- ID and OOD benchmark splits
- verifier-guided iterative solving

### 4.2 Explicitly Out of Scope

Do not pull these into the main paper:

- nonlinear bistable systems
- magnetic coupling
- array systems
- complex multi-DOF structures
- automatic CAD generation
- automatic circuit synthesis
- firmware/code generation
- full material discovery
- overly complex multi-agent orchestration

## 5. Current Repository Reality

The repository already contains a working literature pipeline, but it is not yet a finished benchmark repo.

Today the implemented chain is mostly:

`search_papers.py -> backfill_abstracts.py -> filter_01~04 -> cleanup_pdfs.py -> mineru_runner.py -> extract_schema.py`

That means the repo is currently strongest on:

- metadata search
- candidate paper filtering
- PDF ingestion
- MinerU parsing
- LLM-based structured extraction

What is not yet complete:

- fixed benchmark schema
- task generation
- verifier v1
- split generation
- unified evaluation protocol
- baseline solver suite
- benchmark reporting tables and figures

## 6. Current Status Snapshot

### 6.1 Completed

The following project infrastructure is already working or fixed:

- search and registry dedup are improved
- stage-4 core corpus write logic is fixed
- PDF cleanup script updates `pdf_path`
- MinerU success/failure accounting is fixed
- safe DOI filename matching is fixed in PDF cleanup
- MinerU now uses `mineru.cli.client`
- MinerU default model source is `modelscope`
- MinerU default device now adapts by platform:
  - Linux -> `cuda`
  - macOS -> `mps`
  - other -> `cpu`
- remote deploy/run/fetch scripts exist
- remote venv is installed and validated
- remote `openai` and `mineru` imports are verified
- downstream smoke path has been run through:
  - paper selection
  - PDF match
  - MinerU parse on GPU
  - normalized output
  - extraction of at least one paper

### 6.2 In Progress

These are partially complete and still need stabilization:

- rebuilding the literature corpus so data artifacts match the fixed code
- freezing extraction schema for benchmark use
- turning extracted paper records into benchmark-ready records
- defining candidate / silver / gold acceptance rules
- planning verifier v1 inputs, outputs, and violation labels

### 6.3 Not Started

These are still open:

- benchmark task generator
- split generator
- unified evaluation protocol
- classical optimizer baselines
- zero-shot / RAG / verifier-guided agent baselines
- distilled 8B solver
- FEM transfer validation
- hardware transfer validation

## 7. The Benchmark Object

The basic unit of the paper is not a paper.
The basic unit is a task.

Each task must be a standardized optimization problem with:

- task id
- task type
- source type
- fixed conditions
- variable bounds
- hard constraints
- objective
- verifier config
- query budget
- split
- evaluation metrics

Papers are only the upstream evidence source.
Tasks are the benchmark product.

## 8. Core Task Types

Keep only three main task types in v1.

### Task A: Frequency Matching

Given target resonance frequency and geometry constraints, find design parameters that hit the target.

Inputs:

- target resonance frequency
- geometry bounds
- material option
- load setting

Outputs:

- beam length
- beam width
- thickness terms
- tip mass
- load resistance

Metrics:

- frequency error threshold satisfaction
- full constraint satisfaction
- queries to success

### Task B: Constrained Power Maximization

Given excitation and geometry or stress constraints, maximize feasible output power.

Inputs:

- excitation frequency
- excitation acceleration
- geometry bounds
- stress limit

Outputs:

- design parameters

Metrics:

- feasible power
- normalized objective
- constraint satisfaction
- average queries to success

### Task C: Feasibility Repair

Given an invalid current design, iteratively repair it to a feasible state.

Inputs:

- task spec
- current candidate
- verifier feedback

Outputs:

- next parameter update

Metrics:

- repair success rate
- feasibility gain per query
- invalid proposal rate

## 9. Required Schemas

Schema work must be done before rebuilding the dataset.

### 9.1 Paper Extraction Schema

This defines what is extracted from each paper.

Minimum v1 fields:

- `paper_uid`
- `device_type`
- `structure_class`
- `beam_length_mm`
- `beam_width_mm`
- `substrate_thickness_um`
- `piezo_thickness_um`
- `tip_mass_g`
- `proof_mass_geometry`
- `material_piezo`
- `material_substrate`
- `load_resistance_ohm`
- `acceleration_g`
- `excitation_frequency_hz`
- `resonant_frequency_hz`
- `power_uw`
- `voltage_v`
- `stress_mpa`
- `displacement_mm`
- `excitation_type`
- `experiment_type`
- `evidence_spans`
- `unit_normalization_log`
- `extraction_confidence`

Planned artifact:

- `schemas/vehbench_paper_extraction_v1.json`

### 9.2 Task Schema

This defines the benchmark object.

Minimum v1 fields:

- `task_id`
- `source_type`
- `source_paper_uid`
- `task_type`
- `variable_bounds`
- `fixed_conditions`
- `hard_constraints`
- `objective`
- `verifier_version`
- `budget`
- `metric_spec`
- `split`
- `ood_tags`

Planned artifact:

- `schemas/vehbench_task_v1.json`

### 9.3 Verifier I/O Schema

This defines how all solvers interact with the evaluator.

Inputs:

- design parameters
- material parameters
- excitation settings
- load settings

Outputs:

- `resonant_frequency_hz`
- `tip_displacement_mm`
- `root_stress_mpa`
- `load_power_uw`
- `is_feasible`
- `violation_attribution`

Planned artifact:

- `schemas/vehbench_verifier_io_v1.json`

## 10. Data Ladder

All paper-derived data must move through a strict ladder.

### Layer 1: Raw Metadata

Source:

- OpenAlex
- Semantic Scholar

Current code base:

- `pipelines/download/search_papers.py`
- `pipelines/download/backfill_abstracts.py`

Outputs:

- `data_registry/papers.jsonl`
- canonical metadata table

### Layer 2: PDF Registry

Each paper must record:

- `paper_uid`
- `source`
- `download_url`
- `license`
- `sha256`
- `fetch_status`
- `local_path`

Planned artifact:

- `data_registry/pdf_registry.jsonl`

### Layer 3: Parsed Papers

Current code base:

- `pipelines/download/cleanup_pdfs.py`
- `ingestion/mineru_runner.py`

Outputs:

- `data_registry/raw/`
- `parsed_docs/`
- `normalized_docs/`
- `provenance_docs/`

### Layer 4: Extracted Records

Current code base:

- `pipelines/extract/extract_schema.py`

Outputs:

- `data_registry/extracted/`

### Layer 5: Curated Benchmark Records

New layers to build:

- `candidate_records`
- `silver_records`
- `gold_records`

Suggested output locations:

- `data_registry/benchmark/candidate_records.jsonl`
- `data_registry/benchmark/silver_records.jsonl`
- `data_registry/benchmark/gold_records.jsonl`

## 11. Record Acceptance Policy

Not all papers can become benchmark records.

### 11.1 First-Level Inclusion Tags

Use fixed tags such as:

- `include_linear_piezo_cantilever`
- `exclude_non_linear`
- `exclude_array`
- `exclude_insufficient_geometry`
- `exclude_no_experimental_numbers`
- `manual_review`

### 11.2 Record Tiers

Use these tiers:

- `raw_parsed`
- `candidate`
- `silver`
- `gold`

### 11.3 Gold Record Minimum Requirements

A `gold` record must include at least:

- key geometry parameters
- excitation conditions
- load conditions
- output metrics
- enough fields to back-substitute into the verifier

## 12. Verifier v1

The verifier is the center of the paper.

It does not need to model every physics effect.
It must be:

- fast
- stable
- interpretable
- consistent enough for benchmarking

### 12.1 Required Outputs

Keep only the core outputs:

- resonant frequency
- tip displacement
- root stress
- load power
- violation attribution

### 12.2 Fixed Violation Labels

Use fixed labels:

- `frequency_too_high`
- `frequency_too_low`
- `stress_exceeded`
- `displacement_exceeded`
- `power_below_target`
- `invalid_geometry`

### 12.3 Validation Sources

Verifier validation must come from:

- literature back-substitution
- FEM transfer
- hardware transfer

## 13. Benchmark Construction Plan

Build tasks from two sources.

### 13.1 Paper-Grounded Tasks

Generated directly from `gold` records.

Use these for:

- realism
- evidence traceability
- paper-grounded evaluation claims

### 13.2 Synthetic Tasks

Generated by sampling within physically supported ranges inferred from `gold` records.

Use these for:

- scale
- controllable OOD split design
- richer optimization evaluation

### 13.3 Why Both Are Required

Only paper-grounded tasks:

- too small
- not enough coverage

Only synthetic tasks:

- easier to challenge on realism

Best v1 design:

- gold-supported synthetic generation plus paper-grounded tasks

## 14. Split Design

Split design must prevent leakage.

### 14.1 Rules

- tasks derived from the same paper must not cross train and test
- close design families should not be split carelessly
- OOD must be explicit, not rhetorical

### 14.2 Final Splits

Use:

- `train`
- `val`
- `test-id`
- `test-ood`

### 14.3 OOD Axes

Suggested axes:

- unseen geometry regime
- unseen excitation range
- unseen material combination
- unseen load regime

## 15. Unified Evaluation Protocol

All solvers must share:

- the same variable space
- the same constraints
- the same verifier
- the same query budget
- the same task split

Explicitly forbid:

- private prompt advantages
- extra test leakage
- budget mismatch
- hidden non-public augmentation

The benchmark question is not "who is smartest".
It is:

- who finds feasible designs more reliably
- who is more query-efficient
- who is more stable under OOD
- who uses structured feedback better

## 16. Solver Suite

Keep the baseline suite compact but strong.

### 16.1 Classical Optimizers

Required:

- Random Search
- Genetic Algorithm
- CMA-ES
- Bayesian Optimization

### 16.2 LLM Baselines

Required:

- Zero-shot LLM
- RAG LLM
- Verifier-guided LLM agent

### 16.3 Distilled Baseline

Required:

- Distilled 8B policy model

Total v1 benchmark suite:

- 8 solvers

## 17. Verifier-Guided Agent Contract

Do not make the agent overly open-ended.

Inputs:

- task spec
- current candidate
- latest verifier feedback
- optional retrieved literature snippets

Output JSON should be fixed as:

- `analysis_summary`
- `parameter_update`
- `expected_effect`

The agent role is not free chat.
It is:

- error attribution
- next-step correction

This makes the system benchmarkable and easier to distill.

## 18. Teacher Traces and Distillation

Distillation is a secondary contribution, not the core paper.

### 18.1 Trace Selection Policy

Keep only traces that are:

- successful
- converged in 3 to 8 steps
- physically reasonable
- not prompt-hack dependent

### 18.2 Distillation Sample Types

Use two sample types:

1. first-shot proposal
2. single-step repair

### 18.3 Distilled Model Claim

The distilled model is not there to prove giant-model training.
It is there to prove that benchmark-generated verifier-grounded traces can produce a lower-cost solver.

## 19. Research Questions

All experiments must serve these research questions.

### RQ1: Is the benchmark credible?

Check:

- funnel transparency
- task distributions
- gold and silver construction rules
- split design
- extraction quality

### RQ2: Is the verifier credible?

Check:

- literature back-substitution
- FEM validation
- hardware transfer
- ranking consistency
- feasibility consistency

### RQ3: How do solvers compare under a unified budget?

Check:

- CSR
- queries to success
- normalized objective
- wall-clock
- token or dollar cost

### RQ4: Does structured feedback help?

Compare:

- zero-shot LLM
- scalar-reward LLM
- structured verifier-guided LLM

### RQ5: Who is more robust under OOD?

Compare:

- success-rate drop
- invalid proposal increase
- repair efficiency drop

## 20. Required Experiments

### Experiment 1: Benchmark Data and Distribution Statistics

Show:

- raw candidate paper count
- parseable paper count
- candidate / silver / gold counts
- task counts
- task type distribution
- geometry distribution
- frequency distribution
- excitation distribution
- load distribution

Purpose:

- prove the benchmark is not arbitrarily assembled

### Experiment 2: Verifier Validation

#### 2.1 Literature Back-Substitution

Metrics:

- frequency MAPE
- power MAPE
- stress decision accuracy

#### 2.2 FEM Transfer

Metrics:

- absolute error
- rank correlation

#### 2.3 Hardware Transfer

Metrics:

- trend consistency
- feasibility consistency
- rank consistency

Purpose:

- show that the verifier is approximate but valid enough as the benchmark semantic layer

### Experiment 3: Main Benchmark Results

Compare all baselines on ID test using:

- CSR
- best normalized objective
- average queries to success
- invalid proposal rate
- wall-clock
- token or dollar cost

### Experiment 4: OOD Generalization

Compare:

- CSR drop
- invalid rate increase
- objective degradation

### Experiment 5: Structured Feedback Ablation

Compare:

- no verifier
- scalar reward only
- structured feedback

Purpose:

- prove structured feedback improves repair and convergence

### Experiment 6: Retrieval and Training Source Ablation

Compare:

- no retrieval
- retrieval enabled
- literature-only support
- synthetic-only support
- mixed support

### Experiment 7: Distilled Small Model

Compare:

- teacher verifier-guided agent
- distilled 8B

Metrics:

- CSR
- queries
- cost
- latency

## 21. Paper Figures and Tables

### Figures

- Figure 1: overall system diagram
- Figure 2: source-to-task funnel
- Figure 3: verifier architecture
- Figure 4: benchmark distributions
- Figure 5: main result Pareto plot
- Figure 6: external validation plot
- Figure 7: repair trajectory case study

### Tables

- Table 1: benchmark summary
- Table 2: verifier validation
- Table 3: main benchmark results
- Table 4: OOD generalization
- Table 5: ablations
- Table 6: reproducibility and artifacts

## 22. Implementation Phases

This is the recommended build order.

### Phase 1: Definitions and Data Bedrock

Goal:

- freeze schemas
- make metadata canonical
- make PDF registry traceable

Tasks:

1. define paper extraction schema
2. define task schema
3. define verifier I/O schema
4. freeze unit normalization rules
5. rebuild metadata registry
6. build canonical `paper_uid`
7. build PDF registry

Primary deliverables:

- `schemas/vehbench_paper_extraction_v1.json`
- `schemas/vehbench_task_v1.json`
- `schemas/vehbench_verifier_io_v1.json`
- `docs/vehbench_normalization_rules.md`
- `data_registry/papers.jsonl`
- `data_registry/pdf_registry.jsonl`

Exit criteria:

- schema fields are frozen
- metadata is deduplicated
- PDF registry is auditable

### Phase 2: Parsing and Structured Extraction

Goal:

- produce stable paper records from PDFs

Tasks:

1. rebuild stage-4 corpus with fixed code
2. ensure `pdf_path` is filled
3. run MinerU over available PDFs
4. run extraction into structured records
5. add evidence spans and normalization logs
6. classify records into raw and candidate

Primary deliverables:

- refreshed `papers_stage04_core_corpus.jsonl`
- refreshed `parsed_docs/`
- refreshed `normalized_docs/`
- refreshed `data_registry/extracted/`
- `data_registry/benchmark/candidate_records.jsonl`

Exit criteria:

- extraction pipeline is stable
- a non-trivial set of complete candidate records exists

### Phase 3: Candidate, Silver, Gold Curation

Goal:

- create benchmark-ready paper records

Tasks:

1. define candidate / silver / gold rules
2. back-substitute extracted records into verifier
3. score physical consistency
4. label acceptance tier
5. create review queue for borderline papers

Primary deliverables:

- `candidate_records.jsonl`
- `silver_records.jsonl`
- `gold_records.jsonl`
- curation logs and decision reasons

Exit criteria:

- gold records are sufficient to seed benchmark tasks

### Phase 4: Verifier v1

Goal:

- produce a fast and stable evaluator

Tasks:

1. implement v1 cantilever verifier
2. define violation attribution mapping
3. validate against literature back-substitution
4. validate against FEM cases
5. validate against hardware cases

Primary deliverables:

- `vehbench/verifier/v1/`
- verifier tests
- validation reports

Exit criteria:

- verifier outputs are stable
- literature consistency is acceptable

### Phase 5: Benchmark Task Generation

Goal:

- convert gold records into standardized tasks

Tasks:

1. generate paper-grounded tasks
2. generate gold-supported synthetic tasks
3. assign task ids
4. compute budgets and metric specs
5. assign ID and OOD tags

Primary deliverables:

- `data_registry/benchmark/tasks_train.jsonl`
- `data_registry/benchmark/tasks_val.jsonl`
- `data_registry/benchmark/tasks_test_id.jsonl`
- `data_registry/benchmark/tasks_test_ood.jsonl`

Exit criteria:

- task schema is stable
- split leakage checks pass
- benchmark size is sufficient

### Phase 6: Unified Evaluation Protocol

Goal:

- make solver comparison fair

Tasks:

1. define solver API
2. define query budget rules
3. define logging and trace schema
4. define cost accounting
5. define evaluation aggregation scripts

Primary deliverables:

- `vehbench/eval/`
- run config templates
- evaluation scripts

Exit criteria:

- every solver can be run under one protocol

### Phase 7: Baselines

Goal:

- establish strong reference points

Tasks:

1. Random Search
2. GA
3. CMA-ES
4. BO
5. zero-shot LLM
6. RAG LLM
7. verifier-guided agent

Primary deliverables:

- `vehbench/solvers/`
- baseline result tables

Exit criteria:

- all baseline solvers run on the same split and budget

### Phase 8: Distillation

Goal:

- test whether benchmark traces can produce a cheaper solver

Tasks:

1. collect high-quality teacher traces
2. create trace dataset
3. train distilled 8B
4. evaluate distilled solver

Primary deliverables:

- trace dataset
- training scripts
- distilled checkpoints
- distilled evaluation report

Exit criteria:

- distilled model has a clear cost or latency advantage

### Phase 9: Artifact and Paper Finalization

Goal:

- make the project submission-ready

Tasks:

1. package data artifact
2. package code artifact
3. freeze versions
4. generate benchmark summary tables
5. generate paper figures
6. run mock review

Primary deliverables:

- dataset card
- model card
- reproducibility scripts
- paper figures and tables
- submission checklist

Exit criteria:

- an external operator can rerun the benchmark artifact

## 23. Acceptance Gates by Phase

### Phase 1 Gate

- schemas frozen
- metadata deduplicated
- PDF registry traceable

### Phase 2 Gate

- extraction pipeline stable
- enough structurally complete candidate records exist

### Phase 3 Gate

- candidate / silver / gold tiers are reproducible
- gold records can be back-substituted

### Phase 4 Gate

- verifier outputs are stable
- literature consistency is acceptable

### Phase 5 Gate

- task schema frozen
- split leakage checks pass
- benchmark size is enough

### Phase 6 Gate

- all solvers run under unified protocol

### Phase 7 Gate

- reference baselines all run successfully

### Phase 8 Gate

- distilled model has clear efficiency value

### Phase 9 Gate

- data, code, scripts, docs, and results are reproducible

## 24. Minimum Publishable Version

If time is constrained, the minimum credible submission target is:

- only piezo cantilever + sinusoidal + resistive load
- 150 to 250 gold records
- 3000 to 5000 benchmark tasks
- verifier calibrated with literature + FEM + limited hardware
- 4 classical optimizer baselines
- 3 LLM baselines
- 1 distilled 8B baseline
- full artifact package

This is enough for a serious Datasets and Benchmarks paper if executed cleanly.

## 25. Immediate Execution Queue

Do these next, in order.

### Immediate Block 1: Freeze Schemas

1. create `vehbench_paper_extraction_v1`
2. create `vehbench_task_v1`
3. create `vehbench_verifier_io_v1`
4. write normalization rules

### Immediate Block 2: Rebuild Current Literature Artifacts

1. rerun metadata pipeline with fixed dedup
2. rerun stage-4 filtering with fixed write logic
3. rebuild or backfill PDF registry
4. rerun PDF cleanup so `pdf_path` is trustworthy

### Immediate Block 3: Produce First Benchmark-Ready Paper Records

1. rerun MinerU on a controlled corpus slice
2. rerun extraction with fixed schema
3. create first `candidate_records.jsonl`
4. define silver and gold promotion rules

### Immediate Block 4: Implement Verifier v1

1. define formula set and assumptions
2. implement verifier API
3. test on paper back-substitution cases
4. log violation attribution consistently

### Immediate Block 5: Generate First Task Set

1. generate paper-grounded tasks from gold records
2. create a tiny ID and OOD split
3. run one classical optimizer and one LLM baseline
4. confirm end-to-end evaluation loop

## 26. Repo Mapping

Use the current repo like this.

### Existing Files to Reuse

- `pipelines/download/search_papers.py`
- `pipelines/download/backfill_abstracts.py`
- `pipelines/download/filtering/filter_01_topic.py`
- `pipelines/download/filtering/filter_02_experiment.py`
- `pipelines/download/filtering/filter_03_quantitative.py`
- `pipelines/download/filtering/filter_04_llm_score.py`
- `pipelines/download/cleanup_pdfs.py`
- `ingestion/mineru_runner.py`
- `pipelines/extract/extract_schema.py`
- `scripts/deploy_remote.sh`
- `scripts/run_remote.sh`
- `scripts/fetch_remote.sh`

### New Areas to Add

- `schemas/vehbench_*`
- `vehbench/verifier/`
- `vehbench/tasks/`
- `vehbench/solvers/`
- `vehbench/eval/`
- `data_registry/benchmark/`
- `artifacts/reports/vehbench/`

## 27. Source-of-Truth Priority

When documents conflict, use this order:

1. this file
2. `docs/PROJECT_HANDOFF.md`
3. actual code
4. older roadmap or aspirational README content

The older `TASK_ROADMAP.md` and `VEHBENCH_NEURIPS_DB_EXECUTION_BLUEPRINT.md` remain useful context, but this file is the operative benchmark build plan.
