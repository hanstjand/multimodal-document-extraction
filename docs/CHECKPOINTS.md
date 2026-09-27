# Checkpoints

Legend: `[ ]` Not started · `[~]` In progress · `[x]` Completed · `[!]` Blocked

Rules: one checkpoint at a time; never auto-advance; after completion update this file and
`RESEARCH_LOG.md`, summarize, STOP, and wait for explicit user approval.

**Current checkpoint:** none in progress — CP-0.3 completed 2026-09-27 (Phase 0 complete); awaiting approval for CP-1.1.

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

### [ ] CP-1.1 Core data models
Acceptance: typed models for document, page, question (with gold evidence pages),
retrieved item, retrieval result; unit tests pass.

### [ ] CP-1.2 Perfect Recall metric
Acceptance: implementation matches paper definition (P ⊆ P̂); edge cases decided in
`DECISIONS.md`; unit tests pass.

### [ ] CP-1.3 Irrelevant Pages Ratio metric
Acceptance: implementation matches paper definition (|P̂ \ P| / |P̂|); empty-retrieval
edge case decided in `DECISIONS.md`; unit tests pass.

---

## Phase 2 — Original Benchmark Preparation

### [ ] CP-2.1 Inspect MMLongBench-Doc
Acceptance: source, license, version/commit, file format, field meanings, evidence-page
indexing (0- vs 1-based), unanswerable-question handling documented.

### [ ] CP-2.2 Dataset loader
Acceptance: loader maps raw data to CP-1.1 models; counts match documented statistics
(or discrepancies are recorded); tests pass.

### [ ] CP-2.3 Pilot subset
Acceptance: fixed, versioned pilot subset (doc IDs + question IDs) with selection
procedure and seed recorded.

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
