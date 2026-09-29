# Checkpoints

Legend: `[ ]` Not started · `[~]` In progress · `[x]` Completed · `[!]` Blocked

Rules: one checkpoint at a time; never auto-advance; after completion update this file and
`RESEARCH_LOG.md`, summarize, STOP, and wait for explicit user approval.

**Current checkpoint:** none in progress — CP-4.4 completed 2026-09-29; awaiting approval. CP-4.3D Stage 1 approved (Stage 2 not started); CP-4.5, CP-4.5A not started.

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

### [x] CP-3.1 BM25 baseline — completed 2026-09-27
- [x] Text source decided — D-014 (`bm25-pagetext`: PyMuPDF page text; paper-style `bm25-elements` after Phase 4)
- [x] `retrieval/bm25.py` — per-document bm25s index, full deterministic page ranking, empty-document handling, latency + config in metadata
- [x] Dependency `bm25s>=0.2` (0.3.11 installed)
- [x] Tests — `tests/test_bm25.py` (7 unit + 1 pilot smoke test, no metrics); full suite 114 passed; ruff clean
### [x] CP-3.2 BM25 evaluation — completed 2026-09-27
- [x] Run recording per protocol — `utils/run_recording.py`, `scripts/run_retrieval_eval.py`, D-015 (JSON configs)
- [x] k-sweep + first-PR-k metrics — `evaluate_retrieval_at_k`, `first_perfect_recall_k`
- [x] EXP-0001 `bm25-pagetext` on pilot-v1 (80 q, k = 1..37) → `experiments/ladrag/results/results.csv` (37 rows, `[REPRO]`, `substituted`)
- [x] Evidence / no-evidence subsets reported separately; single- vs multi-page and text vs image-only breakdowns
- [x] Tests — `tests/test_run_recording.py` (6); full suite 120 passed; ruff clean
### [x] CP-3.3 Dense retrieval — completed 2026-09-27
- [x] User choices — MaxP chunking, GPU install (D-016)
- [x] Installed torch 2.14.0+cu126 + sentence-transformers 6.1.0 (extra `dense`); models pinned and cached
- [x] `retrieval/dense.py` — E5-large-v2 / BGE-large-en specs (prefixes from model cards), offset-based token windows, MaxP, unscored empty pages last
- [x] Tests — `tests/test_dense.py` (8 with fake encoder + 1 real E5 smoke); full suite 129 passed; ruff clean
- [x] GPU feasibility on pilot (no metrics): 241 pages → 244 chunks, ~12 s indexing per model, ~18 ms/query, peak VRAM 1.64 GiB
### [x] CP-3.4 Dense retrieval evaluation — completed 2026-09-27
- [x] Runner supports `dense-pagetext` (E5 / BGE); EXP-0002 (E5) and EXP-0003 (BGE) on pilot-v1, same protocol as EXP-0001 → results.csv (112 rows total)
- [x] Paired comparison script + CMP-0001 (bootstrap CIs, W/T/L, subgroups) — D-017
- [x] Result: no clear difference between BM25, E5, BGE on pilot-v1 (all 95% CIs include 0)
- [x] Failure observation: 16/66 evidence questions have a gold page without text layer → PR@5 = 0 for all three text baselines

Acceptance (evaluation CPs): results written per `EXPERIMENT_PROTOCOL.md`, PR/IPR vs. k,
labelled `[REPRO]`, compared to `[PAPER]` only where the setting is comparable. ✔ (page-text
baselines are not comparable to the paper's element-summary baselines; no [PAPER] comparison made)

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

### [x] CP-4.1 Paper implementation review — completed 2026-09-27
- [x] Figures inspected visually (Figs. 2, 3, 5, 6, 7) — new details in PAPER_NOTES §16 (node ID format, filter code, LAD-RAG operating point ≈ PR 0.83 / IPR 0.79 on MMLongBench)
- [x] Prompts Figs. 9–12 transcribed word-exact with a self-checking script — `studies/ladrag/prompts/` + `scripts/transcribe_ladrag_prompts.py`
- [x] Implementation spec — `docs/studies/ladrag/IMPLEMENTATION_SPEC.md` (pipeline, reconstructions R1–R20, resolution of all 12 open questions, Phase 4 CP plan)
- [x] D-018 recorded as **Proposed** — requires user approval before CP-4.2

### [x] CP-4.1A Resource-Constrained Phase 4 Revision — completed 2026-09-27
(Added 2026-09-27 at user request; documentation/planning only — no code, installs, downloads or API calls.)
- [x] "Local-first, API-last" principle in REPRODUCTION_PROTOCOL.md (§0) and IMPLEMENTATION_SPEC.md (§0)
- [x] Labels [PAPER-EXACT] / [RECONSTRUCTED] / [SUBSTITUTED] / [OPTIONAL-REFERENCE] applied throughout the spec and protocol
- [x] $0-API-completable Phase 4 plan (CP-4.2, 4.3A–D, 4.4, 4.5, 4.6A–C, optional 4.7) replacing the former CP-4.3–4.6 plan
- [x] Config-driven reconstruction parameters (IMPLEMENTATION_SPEC §6)
- [x] API spending policy — 10 hard rules (REPRODUCTION_PROTOCOL §5)
- [x] D-018 revised in place, status **Proposed** (earlier "Accepted" withdrawn); D-019 (resource strategy) recorded as **Proposed**; D-011 marked pending supersession
- [x] RESEARCH_LOG entry appended; CP-4.2 put on hold pending user decision
- [x] **Finalized 2026-09-27:** user approved the revised plan; D-018 and D-019 → **Accepted**; D-019 supersedes only the model/resource/budget parts of D-011 (methodological parts retained); user decided to keep the CP-4.2 implementation, subject to review against the final spec

### [x] CP-4.2 Document graph schema — completed 2026-09-27 (after review against accepted D-018/D-019)
**Review (after CP-4.1A approval):** user decided to keep the implementation. Reviewed against the final
spec; fixed: unknown extracted keys were dropped (now preserved in `extra_fields`, model ID in
`claimed_object_id`); `from_dict` did not validate edges (unknown endpoints silently created nodes) or
duplicates → strict validation + `validate()`; JSON not byte-deterministic → `to_json` with sorted keys;
no graph metadata → `GraphMetadata`; no working-memory validation → `validate_memory`; hard-coded
section types → `DEFAULT_SECTION_TYPES` (config default, R3); `order_on_page` unvalidated. Paper-exact vs.
reconstructed node fields labelled. No ingestion logic, model inference or API calls.
Tests: CP-4.2 tests 39 (23 → 39); full suite 168 passed; ruff clean.

Original record (kept):
**Hold note (CP-4.1A):** implemented after the user's message "lanjut 4.2 …", which was recorded as
approval of D-018. The user has since stated that D-018 was not accepted and that Phase 4 must be
revised first (CP-4.1A); D-018 is back to *Proposed*. The work below exists in the working tree
(uncommitted, tests passing) and matches the revised CP-4.2 scope, but the checkpoint is not
considered accepted until the user decides (keep as is / revise / redo). Original record kept below.
- [x] D-018 approved by user without changes *(recorded at the time; withdrawn in CP-4.1A)*
- [x] `studies/ladrag/schema.py` — node IDs `page_{n}-obj_{k:03d}` (R1) + deterministic reassignment, Fig. 9 field normalization, `DocumentGraph` (validated nodes, merged typed undirected edges with rejection reasons (R7), communities (R8), deterministic node-link JSON, stats), initial memory (R6)
- [x] `studies/ladrag/prompts/__init__.py` — renderers for Figs. 9–12 reproducing the paper's `.format` / f-string semantics without altering inserted values; template checksums pinned in tests
- [x] Dependency `networkx>=3.2` made explicit (3.6.1, BSD); prompt files declared as package data
- [x] Tests — `tests/test_ladrag_schema.py`, `tests/test_ladrag_prompts.py` (23); full suite 152 passed; ruff clean; no API calls
Revised plan (CP-4.1A, D-019): every checkpoint below must be completable with **$0 API spend**;
paid API use is optional validation, never an acceptance criterion. Replaces the former
CP-4.3 Graph construction, CP-4.5 Neural + symbolic retrieval and CP-4.6 Dynamic retrieval agent
(none had started). Details: `docs/studies/ladrag/IMPLEMENTATION_SPEC.md` §9.

### [x] CP-4.3A Ingestion framework — completed 2026-09-27
Mock/scripted VisionModel; PDF → page images → nodes → memory → intra-page edges → cross-page edges →
persisted graph; invalid JSON, retry, cache, persistence, page-level resume. No real VLM, no API.
Acceptance: a small synthetic PDF runs end-to-end PDF → graph with deterministic mock responses. ✔
- [x] `studies/ladrag/models.py` — vendor-neutral `VisionModel` protocol, `ScriptedVisionModel`, `MockVisionModel` (schema-valid replies from the rendered Figs. 9–11)
- [x] `utils/model_cache.py` — permanent content-addressed cache (atomic writes)
- [x] `studies/ladrag/ingestion.py` — 1-based PyMuPDF rendering, steps A–D, JSON parsing + repair, ID normalization, relation validation, memory handling, Louvain, graph + summary, page records, fingerprinted resume
- [x] Tests — `tests/test_ladrag_ingestion.py` (20): synthetic 3-page PDF end-to-end; JSON repair / unrepairable; bad IDs; rejected relations; memory/section-queue rejection; cache (2nd run: 0 model calls, identical graph); crash on page 3 → resume calls page 3 only, graph identical to an uninterrupted run; fingerprint mismatch / restart; full suite 188 passed; ruff clean

### [x] CP-4.3B Local VLM feasibility — completed 2026-09-28 (verdict approved by user; D-020 Accepted)
- [x] Ecosystem check + survey documented before download (`docs/studies/ladrag/LOCAL_VLM_FEASIBILITY.md`)
- [x] User-approved downloads (Qwen3.5-2B, Qwen3-VL-2B-Instruct, pinned) and deps (Pillow, torchvision)
- [x] `studies/ladrag/local_vlm.py` (transformers VisionModel, fp16, greedy, thinking off) + `scripts/ladrag_vlm_feasibility.py`
- [x] 5 representative pages × 2 models through the full A–D pipeline; $0 API cost
- [x] Framework fixes found by the run: R17b, R17c, R21 (tests added; record version 3)
- [x] Verdict: **Qwen3.5-2B feasible with limitations** (5/5 pages, JSON ≤ 1 repair, 4.7 GiB, ≈ 4 min/page; misses figures on a dense academic page); **Qwen3-VL-2B not feasible** (runaway repetition, 2/5 pages empty, 7.75 GiB reserved)
- [x] Full suite 199 passed; ruff clean
Survey current small VLMs (≈ 2B–4B class, quantized if useful) that fit 8 GB VRAM; document
model/checkpoint/version/license/quantization/runtime before download; test 3–5 representative pages
(text-heavy, table, figure/chart, layout-heavy, cross-page if possible); measure load, VRAM, latency,
JSON validity, node counts/types, coverage, manual quality. No pilot run, no API.
Acceptance: an honest feasibility verdict (including "not feasible" with a cheaper alternative).

### [x] CP-4.3C Local ingestion calibration — completed 2026-09-28 (CP-4.3B approved 2026-09-28)
- [x] 27 contiguous pages from 5 pilot documents, full pipeline at 1280 px (CAL-0001): 27/27 pages with nodes, 0 unrecoverable JSON, runaway 8.3 % of first attempts, est. no-cache model time 312 s/page (281 s/page actually spent), peak 5.62 / 7.62 GiB
- [x] Page-level checkpoint/resume proven with the real model (killed after page 3 → resumed at page 4, pages 1–3 untouched)
- [x] Determinism verified (2/2 identical re-runs without cache)
- [x] Memory growth, cross-page relations (44 accepted, 6 rejected), latency, VRAM, total time recorded
- [x] 1280 vs 1600 px on 7 figure-rich pages (CAL-0002): more figures/coverage at 1600 px, +21 % time
- [x] `DocumentIngestor.extract_nodes`, `scripts/ladrag_ingestion_calibration.py` (+ `--mock` dry run); report `docs/studies/ladrag/INGESTION_CALIBRATION.md`; $0 API
- [x] Analysis-only completion: AI-assisted qualitative diagnostic audit of 19 of 44 cross-page relations (failure-analysis evidence only; not ground truth / edge accuracy / benchmark metric, D-021) (1 correct, 5 plausible, 13 incorrect, 0 hallucinated — sample only; `scripts/ladrag_relation_audit_sample.py`); timing fields renamed (estimated no-cache vs. this-run model time vs. wall time), no re-run
≈ 20–30 representative pages with the selected local model: stability, JSON failure rate, memory
growth, cross-page edges, latency, VRAM, total time, consistency; page-level checkpoint/resume proven.

### [~] CP-4.3D Staged pilot graph construction (revised 2026-09-28; D-021 Accepted; Stage 1 approved 2026-09-29, Stage 2 not started)
Evaluation strategy changed after CP-4.3C: generated graphs are evaluated downstream against the
official `evidence_pages` (design: `docs/studies/ladrag/RETRIEVAL_EVAL_V1.md`).
- [x] Stage-1 design (analysis only, no inference): subset retrieval-eval-v1 = 43 pilot-v1 questions of the five CAL-0001 documents (132 pages; 35 evidence, 18 multi-page); stats `experiments/ladrag/results/design/retrieval-eval-v1-stage1-stats.json`; conditions A/B/C/D, budget control, reachability diagnostic fixed before results
- [x] User approval of D-021 and Stage-1 settings (2026-09-28): 1280 px, 8192 tokens, runaways measured only, R22 OOM policy; retrieval-eval-v1 protocol frozen before results
- [x] Stage 1 (ING-0001, 2026-09-28 18:37 → 09-29 04:12, 9.57 h, $0): 132/132 pages, 0 resource failures, 129 pages with nodes (3 without, JSON failure, none gold), 846 nodes, 1,593 edges, 714 cross-page edges, 206 rejected relations, runaways 6.5 % of first attempts, 49/362 calls from cache, peak 5.82 / 8.06 GiB; all 35 evidence questions have every gold page represented by ≥ 1 node; R22 OOM policy and R23 resume fix (tests); report `docs/studies/ladrag/PILOT_INGESTION.md`
- [ ] Stage 2 (remaining five pilot-v1 documents, 109 pages) only after Stage-1 evaluation and approval
Original scope (kept): ingest pilot-v1 (10 docs, 241 pages) locally; completing all 241 pages is not
required to prove the framework; overnight runs acceptable.

### [x] CP-4.4 Symbolic retrieval — completed 2026-09-29
Safe graph filtering (AST-restricted evaluation), community lookup, `get_community_for_node`, graph
query utilities, tests. CPU only; no VLM, no API.
- [x] `studies/ladrag/graph_retrieval.py`: `GraphIndex` — node → page (validated against the ID), ordered unique pages, neighbours with scope all / cross-page / intra-page (cross-page := endpoints on different pages) and relation-type / origin filters, edge metadata preserved, undirected
- [x] Ordered one-hop expansion for retrieval-eval-v1 (R24, D-021): seed rank → neighbour page → node ID order, deterministic deduplication; no gold information; k truncation left to CP-4.5A
- [x] `get_community_for_node(node_id, doc_graph)` over persisted Louvain communities (node ID order; unknown node → error; missing assignment → singleton)
- [x] `studies/ladrag/graph_query.py`: R13 AST sandbox (expression-only, allow-listed syntax/methods, read-only graph facade, restricted builtins, timeout 10 s, result cap)
- [x] Tests `tests/test_ladrag_graph_retrieval.py` (52); full suite 256 passed; ruff clean
- [x] Read-only smoke test on the five Stage-1 graphs (`scripts/ladrag_graph_utilities_smoke.py`): all load, all consistency checks pass, cross-page edges 714 = graph-check count; no gold data, no PR/IPR
- [x] Provenance clarifications: ING-0001 run from uncommitted tree on 2c81370, code committed afterwards as 9522b2b; CP-4.3C audit predates R23, qualitative only

### [ ] CP-4.5 Neural retrieval + element baselines
Neural index over node text on the local GPU (E5-large-v2, BGE-large-en where useful);
element-summary baselines (BM25 / E5 / BGE) kept separate from Phase 3 page-text baselines; all
paper-unspecified parameters config-driven.

### [ ] CP-4.5A Ground-truth graph-expansion evaluation, Stage 1 (proposed, D-021)
Needs CP-4.3D Stage 1, CP-4.4 (neighbour lookup with intra/cross-page edge filter) and CP-4.5 (node
ranking). Conditions A/B/C/D on retrieval-eval-v1, matched distinct-page budget k ∈ {1, 3, 5, 10} and
unbudgeted PR/IPR/|P̂|; reachability diagnostic; D-017 paired comparisons + document-cluster
bootstrap; subgroups multi-page / single-page / source. Outcome: go/no-go for Stage 2. No API.

### [ ] CP-4.6A Agent engine
Full agent loop with ScriptedAgentModel/FakeAgentModel: step/keyword/code parsing, tool dispatch,
observations, malformed replies, sandbox violations, unknown IDs, DONE parsing, fallback, max rounds,
token budget, deterministic stopping. No API.
Acceptance: complete orchestration works with scripted model outputs.

### [ ] CP-4.6B Local agent feasibility
Can a lightweight local text LLM (7B/8B optional, not mandatory) run the agent on 8 GB VRAM? Very
small question subset; tool validity, code validity, rounds, premature DONE, invalid IDs, loops,
completion rate, latency, VRAM. Insufficient quality is a valid, documented outcome.

### [ ] CP-4.6C Limited DeepSeek agent evaluation (optional paid; explicit approval required)
Re-check model/price first; hard cap: cumulative DeepSeek spend < USD 5. Start with 20 evidence
questions (≈ 10 single-page, 10 multi-page); compare semantic-only vs. full LAD-RAG† only; record
tokens, turns, cost/question, total cost, PR, IPR, failures, tool use. Expansion only after approval.

### [ ] CP-4.7 Optional ablation / reproduction comparison
Only if preliminary LAD-RAG† results are meaningful, budget remains, and ablations (full, w/o C,
w/o G, w/o C&G) answer a useful question. Never executed automatically.

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
