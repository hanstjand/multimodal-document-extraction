# Research Plan — Multimodal Document Extraction

Detailed per-checkpoint status and acceptance criteria live in `docs/CHECKPOINTS.md`.
This file describes intent and the reasoning behind the phase order.

| Phase | Name | Study |
|---|---|---|
| 0 | Research infrastructure | — |
| 1 | Evaluation foundation | shared |
| 2 | Original benchmark preparation | shared (used by Study 01) |
| 3 | Conventional retrieval baselines | shared (used by Study 01, 02) |
| 4 | LAD-RAG reproduction | **Study 01** |
| 5 | Technical-domain evaluation | **Study 02** |
| 6 | Failure analysis and research-gap discovery | — |
| 7 | Future proposed method | not yet defined |

## Phase 0 — Research infrastructure
Inspect the environment, create the repository structure, set up the Python package.
Output: a reproducible, documented starting point for the whole Master's research.

## Phase 1 — Evaluation foundation
Implement the core data models (documents, pages, questions, retrieval results) and the
retrieval metrics **before** any retriever, so every method is evaluated by the same tested code.
The first metrics are those used by LAD-RAG:
- **Perfect Recall (PR)** — 1 if gold evidence pages ⊆ retrieved pages, else 0.
- **Irrelevant Pages Ratio (IPR)** — |retrieved \ gold| / |retrieved|.
Edge cases (empty gold set for unanswerable questions, empty retrieval) must be decided
explicitly and recorded in `DECISIONS.md`. This code is method-agnostic
(`src/multimodal_document_extraction/evaluation/`).

## Phase 2 — Original benchmark preparation
Inspect MMLongBench-Doc (format, license, evidence-page annotation, unanswerable questions),
write a loader, and define a small, fixed **pilot subset** for cheap iteration.

## Phase 3 — Conventional retrieval baselines
BM25 and dense retrieval, evaluated with PR/IPR across k. The LAD-RAG paper's baselines
operate over *element summaries* produced by LAD-RAG ingestion; simpler page-text baselines
come first and are clearly labelled as such. Baselines are shared code, reused in Study 02.

## Phase 4 — Study 01: LAD-RAG reproduction
Review the paper for implementable details (and gaps), define the document graph schema,
build ingestion (LVLM element extraction + running memory + edges), symbolic queries,
neural + symbolic retrieval, and the dynamic retrieval agent.
Method-specific code in `src/multimodal_document_extraction/studies/ladrag/`; notes in
`docs/studies/ladrag/`; experiments in `experiments/ladrag/`.

## Phase 5 — Study 02: Technical-domain evaluation
Assemble a technical document / datasheet set with ground-truth evidence pages,
run the unchanged pipeline(s), and quantify the drop relative to `[REPRO]`.
Experiments in `experiments/technical/`.

## Phase 6 — Failure analysis and research-gap discovery
Categorize observed failures, identify concrete research problems, and run a targeted
literature search for methods addressing them. Candidate improvements may include
combinations or modifications of existing methods.

## Phase 7 — Future proposed method
Intentionally **not defined yet**. Its contents are written only after Phase 6, based on
experimental evidence, and recorded in `DECISIONS.md`.

## Risks (initial)
- **Cost:** LAD-RAG uses GPT-4o for per-page ingestion and for the agent. A full
  MMLongBench-Doc ingestion (~135 docs × ~47.5 pages) is expensive; pilot subsets first.
- **Unreleased code:** the official LAD-RAG implementation is not public (paper, App. A).
  Several details are unspecified (see `docs/studies/ladrag/PAPER_NOTES.md` → "Open questions").
- **Local hardware:** 8 GB VRAM (see `docs/ENVIRONMENT.md`); large open LVLMs may not fit locally.
