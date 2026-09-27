# Checkpoints

Legend: `[ ]` Not started · `[~]` In progress · `[x]` Completed · `[!]` Blocked

Rules: one checkpoint at a time; never auto-advance; after completion update this file and
`RESEARCH_LOG.md`, summarize, STOP, and wait for explicit user approval.

**Current checkpoint:** none in progress — CP-2.3 completed 2026-09-27 (Phase 2 complete); awaiting approval for CP-3.1.

---

## Phase 0 — Research Infrastructure

### [x] CP-0.1 Environment Inspection — completed 2026-09-27
- [x] Detect OS — Windows 10 Pro 10.0.19045, 64-bit
- [x] Detect Python version — 3.13.12 (conda base); 3.8 also present
- [x] Detect Git version — 2.53.0.windows.2
- [x] Check NVIDIA GPU availability — Quadro RTX 4000 present
- [x] Run `nvidia-smi` if available — driver 595.97, CUDA (driver) 13.2
- [x] Record CPU / RAM / GPU / VRAM when possible — i7-10700 8C/16T, 31.8 GB RAM, 8 GB VRAM
- [x] Do NOT modify system software — nothing installed or changed

Acceptance: all items above recorded in `docs/ENVIRONMENT.md` and `RESEARCH_LOG.md`;
nothing installed or changed on the system. ✔

### [x] CP-0.2 Repository Structure — completed 2026-09-27
- [x] Initialize local Git if needed — `git init -b main` (no global config changed)
- [x] Create project structure — all 33 planned paths verified present; added `.gitattributes`, `papers/README.md`
- [x] Create `.gitignore` — verified with `git check-ignore` (secrets, data, runs, weights, paper PDFs, local Claude settings ignored; `.gitkeep`, `.env.example`, `experiments/results/` not ignored)
- [x] Create documentation scaffold — docs verified; paper notes updated to ACL camera-ready

Acceptance: `git status` works; directory tree matches the planned layout;
`.gitignore` excludes secrets, data, and run artifacts; initial commit only after user approval. ✔
(Initial commit **not yet made** — pending user approval; see RESEARCH_LOG.)
Note: the scaffold files were drafted during project bootstrap (before CP-0.1, at user request);
CP-0.2 verifies and finalizes them and initializes Git.

### [x] CP-0.2A Repository Scope Realignment — completed 2026-09-27
- [x] Realign repository from "LAD-RAG reproduction" to "Multimodal Document Extraction" research repository, with LAD-RAG as Study 01
- [x] Rename package `src/ladrag_reproduction/` → `src/multimodal_document_extraction/`; add `agents/`, `studies/ladrag/`
- [x] Move study-specific material (paper PDF, paper notes, experiments) under `ladrag/` study locations; add `experiments/technical/`
- [x] Update PROJECT_CONTEXT, RESEARCH_PLAN (Phases 0–7), CHECKPOINTS, README, CLAUDE.md, pyproject, `.gitignore`, EXPERIMENT_PROTOCOL, study READMEs
- [x] Record decision in DECISIONS.md (D-005); append RESEARCH_LOG entry
- [x] No LAD-RAG code, no installs, no environments, no downloads, no experiments

Acceptance: target structure present; no remaining stale references to the old package name or
old paths outside historical log/decision entries; ignore rules re-verified; CP-0.2 history untouched. ✔

### [x] CP-0.3 Python Project Setup — completed 2026-09-27
- [x] Create / finalize `pyproject.toml` — `requires-python >=3.11`, `dev` extra, ruff config; plus `environment.yml`
- [x] Define minimal dependencies — no runtime deps yet; dev: pytest, ruff (D-006)
- [x] Prepare Python package — editable install of `multimodal-document-extraction 0.0.1` in conda env `mmde`
- [x] Verify imports — package + 9 subpackages import from outside the repo; `tests/test_imports.py` 10/10 passed

Acceptance: isolated environment created (decision recorded); `pip install -e .` succeeds;
`import multimodal_document_extraction` works; `pytest` runs (even with zero tests). ✔

---

## Phase 1 — Evaluation Foundation

### [x] CP-1.1 Core data models — completed 2026-09-27
- [x] Decide model technology and page-numbering convention — D-007 (frozen dataclasses, 1-based pages)
- [x] `Document`, `Page`, `Question` (gold evidence pages), `RetrievedItem`, `RetrievalResult` — `src/multimodal_document_extraction/data_models.py`
- [x] Validation of invariants (page numbers, ranks, doc consistency, duplicates, finite scores)
- [x] Lossless dict/JSON round-trip (for JSONL results per EXPERIMENT_PROTOCOL)
- [x] Unit tests — `tests/test_data_models.py`; full suite 47 passed; ruff clean

Acceptance: typed models for document, page, question (with gold evidence pages),
retrieved item, retrieval result; unit tests pass. No metrics, loaders, or retrievers in this CP. ✔

### [x] CP-1.2 Perfect Recall metric — completed 2026-09-27
- [x] PR = 1 if P ⊆ P̂ else 0 — `evaluation/retrieval_metrics.py` (`perfect_recall`, `perfect_recall_for`)
- [x] Edge cases decided — D-008: empty gold → undefined, excluded from mean and counted; empty retrieval → 0
- [x] Aggregation — `mean_perfect_recall` → `MetricSummary(mean, num_scored, num_excluded)`; duplicate questions rejected
- [x] Unit tests — `tests/test_perfect_recall.py` (21 tests); full suite 68 passed; ruff clean

Acceptance: implementation matches paper definition (P ⊆ P̂); edge cases decided in
`DECISIONS.md`; unit tests pass. ✔

### [x] CP-1.3 Irrelevant Pages Ratio metric — completed 2026-09-27
- [x] IPR = |P̂ \ P| / |P̂| — `irrelevant_pages_ratio`, `irrelevant_pages_ratio_for` (page-level, elements mapped to pages)
- [x] Edge cases decided by user — D-009 (three cases; empty retrieval → 0.0; no-evidence: 0.0 / 1.0)
- [x] NoEvidenceCorrect metric for the no-evidence subset — `no_evidence_correct[_for]`
- [x] Subset-separated reporting — `evaluate_retrieval` → `RetrievalEvaluation` (evidence subset = paper-compatible PR/IPR; no-evidence subset = IPR + NoEvidenceCorrect)
- [x] EXPERIMENT_PROTOCOL updated (fields + edge-case table)
- [x] Unit tests — `tests/test_irrelevant_pages_ratio.py` (17 tests); full suite 85 passed; ruff clean

Acceptance: implementation matches paper definition (|P̂ \ P| / |P̂|); empty-retrieval
edge case decided in `DECISIONS.md`; unit tests pass. ✔

---

## Phase 2 — Original Benchmark Preparation

### [x] CP-2.1 Inspect MMLongBench-Doc — completed 2026-09-27
- [x] Source, license, version/commit — GitHub @ `d73f0dc0`, HF @ `2ff6aa92`, Apache-2.0 (D-010)
- [x] Reproducible download with checksums — `scripts/download_mmlongbench_doc.py`, `MANIFEST.json`
- [x] File format and field meanings — `docs/studies/ladrag/MMLONGBENCH_DOC.md` §2
- [x] Evidence-page indexing — 1-based physical pages (empirical 46/55 vs 0/55; bounds)
- [x] Unanswerable-question handling — 223 "Not answerable"; 228 empty evidence; the sets differ (7 + 12)
- [x] Statistics vs. paper — 1,082 q / 135 docs / 33% multi-page match; mean pages 48.36 vs 47.5
- [x] Data-quality issues — wrong `dr-vorapp` PDF (10 q), 9 invalid evidence pages, 28 PDFs without text layer, HF vs GitHub differences
- [x] Inspection script — `scripts/inspect_mmlongbench_doc.py` → `data/processed/mmlongbench-doc/inspection.json`

Acceptance: source, license, version/commit, file format, field meanings, evidence-page
indexing (0- vs 1-based), unanswerable-question handling documented. ✔

### [x] CP-2.2 Dataset loader — completed 2026-09-27
- [x] Policies chosen by user — D-012 (index+hash IDs; load, flag, exclude from clean set)
- [x] Loader → `Document` / `Question` / `Page` — `datasets/mmlongbench_doc.py` (`load_mmlongbench_doc`, `load_pages`)
- [x] Checksum verification against MANIFEST (samples always, PDFs optional)
- [x] Counts match CP-2.1: 1,082 q, 135 docs, 6,529 pages; 19 flagged (9 invalid pages + 10 wrong document); clean 1,063
- [x] Tests — `tests/test_mmlongbench_doc.py` (9 synthetic + 4 real-data); full suite 98 passed; ruff clean

Acceptance: loader maps raw data to CP-1.1 models; counts match documented statistics
(or discrepancies are recorded); tests pass. ✔

### [x] CP-2.3 Pilot subset — completed 2026-09-27
- [x] Generic versioned `Subset` + seeded stratified selection — `datasets/subsets.py`
- [x] Script — `scripts/make_mmlongbench_pilot.py` (refuses to overwrite versions)
- [x] `pilot-v1`: 10 docs / 7 types / 241 pages / 80 questions (35% multi-page, 14 no-evidence, 1 image-only), seed 0, attempt 2
- [x] `calib-v1`: 2 docs / 33 pages / 16 questions
- [x] Decision D-013; reproducibility test re-derives the same documents; full suite 106 passed; ruff clean
Acceptance: fixed, versioned pilot subset (doc IDs + question IDs) with selection
procedure and seed recorded; follows `docs/studies/ladrag/REPRODUCTION_PROTOCOL.md` §5
(`pilot-v1`: 10 stratified docs ≤ 40 pages; `calib-v1`: 2 of them). ✔

---

## Phase 3 — Conventional Retrieval Baselines

### [ ] CP-3.1 BM25 baseline
### [ ] CP-3.2 BM25 evaluation
### [ ] CP-3.3 Dense retrieval
### [ ] CP-3.4 Dense retrieval evaluation

Acceptance (evaluation CPs): results written per `EXPERIMENT_PROTOCOL.md`, PR/IPR vs. k,
labelled `[REPRO]`, compared to `[PAPER]` only where the setting is comparable.

---

## Phase 4 — Study 01: LAD-RAG Reproduction

### [x] CP-4.0 Reproduction Resource Strategy — completed 2026-09-27
(Added 2026-09-27 at user request; executed before CP-2.2 because it constrains the pilot subset and model choices.)
- [x] Document original LAD-RAG compute requirements — protocol §1 (incl. planning cost estimate)
- [x] Document unavailable resources — §2
- [x] Define exact reproduction vs substituted components — §3 (C1–C16; system named LAD-RAG†)
- [x] Select lightweight ingestion alternatives — §4 (primary gpt-4o-mini; GPT-4o calibration; fallbacks)
- [x] Define pilot document count — §5 (10 docs ≤ 40 pages, stratified; 2-doc calibration set; budget + stop rule)
- [x] Define how substituted results will be reported — §6 (`reproduction_level`, component spec)
- [x] Ensure paper-reported and reproduced results remain separate — §7
- [x] Decision D-011; EXPERIMENT_PROTOCOL fields added

Deliverable: `docs/studies/ladrag/REPRODUCTION_PROTOCOL.md` ✔

### [ ] CP-4.1 Paper implementation review
### [ ] CP-4.2 Document graph schema
### [ ] CP-4.3 Graph construction
### [ ] CP-4.4 Symbolic retrieval
### [ ] CP-4.5 Neural + symbolic retrieval
### [ ] CP-4.6 Dynamic retrieval agent

---

## Phase 5 — Study 02: Technical-Domain Evaluation

### [ ] CP-5.1 Technical dataset
### [ ] CP-5.2 Technical ground truth
### [ ] CP-5.3 Evaluate existing pipeline
### [ ] CP-5.4 Measure performance drop
### [ ] CP-5.5 Failure analysis

---

## Phase 6 — Failure Analysis and Research-Gap Discovery

### [ ] CP-6.1 Categorize observed failures
### [ ] CP-6.2 Targeted literature search
### [ ] CP-6.3 Candidate improvement
### [ ] CP-6.4 Experiment design
### [ ] CP-6.5 Proposed method evaluation

(CP IDs kept unchanged in CP-0.2A to avoid renumbering the roadmap. CP-6.3–6.5 are generic
placeholders; any of them may move to Phase 7 when Phase 7 is defined.)

---

## Phase 7 — Future Proposed Method

Intentionally not defined. Checkpoints are written only after Phase 6, based on experimental
evidence, and recorded in `DECISIONS.md`.

Detailed acceptance criteria for Phases 3–7 are written when each phase begins.
