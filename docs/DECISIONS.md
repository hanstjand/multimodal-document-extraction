# Decisions

Record architecture, methodology, data, and metric decisions here.
Never delete a decision; supersede it with a new one and update the old one's Status.

Template:

```
## D-XXX: <title>
- Date:
- Status: Proposed | Accepted | Superseded by D-YYY | Rejected
- Context:
- Decision:
- Reason:
- Alternatives:
- Consequences:
```

---

## D-001: Checkpoint-based development
- Date: 2026-09-27
- Status: Accepted
- Context: Multi-month research project with reproduction, domain shift, and an undecided contribution; high risk of scope drift and of unverifiable results.
- Decision: Work proceeds one checkpoint at a time (`docs/CHECKPOINTS.md`), with an append-only `docs/RESEARCH_LOG.md`, and explicit user approval between checkpoints.
- Reason: Traceability and reproducibility; keeps the research direction open until evidence exists.
- Alternatives: Free-form development; issue tracker only.
- Consequences: Slower pace, but every result is attributable to a logged, approved step.

## D-002: `src/` package layout, package name `ladrag_reproduction`
- Date: 2026-09-27
- Status: Superseded by D-005 (package name only; `src/` layout still applies)
- Context: Need an importable package usable from scripts, tests, and notebooks.
- Decision: `src/ladrag_reproduction/` with subpackages `datasets`, `ingestion`, `retrieval`, `graph`, `evaluation`, `utils`; metadata in `pyproject.toml` (setuptools).
- Reason: `src` layout prevents accidental imports from the working directory; standard tooling.
- Alternatives: flat layout; Poetry / uv project managers (can still be adopted in CP-0.3).
- Consequences: Package must be installed (editable) to be imported; done in CP-0.3.

## D-003: Result source labelling
- Date: 2026-09-27
- Status: Accepted
- Context: Paper numbers, reproduction numbers, domain-shift numbers, and proposed-method numbers will coexist.
- Decision: Every reported number carries one of `[PAPER]`, `[REPRO]`, `[TECH]`, `[PROPOSED]`; machine-readable results carry a `source` field.
- Reason: Prevents accidental conflation and misreporting.
- Alternatives: Separate files only.
- Consequences: Result schemas must include the label.

## D-004: Repository hygiene — Git, line endings, untracked binaries
- Date: 2026-09-27
- Status: Accepted (ignore patterns amended by D-005 for per-study folders)
- Context: CP-0.2. Windows development machine; reference PDFs are large (the LAD-RAG PDF is 18.5 MB) and more papers will be added in Phase 6; Claude Code writes a per-user `.claude/settings.local.json`.
- Decision: Local Git repo on branch `main`. `.gitattributes` normalizes text to LF (CRLF for `.ps1`/`.bat`) and marks PDFs/images/parquet as binary. `papers/*.pdf` and `.claude/settings.local.json` are git-ignored; papers are listed with source and SHA-256 in `papers/README.md`. Data, run artifacts, model weights, and `.env` are ignored (as in the initial `.gitignore`).
- Reason: Keeps history small and portable; avoids redistributing third-party PDFs; per-user tool settings are not project state.
- Alternatives: Commit PDFs directly; Git LFS for PDFs; commit `.claude/settings.local.json`.
- Consequences: A fresh clone needs the paper re-downloaded (checksum allows verification). Easy to reverse by removing the ignore line.

## D-005: One broad research repository, with LAD-RAG as Study 01
- Date: 2026-09-27
- Status: Accepted
- Context: The repository was scaffolded as a LAD-RAG reproduction project (package `ladrag_reproduction`). The user clarified that it is the main repository for the whole Master's research on Multimodal Document Extraction; LAD-RAG reproduction is only the first empirical study. The final novelty is intentionally not fixed.
- Decision: Use one broad research repository rather than a LAD-RAG-specific repository. Rename the package to `multimodal_document_extraction`. Shared components (`datasets`, `ingestion`, `retrieval`, `graph`, `evaluation`, `agents`, `utils`) live at the top level of the package; method-specific code lives in `studies/<study>/` (Study 01: `studies/ladrag/`). Study material follows the same pattern: `docs/studies/ladrag/`, `papers/ladrag/`, `experiments/ladrag/`, `experiments/technical/`. Roadmap reorganized into Phases 0–7 with Study 01 = Phase 4 and Study 02 = Phase 5; Phase 7 (proposed method) is left undefined.
- Reason: LAD-RAG reproduction is only the first empirical study. The same repository will later contain technical-domain experiments, failure analysis, additional methods, and the eventual proposed approach.
- Alternatives: A LAD-RAG-specific repository plus separate repositories for later studies (fragments shared code and history); keeping the `ladrag_reproduction` namespace (would misrepresent later work as part of LAD-RAG).
- Consequences: Shared components such as datasets, retrieval, evaluation, graph, ingestion, and utilities use the generic project namespace and must stay method-agnostic; LAD-RAG-specific logic must not leak into them. Ignore patterns became `papers/**/*.pdf` and `experiments/*/runs/*`. D-002's package name is superseded.

## D-006: Python environment — conda env `mmde`, Python 3.11, dependencies added on demand
- Date: 2026-09-27
- Status: Accepted
- Context: CP-0.3. The machine's default `python` is conda base (3.13.12, with unrelated packages such as PyTorch 2.12); it must not be used for the project. The LAD-RAG paper used Python 3.10.12 / PyTorch 2.7.0+cu126 / vLLM 0.9.2. Python 3.10 reaches end-of-life in October 2026.
- Decision: Dedicated conda environment `mmde` (conda-forge, Python 3.11), defined in `environment.yml`; the project is installed editable (`pip install -e .[dev]`). `pyproject.toml` has `requires-python >=3.11`, no runtime dependencies yet, and a `dev` extra (pytest, ruff). Each later checkpoint adds only the runtime dependencies it needs (with a lower bound) and notes them in RESEARCH_LOG; exact versions used by an experiment are captured via `pip freeze` in the run metadata.
- Reason: Isolation from base; 3.11 is close to the paper's 3.10 and broadly supported by the ML stack (PyTorch, sentence-transformers, networkx), while still supported upstream beyond 2026. Adding dependencies on demand keeps the environment small and makes every addition traceable.
- Alternatives: Python 3.10 (exact paper match, but EOL next month); 3.12/3.13 (newer, higher risk of missing wheels for some research libraries); `venv` or `uv` instead of conda (conda already installed and handles CUDA-related packages more easily on Windows); pinning a full dependency set now (premature).
- Consequences: Commands must run inside `mmde` (`conda activate mmde`, or `C:\Users\Hanz\miniconda3\envs\mmde\python.exe`). GPU libraries (PyTorch CUDA build) are not installed yet and will be added in the checkpoint that first needs them (e.g. dense retrieval, CP-3.3). If vLLM is needed later, WSL2/Linux may be required (see ENVIRONMENT.md).

## D-007: Core data models — frozen dataclasses, 1-based page numbers
- Date: 2026-09-27
- Status: Accepted
- Context: CP-1.1. Datasets, retrievers (BM25, dense, LAD-RAG, later methods), and metrics must share one representation of documents, questions, gold evidence pages, and retrieval outputs. Datasets differ in page indexing; LAD-RAG object IDs use `page_<n>`; MMLongBench-Doc's indexing is not yet verified (CP-2.1).
- Decision:
  - Module `src/multimodal_document_extraction/data_models.py` with `Document`, `Page`, `Question`, `RetrievedItem`, `RetrievalResult`, implemented as **frozen stdlib dataclasses** (no new dependency), validated in `__post_init__`, with explicit `to_dict`/`from_dict` for JSONL.
  - **Page numbers are 1-based physical page positions** in the PDF (first page = 1), never printed page labels. Loaders convert dataset-native indexing; the conversion is verified per dataset (MMLongBench-Doc in CP-2.1).
  - Retrieval granularity is explicit (`unit_type` ∈ {page, element, node}); every item carries its page, so page-level metrics use `RetrievalResult.retrieved_pages` (the set P̂).
  - `RetrievalResult` invariants: one document; ranks exactly 1..n; no duplicate units. Unranked outputs (e.g. an agent's set) get ranks in output order. `top_k(k)` truncates *items*; `pages_in_rank_order()` is available for page-level cut-offs (which of the two the LAD-RAG Figure 3 x-axis uses is still open, PAPER_NOTES §15.9).
  - `Question.evidence_pages` may be empty; the metric decides how to treat it (CP-1.2/1.3).
  - `metadata` dicts carry extras, excluded from equality/hash.
  - Invalid values raise `ValueError`; wrong container/item types raise `TypeError`.
- Reason: Zero dependencies and immutability are enough for this scale; explicit validation catches indexing and ranking bugs before they silently corrupt PR/IPR. 1-based numbering matches how humans, PDF viewers, and LAD-RAG object IDs refer to pages.
- Alternatives: pydantic models (richer validation/serialization, extra dependency); 0-based pages (matches Python/PyMuPDF indexing but not annotations or viewers); plain dicts (no validation).
- Consequences: Code using PyMuPDF must convert (`page_number = index + 1`). Serialization is hand-written and must be updated when fields change (covered by round-trip tests). Shared models stay method-agnostic; method-specific structures (e.g. LAD-RAG graph nodes) live in `studies/<study>/`.

## D-008: Perfect Recall — questions without gold evidence pages are excluded
- Date: 2026-09-27
- Status: Accepted (chosen by the user in CP-1.2); extended by D-009 (no-evidence subset evaluation)
- Context: CP-1.2. LAD-RAG defines PR = 1 if P ⊆ P̂ else 0 (§3.3) but does not say how questions with an empty gold set P are handled. MMLongBench-Doc contains unanswerable questions, which are expected to have no evidence pages (to be verified in CP-2.1). With P = ∅, P ⊆ P̂ holds for any retrieval, so every retriever would score 1 for free.
- Decision: PR is **undefined (`None`)** when P is empty. Such questions are excluded from the mean; the summary reports `num_scored` and `num_excluded` next to the mean. Empty retrieval with non-empty P gives PR = 0. Implemented in `src/multimodal_document_extraction/evaluation/retrieval_metrics.py` (`perfect_recall`, `perfect_recall_for`, `mean_perfect_recall`, generic `summarize` / `MetricSummary`). Aggregation rejects duplicate question IDs.
- Reason: Avoids inflating PR with trivially satisfied questions and keeps the metric about evidence retrieval.
- Alternatives: Count as PR = 1 (literal definition; inflates PR by the share of unanswerable questions); configurable policy (more code, not needed yet).
- Consequences: Our PR may not be directly comparable to the paper's if the paper counted these questions; comparisons with `[PAPER]` numbers must state the policy. If needed, a "PR incl. trivial" number can be derived later from `num_excluded`.

## D-009: IPR edge cases and separate evidence / no-evidence reporting
- Date: 2026-09-27
- Status: Accepted (specified by the user in CP-1.3)
- Context: CP-1.3. IPR = |P̂ \ P| / |P̂| (LAD-RAG §3.3) is 0/0 for an empty retrieval, and questions without gold evidence pages (P = ∅) cannot be evaluated with Perfect Recall (∅ ⊆ P̂ trivially). The paper specifies neither case.
- Decision:
  - Case 1 — P ≠ ∅, P̂ = ∅: PR = 0, IPR = 0.0.
  - Case 2 — P = ∅, P̂ = ∅: IPR = 0.0, NoEvidenceCorrect = 1.
  - Case 3 — P = ∅, P̂ ≠ ∅: IPR = 1.0, NoEvidenceCorrect = 0.
  - Standard Perfect Recall is never used for no-evidence questions (D-008).
  - Results are reported per subset: the **evidence subset** (P ≠ ∅) carries the paper-compatible LAD-RAG metrics (PR, IPR); the **no-evidence subset** (P = ∅) carries IPR and NoEvidenceCorrect. The two are never averaged together.
  - Implemented in `evaluation/retrieval_metrics.py`: `irrelevant_pages_ratio[_for]`, `no_evidence_correct[_for]`, `mean_irrelevant_pages_ratio` (evidence subset), `evaluate_retrieval` → `RetrievalEvaluation`.
- Reason: Keeps the strict reproduction metrics comparable to the paper's setting while still measuring how retrievers behave on questions that have no evidence (e.g. unanswerable questions), instead of silently dropping them.
- Alternatives: Treat empty retrieval as undefined IPR (excluded from the mean); keep no-evidence questions in one combined IPR mean.
- Consequences: With IPR = 0 for empty retrieval, a retriever that returns nothing gets IPR 0 — IPR must always be read together with PR on the same (evidence) subset. NoEvidenceCorrect = 1 only for a completely empty retrieval, so fixed-top-k baselines always score 0 on it; it is mainly informative for dynamic retrievers (e.g. the LAD-RAG agent). Experiment records must carry both subsets (EXPERIMENT_PROTOCOL).

## D-010: MMLongBench-Doc source — GitHub samples.json (1,082) and GitHub PDFs, pinned
- Date: 2026-09-27
- Status: Accepted
- Context: CP-2.1. Two official sources exist. GitHub `samples.json` has 1,082 questions (= LAD-RAG paper); the HF split has 1,091 (later revision: 26 new questions, 11 edited, 17 absent). The HF file endpoint served wrong bytes for some PDFs (e.g. `mi_phone.pdf` → `NYU_graduate.pdf`), while HF metadata hashes match GitHub.
- Decision: Use GitHub `mayubo2333/MMLongBench-Doc` @ `d73f0dc0be7e0a2ff6a403d5fe65fcd96461f384` for both annotations (`data/samples.json`) and PDFs; verify every file against its git blob hash and cross-check PDFs with HF-listed hashes; record sha256 in `data/raw/mmlongbench-doc/MANIFEST.json`. The HF parquet (@ `2ff6aa92…`) is stored for reference but not used. PyMuPDF (`pymupdf>=1.24`) added as the first runtime dependency (D-006 policy), used for page counts / text and later rendering.
- Reason: The 1,082-question version is the one the LAD-RAG paper evaluated; pinned commits plus content hashes make the data reproducible and guard against the observed serving error.
- Alternatives: HF split (1,091, newer labels; not paper-comparable); HF PDFs (unreliable endpoint at download time); pypdf instead of PyMuPDF (BSD license, but the paper renders with PyMuPDF).
- Consequences: Results are paper-comparable in question set. Known data issues (wrong `dr-vorapp` PDF, 9 invalid evidence pages, 28 PDFs without text layer) are documented in `docs/studies/ladrag/MMLONGBENCH_DOC.md` and must be handled explicitly in CP-2.2 / Phase 3. PyMuPDF is AGPL-3.0 — acceptable for academic research; revisit if code is ever distributed under a different license.

## D-011: LAD-RAG reproduction resource strategy (LAD-RAG†)
- Date: 2026-09-27
- Status: Accepted (CP-4.0); **partially superseded by D-019** (accepted 2026-09-27, CP-4.1A).
  - **Superseded (model/resource/budget parts):** GPT-4o calibration on calib-v1; gpt-4o-mini as primary ingestion model and the ingestion tiers I-0…I-4 as prioritized in CP-4.0; agent plan "local 7–8B for development, DeepSeek for pilot evaluation" as a default; the CP-4.0 budget plan (OpenAI ≈ $0.8–3.4, DeepSeek ≈ $1–3, 80%-of-balance stop rule) and the upgrade path "agent → GPT-4o, ingestion → GPT-4o, full dataset". Replaced by D-019's local-first order, $0-completable checkpoints, and API spending hard rules.
  - **Still valid:** LAD-RAG† naming and explicit substitution reporting (`reproduction_level`, component spec); Study 01 scope = MMLongBench-Doc only; component levels of dataset, metrics, prompts, graph library and baselines; pilot/calibration subset definitions (realized in D-013); separation of PAPER vs. REPRO results; ColPali, RAPTOR and the QA stage deferred unless later reconsidered; LongDocURL, DUDE, MP-DocVQA not reproduced.
- Context: A faithful run needs GPT-4o for ≈ 19.6k image-bearing ingestion calls plus the agent (≈ $200–400 estimated) and the paper used 4× A100 with vLLM. Available: 8 GB local GPU on Windows, $4.68 OpenAI and $3.78 DeepSeek credit. Official code and some details are unpublished.
- Decision: Follow `docs/studies/ladrag/REPRODUCTION_PROTOCOL.md`: keep dataset, metrics definitions, prompts, agent loop, graph library, and baselines exact; reconstruct unpublished details; substitute the ingestion LVLM (primary gpt-4o-mini; GPT-4o only on a 2-document calibration set; deepseek-flash and local Qwen2.5-VL as fallbacks) and the agent LLM (local 7–8B model for development, DeepSeek API for pilot evaluation); defer ColPali, RAPTOR, and the QA stage; reproduce MMLongBench-Doc only. Pilot: 10 stratified documents ≤ 40 pages (≈ 200–250 pages, ≈ 70–90 questions). Results are labelled LAD-RAG† with `reproduction_level` and a component spec; paper numbers stay in a separate file. Spending stops at 80% of each balance.
- Reason: Makes the reproduction feasible with available resources while keeping every deviation explicit and the internal comparisons (LAD-RAG† vs. our baselines on identical inputs) valid.
- Alternatives: Full GPT-4o run (unaffordable now); fully local models only (free, but furthest from the paper and slow for vision); wait for lab GPU/budget (blocks progress).
- Consequences: Absolute numbers are not directly comparable with `[PAPER]`; only trends are. The upgrade path (agent → GPT-4o, ingestion → GPT-4o, full dataset) is defined for when resources appear. Token usage must be logged per call to replace planning estimates with measurements.

## D-012: MMLongBench-Doc loader policy — IDs, flags, full vs. clean set
- Date: 2026-09-27
- Status: Accepted (options chosen by the user in CP-2.2)
- Context: CP-2.2. The dataset has no question IDs; 9 questions have evidence pages outside 1..num_pages; 10 questions refer to `dr-vorapp…pdf`, whose shipped file is a different document (CP-2.1).
- Decision:
  - Question ID = `mmlb-<index:04d>-<sha1(doc_id + "\n" + question)[:8]>` (index = position in `samples.json`).
  - Load all 1,082 questions. Evidence pages outside the PDF range are dropped from `evidence_pages`; the original list is kept in `metadata.raw_evidence_pages`; the question gets `quality_flags = ["invalid_evidence_pages"]`. Questions on a document in `KNOWN_WRONG_DOCUMENTS` get `"wrong_document"`. No hand corrections.
  - **Full set** = all 1,082 questions (paper-comparable count). **Clean set** = questions without flags = 1,063.
  - `samples.json` is always checked against `MANIFEST.json`; PDFs optionally (`verify_pdfs=True`).
  - Implemented in `src/multimodal_document_extraction/datasets/mmlongbench_doc.py` (`load_mmlongbench_doc`, `load_pages`).
- Reason: Keeps the paper's question count, avoids introducing our own annotations, and makes every defect visible and filterable.
- Alternatives: Drop flagged questions (1,063 only, not paper-comparable); manually correct page numbers (adds our annotations); index-only or hash-only IDs.
- Consequences: In the full set, 8 of the 9 invalid-page questions lose **all** evidence pages and therefore fall into the no-evidence subset of D-009 (full set: 846 evidence / 236 no-evidence; clean set: 837 / 226). Full-set no-evidence metrics are thus slightly contaminated; the **clean set is the primary evaluation set**, and full-set numbers are reported alongside for paper comparability. IDs depend on the pinned `samples.json` (D-010); a changed file is detected by the checksum.

## D-013: MMLongBench-Doc pilot (pilot-v1) and calibration (calib-v1) subsets
- Date: 2026-09-27
- Status: Accepted (CP-2.3)
- Context: REPRODUCTION_PROTOCOL.md §5 requires a small, stratified, versioned pilot for LAD-RAG† and a 2-document calibration set for the GPT-4o vs. substitute comparison.
- Decision:
  - Eligible documents: all questions clean (D-012) and ≤ 40 pages → 128 documents are clean; the page limit is applied during selection.
  - Seeded rejection sampling (`datasets/subsets.py::select_documents`, seed 0): one document per doc type (7) + 3 more at random; accept when 10 documents, 200–250 pages, 70–90 questions, multi-page share ≥ 0.25, ≥ 5 no-evidence questions, ≥ 1 image-only PDF. Accepted at attempt 2.
  - Calibration: among pilot documents with ≥ 1 multi-page question, all pairs with ≤ 35 pages; one chosen with the seeded RNG. (An extra "one image-only + one text PDF" requirement I had coded was infeasible — the only image-only pilot PDF has 34 pages — and was not part of the protocol; it was removed without changing the seed.)
  - Files (committed): `data/splits/mmlongbench-doc/pilot-v1.json`, `calib-v1.json` (doc IDs, question IDs, seed, attempt, constraints, source commit + samples sha256, per-document stats). The script refuses to overwrite existing versions.
- Result: pilot-v1 = 10 documents, 7 doc types, 241 pages, 80 questions (28 multi-page = 35%, 14 no-evidence, 1 image-only PDF). calib-v1 = `2305.14160v4.pdf` (16 p) + `f8d3a162ab9507e021d83dd109118b60.pdf` (17 p): 33 pages, 16 questions, 7 multi-page.
- Reason: Stratification covers all document types; constraints keep cost within the budget of D-011; seeds and versioned files make the subset reproducible.
- Alternatives: Purely random documents (may miss doc types / multi-page questions); hand-picked documents (selection bias); question-level sampling (breaks document-level ingestion cost control).
- Consequences: Pilot results are on clean questions only and never extrapolated to the full dataset. The calibration set has no image-only PDF, so GPT-4o vs. substitute quality on image-only pages is only observable through the pilot's single image-only document. Any new pilot must be a new version (pilot-v2), not an overwrite.

## D-014: BM25 baseline — page text from PyMuPDF (bm25-pagetext)
- Date: 2026-09-27
- Status: Accepted (option recommended and approved by the user in CP-3.1)
- Context: CP-3.1. The paper's BM25 baseline (bm25s) ranks LVLM-generated element summaries, which only exist after Phase 4 ingestion. 28 of 135 MMLongBench-Doc PDFs (1 of 10 pilot documents) have no text layer.
- Decision:
  - Now: `bm25-pagetext` — BM25 over the PyMuPDF text of each page, one index per document, retrieval unit = page. Image-only pages have empty text (score 0); no OCR.
  - Later (after Phase 4 ingestion): `bm25-elements` — the paper-comparable BM25 over element summaries, as a separate method name.
  - Library `bm25s` (same as the paper), `lucene` scoring, k1 = 1.5, b = 0.75, lowercase, English stopwords, no stemming (paper does not specify tokenization).
  - All pages are returned, ranked by score; ties and zero scores ordered by ascending page number (deterministic), so evaluation can sweep any k up to the document length.
  - A document with no indexable token (image-only) yields all-zero scores, i.e. pages in natural order (bm25s itself raises on an all-empty corpus).
  - Implemented in `src/multimodal_document_extraction/retrieval/bm25.py` (`BM25PageRetriever`, `BM25Config`).
- Reason: Gives a cheap, deterministic lexical baseline now, clearly distinguished from the paper's variant, without new OCR dependencies.
- Alternatives: OCR for image-only pages (extra dependency; deferred); waiting for element summaries (blocks Phase 3); stemming (not specified by the paper).
- Consequences: `bm25-pagetext` numbers are **not** paper-comparable (different text source) and are expected to be weak on image-only documents, where the ranking degenerates to page order. They serve as an internal lower-bound baseline and for the later domain-shift study.

## D-015: Experiment recording format
- Date: 2026-09-27
- Status: Accepted (CP-3.2)
- Context: First experiment (EXP-0001). EXPERIMENT_PROTOCOL.md asked for YAML configs and a clean working tree or a saved diff.
- Decision: Configs are JSON (no new dependency). `utils/run_recording.py` creates `experiments/<study>/runs/<experiment_id>/` (refuses reuse), writes `config.json`, `per_query.jsonl` (full ranking per question, so any metric at any k can be recomputed), `run_meta.json` (git commit/dirty/untracked, package versions, timings, breakdowns) and, for a dirty tree, `git_diff.patch`. `results.csv` gets one row per k with the fields in `RESULTS_FIELDS` (protocol fields + `question_set`, `git_dirty`); header and ID uniqueness are enforced. Aggregates are computed by code only.
- Reason: Machine-readable, append-only, recomputable results; runs remain reproducible even when made before a commit.
- Alternatives: YAML configs (needs PyYAML); MLflow/W&B tracking (heavier, external service); one row per experiment with a k-curve blob (less CSV-friendly).
- Consequences: A dirty-tree run is reproducible only together with its local `git_diff.patch` (runs are not committed); untracked files are listed but not stored, so committing before important runs is preferable.

## D-016: Dense retrieval baseline — E5-large-v2 / BGE-large-en over page text, MaxP chunks
- Date: 2026-09-27
- Status: Accepted (chunking and GPU install chosen by the user in CP-3.3)
- Context: CP-3.3. The paper's dense baselines (E5-large-v2, BGE-large-en) embed LVLM element summaries; those exist only after Phase 4. Both models accept at most 512 tokens; some pages are longer.
- Decision:
  - Methods `dense-e5-large-v2-pagetext` and `dense-bge-large-en-pagetext` over PyMuPDF page text (same text source as D-014), one index per document, retrieval unit = page.
  - Models pinned: `intfloat/e5-large-v2` @ `f169b11e22de13617baa190a028a32f3493550b6` (mean pooling), `BAAI/bge-large-en` @ `abe7d9d814b775ca171121fb03f394dc42974275` (CLS pooling); both MIT, 1024-d, normalized, cosine similarity. Prefixes per official model cards: E5 `"query: "` / `"passage: "`; BGE query instruction `"Represent this sentence for searching relevant passages: "`, no passage prefix.
  - Long pages: windows of whole tokens cut at tokenizer offsets (fit 512 incl. prefix and special tokens), 64-token overlap; page score = max cosine over its windows (MaxP).
  - Pages without text get no score and are ranked after all scored pages by page number; an image-only document degenerates to page order (as in D-014).
  - Runtime: PyTorch 2.14.0+cu126 and sentence-transformers 6.1.0 in the `mmde` env via the optional extra `dense` (torch from the CUDA 12.6 index), fp32 on the local GPU.
  - Implemented in `src/multimodal_document_extraction/retrieval/dense.py` (`DensePageRetriever`, `SentenceTransformerEncoder`, `chunk_text`, `MODELS`).
- Reason: Same models as the paper, evidence anywhere on long pages can be matched, pinned revisions make embeddings reproducible.
- Alternatives: Truncation to the first 512 tokens (misses content at the bottom of long pages); mean over chunks (dilutes single matches); CPU-only torch (slower).
- Consequences: Not paper-comparable (page text instead of element summaries); the paper-style `dense-*-elements` variants follow Phase 4. GPU floating-point non-determinism may cause tiny score differences between runs; device and versions are recorded per run.

## D-017: Paired comparison of retrieval runs
- Date: 2026-09-27
- Status: Accepted (CP-3.4)
- Context: Pilot evaluations have few questions (66 evidence questions in pilot-v1), so a PR difference of 0.06 is 4 questions; unpaired point estimates can mislead.
- Decision: Compare methods only on identical question sets, per question (paired), reporting the mean PR difference at each k with a seeded percentile bootstrap 95% CI (10,000 resamples, seed 0) and win/tie/loss counts; also first-k (pages needed for PR = 1) comparisons and subgroup PR (text-layer / image-only / multi-page). Implemented in `scripts/compare_retrieval_runs.py`; output JSON committed under `experiments/<study>/results/comparisons/`. A CI that includes 0 is reported as "no clear difference".
- Reason: Honest reporting on small samples; the same procedure will be reused for LAD-RAG† vs. baselines and for the domain-shift study.
- Alternatives: McNemar / sign tests (binary PR only); unpaired CIs (wider, ignore pairing); no uncertainty (not acceptable).
- Consequences: Pilot-scale comparisons will often be inconclusive; claims require larger subsets or larger effects. Multiple k values are tested without correction — CIs are descriptive, not confirmatory.

## D-018: LAD-RAG† implementation specification (reconstructions R1–R20)
- Date: 2026-09-27 (drafted CP-4.1; revised in place CP-4.1A)
- Status: **Accepted** — the revised, resource-constrained form was explicitly approved by the user on 2026-09-27 (after CP-4.1A). (History: an earlier "Accepted" at the start of CP-4.2 was withdrawn in CP-4.1A because it had been inferred from "lanjut 4.2 …"; the decision was revised in place while Proposed. See RESEARCH_LOG, CP-4.1A and the approval entry after it.)
- Context: The paper leaves many implementation details unspecified (PAPER_NOTES §15); figures add some (PAPER_NOTES §16). Implementation needs a fixed, documented choice for each gap, compatible with the resource strategy of D-019 (local-first, $0-completable).
- Decision (proposed): Implement per `docs/studies/ladrag/IMPLEMENTATION_SPEC.md` (revised CP-4.1A):
  - Labels [PAPER-EXACT] / [RECONSTRUCTED] / [SUBSTITUTED] / [OPTIONAL-REFERENCE] on every item; "Local-first, API-last" development order.
  - [PAPER-EXACT]: verbatim prompts Figs. 9–12; NetworkX undirected graph; Louvain; temperature 0; 8192 ingestion tokens; 20 agent rounds; tool names; PyMuPDF 300 DPI.
  - [RECONSTRUCTED], **all config-driven with defaults that are our choices, not paper facts**: node IDs `page_{n}-obj_{k:03d}` (R1, from Fig. 6); image size per model (R2); section candidate types (R3); deterministic intra-page relations (R4); initial memory (R6); edge validation/merging (R7); Louvain resolution 1.0, seed 0 (R8); no `aggregated_section` nodes (R9); embedding model E5-large-v2, windows 512/64, `semantic_search.top_k = 10` (R10); observations ≤ 50 nodes, 300-char summaries (R11); DONE parsing + recall-first fallback (R12); AST sandbox, 10 s timeout (R13); agent max output 1024 tokens, context budget 100k (R15); cache (R16); one JSON repair retry (R17); page-level k for element baselines (R19); ablation mechanics (R20).
  - [SUBSTITUTED]: ingestion VLM → local lightweight VLM selected in CP-4.3B (S1/S2); agent LLM → scripted → local → optional limited DeepSeek (S3); serving → local 8 GB GPU (S4). No provider is hard-coded as mandatory; vendor-neutral `VisionModel` / `AgentModel` interfaces with mock/scripted implementations first.
  - Ingestion is page-level checkpointed, cached and resumable.
  - Phase 4 plan: CP-4.2, 4.3A–D, 4.4, 4.5, 4.6A–C, optional 4.7 (IMPLEMENTATION_SPEC §9).
- Reason: Each choice is the simplest option consistent with the paper text, prompts and figures, while keeping the whole pipeline completable without paid APIs.
- Alternatives: Listed per item in the spec (e.g. an LLM-based intra-page relation prompt, `aggregated_section` construction, other top-k values); the CP-4.1 draft that assumed GPT-4o calibration and gpt-4o-mini ingestion (superseded by this revision).
- Consequences: All R and S items are deviations reported with LAD-RAG† results and can be revisited as ablations; reconstruction defaults must never be presented as paper values.

## D-019: Resource-constrained, local-first Phase 4 strategy and API spending policy
- Date: 2026-09-27
- Status: **Accepted** — explicitly approved by the user on 2026-09-27 (after CP-4.1A). Supersedes **only** the model/resource/budget parts of D-011 (listed in D-011); D-011's methodological parts remain applicable.
- Context: The research is unfunded. Local: Windows 10, i7-10700, 32 GB RAM, Quadro RTX 4000 8 GB. Paid: DeepSeek (cumulative spend must stay < USD 5), small optional OpenAI credit; no lab A100/H100, no paid cloud GPU.
- Decision (proposed):
  - Study 01 is a **resource-constrained partial reproduction**; the system is always LAD-RAG†; results labelled [PAPER-EXACT] / [RECONSTRUCTED] / [SUBSTITUTED] / [OPTIONAL-REFERENCE].
  - "Local-first, API-last": deterministic → mocks/scripted → lightweight local model → feasibility/quality → optional API validation.
  - Phase 4 must be completable with **$0 API spend**; no checkpoint has a paid API or paid compute as an acceptance criterion.
  - Ingestion priority: mocks → local lightweight VLM (chosen in CP-4.3B, ≈ 2B–4B class preferred, 7B/8B not required) → local calibration → local pilot ingestion; stronger API VLM only as an [OPTIONAL-REFERENCE] on 3–5 pages with explicit approval.
  - Agent: scripted engine → local LLM feasibility → optional limited DeepSeek evaluation (20 evidence questions, semantic-only vs. full) → optional ablations.
  - API spending hard rules 1–10 (REPRODUCTION_PROTOCOL §5): $0-executable; no automatic API runs; approval before each paid experiment; DeepSeek cumulative < USD 5; OpenAI optional; no top-up; log actual usage; permanent cache; abort before exceeding budget; recheck prices/models immediately before each paid run.
  - The resource constraint is not the thesis contribution; related observations are hypotheses only until Phases 5–6.
- Reason: Makes the reproduction feasible and reproducible for an unfunded Master's project while keeping the LAD-RAG architecture.
- Alternatives: D-011 as accepted in CP-4.0 (API-first ingestion calibration, ≈ $2–6.5 spend); waiting for funding/GPU access.
- Consequences: Ingestion quality depends on what fits 8 GB; weaker ingestion/agent quality is a possible, honestly reported outcome. Absolute numbers are further from the paper's setting; internal comparisons on the same pilot remain valid.

## D-020: CP-4.3B outcomes — parser reconstructions R17b/R17c/R21 and local ingestion model
- Date: 2026-09-28
- Status: **Proposed** — awaiting user approval of CP-4.3B (CP-4.3C only starts after approval)
- Context: The 5-page local feasibility run (LOCAL_VLM_FEASIBILITY.md) showed that correct model outputs were lost to parser strictness (single object / id-map containers, LaTeX escapes), that a first container fix could silently salvage a fragment from a truncated reply, and that Fig. 11 on pages without nodes produces invented IDs and runaway output.
- Decision (proposed):
  - Keep the framework changes already implemented and tested: R17b container normalization (flagged), R17c column-0 JSON parsing with a single lenient-escape attempt (flagged; never salvages from broken structures), R21 skip Fig. 11 for pages without nodes (flagged). Ingestion record version 3.
  - Select **Qwen/Qwen3.5-2B @ 15852e8c, fp16, thinking disabled, greedy, images ≤ 1280 px** as the local ingestion model for CP-4.3C (verdict: feasible with limitations); reject Qwen3-VL-2B-Instruct (runaway repetition on 7/11 heavy calls, 2/5 pages without nodes).
  - Dependencies: optional `vlm` extra (torch, torchvision 0.29.0+cu126, pillow 12.3.0, transformers ≥ 5).
- Reason: The fixes recover valid content without inventing any; model choice follows the pre-registered verdict rules.
- Alternatives: stricter paper-only list parsing (loses correct content); quantized 4B model (extra dependency, not needed yet); [OPTIONAL-REFERENCE] API model (not needed for feasibility).
- Consequences: Container shape, lenient escapes and skipped Fig. 11 calls are reported per page (flags). Known limitations (figure omission on dense academic pages, occasional runaway generations, rare `is_part_of_section` edges) carry into calibration; decoding/resolution mitigations need a separate approval in CP-4.3C.

## Open (to be decided in later checkpoints)
- ~~Python version and environment manager (CP-0.3).~~ Decided in D-006.
- ~~PR edge cases (CP-1.2).~~ Decided in D-008. ~~IPR edge cases (CP-1.3).~~ Decided in D-009.
- ~~LVLM / LLM used for ingestion and agent (Phase 4).~~ Strategy decided in D-011; final ingestion model confirmed after calibration (CP-4.3).
- Embedding model for the LAD-RAG neural index (not specified in the paper) (Phase 4).
- ~~MMLongBench-Doc loader policy (CP-2.2).~~ Decided in D-012.
- ~~Text source for text-based baselines (before CP-3.1).~~ Decided in D-014 (page text now; element summaries after Phase 4).
