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

## Open (to be decided in later checkpoints)
- ~~Python version and environment manager (CP-0.3).~~ Decided in D-006.
- ~~PR edge cases (CP-1.2).~~ Decided in D-008. ~~IPR edge cases (CP-1.3).~~ Decided in D-009.
- LVLM / LLM used for ingestion and agent (GPT-4o as in paper vs. open/local model) — cost and hardware dependent (Phase 4).
- Embedding model for the LAD-RAG neural index (not specified in the paper) (Phase 4).
