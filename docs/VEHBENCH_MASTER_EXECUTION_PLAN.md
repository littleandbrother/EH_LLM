# VEHBench Master Execution Plan

Last updated: 2026-03-11

## 1. Document Purpose

This is the execution source of truth for the `VEHBench` paper track inside `EH-LLM`.

Use this document to decide:

- what the paper is actually about
- what the benchmark v1 will and will not include
- what the current repo already supports
- what needs to be built next
- what should be explicitly cut from the v1 submission line

Core decision rule:

> Does this work increase benchmark credibility, or does it distract from the paper?

If it increases benchmark credibility, do it.
If it distracts from the main paper line, cut it.

## 2. Reframed Paper Thesis

`VEHBench` is not a claim about a better harvester design method.
It is not primarily a claim about LLM intelligence.

The v1 paper thesis is:

`VEHBench` is a paper-grounded benchmark and calibrated evaluation environment for inverse design of linear piezoelectric cantilever vibration energy harvesters.

The benchmark contribution has three pillars:

1. a reproducible task set grounded in literature-derived design records
2. a fast verifier that is good enough to serve as a common evaluator
3. a fair solver comparison protocol under shared budgets and shared task definitions

## 3. Strategic Rewrite

The project is now intentionally centered on:

- `frequency-first`
- `power-subset`
- `baseline-before-agent`

This means:

- frequency matching and feasibility are the main v1 benchmark axes
- power is retained, but only as a narrower audited subset task
- classical optimizers come before complex LLM agents
- distillation is a late-stage bonus, not a v1 dependency

## 4. What v1 Will and Will Not Claim

### 4.1 Primary Claims

The paper should aim to prove these four statements:

1. Linear piezoelectric cantilever VEH inverse design can be turned into a standardized, reproducible benchmark.
2. A calibrated fast verifier can provide a unified evaluation environment for that benchmark.
3. Under a shared protocol, classical optimizers and language-based solvers show different capability boundaries.
4. Structured physical feedback is genuinely useful for iterative repair and inverse design.

### 4.2 Claims v1 Should Avoid

Do not make these core claims in v1:

- full-spectrum VEH design automation
- universally accurate power prediction across all paper conditions
- superiority of LLMs over all classical optimizers
- a general benchmark for all energy harvesting architectures
- a complete distilled policy model contribution

## 5. Strict v1 Scope

### 5.1 In Scope

Only build v1 for:

- piezoelectric cantilever VEH
- linear small-amplitude regime
- unimorph and bimorph
- optional proof mass / tip mass
- sinusoidal base excitation
- resistive electrical load
- inverse design tasks
- query-budgeted evaluation
- ID and OOD splits
- verifier-guided repair loops

### 5.2 Explicitly Out of Scope

Do not pull these into the main paper:

- nonlinear bistable systems
- magnetic coupling as a main setting
- VEH arrays
- complicated multi-DOF structures
- fluid-flow or vortex-dominant excitation as a main setting
- full CAD or geometry synthesis
- circuit co-design as a mainline benchmark axis
- firmware generation
- complex multi-agent orchestration
- large-scale distillation as a required result for submission

## 6. Higher-Level Positioning

Viewed against the broader literature, the project sits in a gap between:

- VEH device and optimization papers, which are usually single-structure and single-protocol
- benchmark papers, which prioritize task standardization, evaluator design, and fair comparison

The nearest intellectual template is not a typical VEH device paper.
It is a benchmark paper with a domain-specific evaluator.

Operational consequence:

- the benchmark object is the task, not the paper
- the evaluator must be unified before solver claims matter
- solver comparison only becomes interesting after task and verifier credibility are established

## 7. Current Repository Reality

The repo already supports a strong literature-to-record pipeline.
The implemented chain is:

`search_papers.py -> backfill_abstracts.py -> filter_01~04 -> cleanup_pdfs.py -> mineru_runner.py -> extract_schema.py`

This means the current repository is strongest at:

- focused literature retrieval
- metadata dedup and filtering
- PDF alignment and provenance tracking
- MinerU parsing on GPU
- LLM-based extraction into structured records

What is now partially implemented but not yet benchmark-complete:

- record tiering
- task generation
- verifier input adaptation
- verifier v1 evaluator
- back-substitution reporting

What is still missing for the full paper:

- finalized evaluator calibration policy
- classical optimizer baseline suite
- split-aware evaluation harness
- OOD benchmark results
- FEM and hardware validation

## 8. Current Asset Snapshot

The current experimental state is no longer speculative.
These artifacts already exist in the experimental worktree.

### 8.1 Literature Funnel

Current focused retrieval funnel:

- metadata candidates: `1908`
- stage 1 kept: `1104`
- stage 2 kept: `820`
- stage 3 kept: `301`
- stage 4 core corpus: `236`

PDF and parse coverage:

- cleaned PDFs matched to core corpus: `199`
- MinerU successful parses: `197`
- valid structured extractions: `186`
- invalid extractions: `12`

### 8.2 Record Tiers

Current exact tiers:

- `raw_parsed`: `86`
- `candidate`: `22`
- `silver`: `10`
- `gold_pre_verifier`: `68`
- `gold_curated`: `55`

Supporting audited subset:

- `power_gold_subset`: `18`

### 8.3 Task and Verifier Assets

Current benchmark artifacts:

- curated gold seeds: `55`
- verifier-ready mappings: `52`
- paper-grounded tasks: `162`
- verifier v1 requests: `156`

### 8.4 Verifier Reality Check

Current verifier v1 status:

- all `156/156` requests execute successfully
- calibrated literature back-substitution for frequency is usable
- raw power literature back-substitution is not yet trustworthy enough as a primary metric

Current top-line back-substitution numbers:

- raw frequency MAPE: `759.8%`
- calibrated frequency MAPE: `7.1%`
- raw power MAPE: `199.5%`
- power-gold subset MAPE: `98.9%`

Interpretation:

- frequency can support the v1 verifier story
- power cannot be treated as a universally calibrated mainline target yet

## 9. Benchmark Object

The basic unit of the paper is not a paper.
The basic unit is a task.

Each task is a standardized optimization problem with:

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

Papers are upstream evidence.
Tasks are the benchmark product.

## 10. Task Suite Priority

The v1 task suite is now ordered by credibility, not by ambition.

### 10.1 Primary Task A: Frequency Matching

This is the strongest and most validated task for v1.

Inputs:

- target resonance frequency
- geometry bounds
- material configuration
- load setting

Outputs:

- beam length
- beam width
- thickness-related parameters
- proof mass
- load resistance

Primary metrics:

- frequency error threshold satisfaction
- feasibility
- queries to success

### 10.2 Primary Task B: Feasibility Repair

This is the best task for demonstrating verifier-guided iterative solving.

Inputs:

- task spec
- current candidate
- latest verifier feedback

Outputs:

- next parameter update

Primary metrics:

- repair success rate
- feasibility gain per query
- invalid proposal rate

### 10.3 Secondary Task C: Constrained Power Maximization

Retain this task in v1 only as a narrower audited subset.

Use it for:

- a secondary benchmark table
- a constrained subset analysis
- a bridge toward v1.1 or appendix material

Do not use it as the main credibility axis of the verifier.

## 11. Required Schemas

Schema work remains foundational, but the runtime contract is now clearer.

### 11.1 Extraction Schema

The extraction schema should only retain fields needed for benchmark construction:

- paper metadata copied from normalized docs
- configuration
- proof mass
- geometry
- excitation
- load
- output
- field-level evidence

### 11.2 Task Schema

The task schema remains the benchmark object definition.

### 11.3 Verifier I/O Schema

The verifier schema is the solver-evaluator contract and must stay stable once baselines begin.

## 12. Data Ladder

All paper-derived data moves through a strict ladder.

### Layer 1: Raw Metadata

Source:

- OpenAlex
- Semantic Scholar

Outputs:

- `data_registry/papers.jsonl`

### Layer 2: Core Corpus and PDF Registry

Outputs:

- `papers_stage04_core_corpus.jsonl`
- cleaned PDF registry entries
- auditable local PDF paths

### Layer 3: Parsed Papers

Outputs:

- `parsed_docs/`
- `normalized_docs/`
- `provenance_docs/`

### Layer 4: Extracted Records

Outputs:

- `data_registry/extracted/`
- `data_registry/extracted_invalid/`

### Layer 5: Curated Benchmark Records

Outputs:

- `candidate_records.jsonl`
- `silver_records.jsonl`
- `gold_records.jsonl`
- `gold_records_curated.jsonl`

### Layer 6: Benchmark Tasks and Evaluator Requests

Outputs:

- paper-grounded task seeds
- paper-grounded tasks
- verifier mappings
- verifier requests

## 13. Record Acceptance Policy

### 13.1 Tiers

Use:

- `raw_parsed`
- `candidate`
- `silver`
- `gold_pre_verifier`
- `gold_curated`

### 13.2 Meaning of `gold_curated`

`gold_curated` is the real benchmark seed set.
It means:

- in-scope for linear piezo cantilever VEH
- sufficiently complete for benchmark construction
- manually audited for scope
- ready for verifier mapping

### 13.3 Meaning of `power_gold_subset`

`power_gold_subset` is not the benchmark core.
It is a narrower audited subset where:

- power
- load
- excitation frequency
- excitation amplitude

appear to be locked to the same experimental condition.

## 14. Verifier v1 Positioning

The verifier is the center of the benchmark, but it should be described carefully.

### 14.1 What Verifier v1 Is

Verifier v1 is:

- fast
- interpretable
- stable enough for benchmark use
- frequency-calibrated
- task-aware at runtime

### 14.2 What Verifier v1 Is Not

Verifier v1 is not:

- a full multiphysics simulator
- a universally accurate power predictor
- the final physics authority for all VEH structures

### 14.3 Runtime Stance

Treat the verifier outputs like this:

- frequency: primary calibrated metric
- feasibility / violations: primary benchmark signal
- displacement and stress: useful constraint signals
- power: weak reference in the general set, stronger only in the audited subset

## 15. Verifier Validation Plan

### 15.1 Main Validation Axis for v1

Primary validation:

- literature back-substitution on frequency
- feasibility consistency
- rank and trend consistency where possible

### 15.2 Secondary Validation Axis

Secondary validation:

- power behavior on the audited power subset
- limited FEM transfer
- limited hardware transfer

### 15.3 Validation Claim Discipline

Do not overclaim raw physics fidelity.
Use this hierarchy in the paper:

1. calibrated frequency credibility
2. benchmark-useful feasibility behavior
3. narrower audited power analysis

## 16. Solver Roadmap

The solver roadmap is now explicitly staged.

### 16.1 Stage 1: Classical Baselines First

Build and compare:

- Random Search
- Genetic Algorithm
- CMA-ES
- Bayesian Optimization

This should happen before complex agent work.

### 16.2 Stage 2: Simple Language Baselines

Then add:

- zero-shot LLM
- RAG LLM

These are comparison points, not the paper center.

### 16.3 Stage 3: Verifier-Guided Agent

Only after the evaluator and classical baselines are stable should the verifier-guided agent become a main experiment.

### 16.4 Stage 4: Distillation

Distillation remains optional for v1 and should not block the main paper.

## 17. Research Questions

All experiments must now serve these tighter questions.

### RQ1: Is the benchmark credible?

Check:

- funnel transparency
- record tier construction
- task distributions
- split design

### RQ2: Is the verifier credible enough for benchmark use?

Check:

- calibrated frequency back-substitution
- feasibility behavior
- limited FEM or hardware agreement

### RQ3: How do classical optimizers compare under a unified budget?

Check:

- success rate
- queries to success
- feasibility
- wall-clock

### RQ4: What additional value does structured verifier feedback bring?

Compare:

- zero-shot LLM
- simple reward or scalar feedback
- structured verifier-guided repair

### RQ5: How robust are solvers under OOD?

Check:

- success-rate drop
- invalid proposal increase
- repair degradation

## 18. Required Experiments

### Experiment 1: Benchmark Funnel and Distribution

Show:

- retrieval funnel
- parse coverage
- extraction validity
- candidate / silver / gold counts
- curated gold count
- task counts and distributions

### Experiment 2: Verifier Validation

Main table:

- calibrated frequency metrics
- feasibility consistency
- subset power metrics

Supporting table:

- limited FEM and hardware transfer if available

### Experiment 3: Classical Baseline Results

Run on the primary benchmark using:

- success rate
- best feasible objective
- queries to success
- invalid proposal rate
- wall-clock

### Experiment 4: OOD Generalization

Compare:

- ID vs OOD performance drop
- failure mode changes

### Experiment 5: Structured Feedback Ablation

Compare:

- no verifier
- scalar feedback
- structured verifier feedback

### Experiment 6: Secondary Power-Subset Study

Run only on the audited subset.
Do not present it as the benchmark center.

### Experiment 7: Optional Distillation

Only after the baseline and agent story is already complete.

## 19. Figures and Tables

### Figures

- overall system diagram
- source-to-record funnel
- record-to-task funnel
- verifier architecture
- benchmark distributions
- classical baseline comparison
- repair trajectory case study

### Tables

- benchmark summary
- verifier validation
- classical baseline results
- OOD results
- structured feedback ablation
- reproducibility and artifact table

## 20. Implementation Phases

### Phase 1: Lock the Benchmark Core

Goal:

- freeze schemas
- stabilize record tiers
- finalize the curated gold seed set

Exit criteria:

- extraction schema stable
- curated gold set stable
- power audited subset frozen

### Phase 2: Finalize Verifier v1 for Benchmark Use

Goal:

- freeze evaluator API
- keep calibrated frequency as the primary validated output
- document power as subset-only

Exit criteria:

- all verifier requests execute
- calibrated frequency back-substitution is reproducible
- runtime metric policy is frozen

### Phase 3: Freeze Task Sets and Splits

Goal:

- turn seeds into benchmark tasks
- finalize train/val/test-id/test-ood splits
- verify leakage controls

Exit criteria:

- task schema frozen
- split files frozen
- leakage checks pass

### Phase 4: Run Classical Baselines

Goal:

- establish a strong non-LLM reference suite

Exit criteria:

- Random / GA / CMA-ES / BO all run under one protocol

### Phase 5: Add Language Baselines and Agent

Goal:

- measure what language methods add beyond the classical suite

Exit criteria:

- zero-shot and RAG baselines run
- structured verifier-guided repair loop runs

### Phase 6: Optional Distillation and External Validation

Goal:

- add extra depth without blocking the main paper

Exit criteria:

- optional only

## 21. Acceptance Gates

### Gate A: Benchmark Core Ready

- curated gold stable
- audited subset stable
- task seeds stable

### Gate B: Evaluator Ready

- verifier API frozen
- calibrated frequency metrics reproducible
- power policy explicitly limited to subset analysis

### Gate C: Benchmark Ready

- task sets frozen
- splits frozen
- evaluation protocol frozen

### Gate D: Main Results Ready

- classical baselines complete
- at least one language baseline complete
- structured-feedback ablation executable

## 22. Minimum Publishable Version

The minimum credible v1 is now:

- linear piezo cantilever only
- frequency-first benchmark
- feasibility repair as a primary task
- audited power subset as a secondary study
- `55` curated gold records or a modestly expanded nearby number
- paper-grounded task set plus limited synthetic expansion
- calibrated frequency verifier
- 4 classical optimizer baselines
- 2 to 3 language baselines
- complete artifact and reproducibility package

This is enough for a credible benchmark paper if executed cleanly.

## 23. Immediate Execution Queue

Do these next, in order.

### Immediate Block 1: Freeze the v1 Positioning

1. treat frequency and feasibility as the primary benchmark axes
2. treat power as subset-only in the main plan and paper outline
3. freeze the benchmark claims accordingly

### Immediate Block 2: Freeze Verifier Runtime Policy

1. keep calibrated frequency enabled
2. keep general power calibration disabled
3. document subset-only power evaluation
4. finalize violation labels and feasibility logic

### Immediate Block 3: Freeze Tasks and Splits

1. finalize the `55` paper-grounded seeds
2. freeze the `156` ready verifier requests
3. finalize train / val / test-id / test-ood
4. run leakage and family-overlap checks

### Immediate Block 4: Build the Classical Baseline Harness

1. define solver API
2. implement Random Search
3. implement GA
4. implement CMA-ES
5. implement BO
6. add unified logging and aggregation

### Immediate Block 5: Add the First Language Comparison

1. run zero-shot LLM on the frequency task
2. run one verifier-guided repair loop
3. prepare the structured-feedback ablation

## 24. Repo Mapping

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
- `vehbench/verifier/v1/`
- `scripts/build_paper_grounded_task_seeds.py`
- `scripts/build_verifier_v1_inputs.py`
- `scripts/generate_benchmark_tasks.py`
- `scripts/run_verifier_v1_backsub.py`

### New Areas to Prioritize Next

- `vehbench/solvers/`
- `vehbench/eval/`
- baseline run configs
- split validation utilities
- classical optimizer result reports

## 25. Source-of-Truth Priority

When documents conflict, use this order:

1. this file
2. `docs/PROJECT_HANDOFF.md`
3. actual code and benchmark artifacts
4. older roadmap or aspirational README content

The older roadmap files remain useful context, but this file is the operative benchmark build plan.
