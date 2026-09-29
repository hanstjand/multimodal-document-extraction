# Research Log

**Append-only.** Never edit or delete historical entries. Corrections go in a new entry that
references the earlier one. Newest entry at the bottom.

Entry template:

```
## <YYYY-MM-DD> — <CP-ID> <title>
- Date:
- Checkpoint:
- Objective:
- Work performed:
- Configuration:
- Results:
- Problems:
- Observations:
- Next step:
```

---

## 2026-09-27 — Bootstrap: documentation scaffold (pre-checkpoint)
- Date: 2026-09-27
- Checkpoint: none (project bootstrap, requested by user before CP-0.1)
- Objective: Create the documentation, checkpoint system, and directory scaffold; read the paper and write paper notes.
- Work performed:
  - Created `CLAUDE.md`, `README.md`, `pyproject.toml` (minimal, no dependencies), `.gitignore`, `.env.example`.
  - Created `docs/` (PROJECT_CONTEXT, RESEARCH_PLAN, CHECKPOINTS, RESEARCH_LOG, DECISIONS, PAPER_NOTES, EXPERIMENT_PROTOCOL).
  - Created `data/{raw,processed,technical}`, `src/ladrag_reproduction/{datasets,ingestion,retrieval,graph,evaluation,utils}`, `scripts/`, `experiments/{configs,runs,results}`, `tests/`, `notebooks/` with READMEs / `.gitkeep` / empty `__init__.py`.
  - Extracted paper text with PyMuPDF (already present in conda base) to a session scratch file (not in repo) and wrote `docs/PAPER_NOTES.md`.
- Configuration: n/a
- Results: n/a (no experiments)
- Problems: The Read tool could not render PDF pages (poppler `pdftoppm` not installed); used PyMuPDF text extraction instead, so figures (e.g. Fig. 3 PR/IPR curves) were not read.
- Observations: The local PDF text is stamped `arXiv:2510.07233v2 (28 Feb 2026)` although the filename is the ACL anthology ID. Official code is not released (App. A). Several implementation details are unspecified (PAPER_NOTES §15).
- Next step: CP-0.1 Environment Inspection.

## 2026-09-27 — CP-0.1 Environment Inspection
- Date: 2026-09-27
- Checkpoint: CP-0.1
- Objective: Record OS, Python, Git, CPU, RAM, GPU, VRAM, NVIDIA driver without modifying the system.
- Work performed: Read-only queries: `Get-CimInstance` (OS, CPU, RAM, video controllers, disks), `python --version`, `conda --version`, `conda env list`, `git --version`, `nvidia-smi` (full + CSV query), import check of `torch`/`fitz` in conda base. Recorded in `docs/ENVIRONMENT.md`.
- Configuration: n/a
- Results:
  - OS: Windows 10 Pro 10.0.19045, 64-bit.
  - CPU: Intel Core i7-10700, 8 cores / 16 threads. RAM: 31.8 GB. Disk C: 168 GB free of 930 GB.
  - GPU: NVIDIA Quadro RTX 4000, 8192 MiB VRAM, compute capability 7.5, driver 595.97, driver CUDA 13.2, WDDM.
  - Python: 3.13.12 (miniconda base, default `python`); Python 3.8 also installed. conda 26.1.1.
  - Git: 2.53.0.windows.2.
  - conda base has PyTorch 2.12.0+cu126 with CUDA available, and PyMuPDF 1.27.2.3.
- Problems: none blocking. poppler not installed (only matters for tool-side PDF rendering; PyMuPDF covers our needs).
- Observations: 8 GB Turing GPU is enough for BM25/dense-retriever baselines; 7B+ LVLMs would need quantization or remote compute; vLLM not officially supported on native Windows. Project should use a dedicated environment rather than conda base (to be decided in CP-0.3). Paper env: Python 3.10.12, PyTorch 2.7.0+cu126, vLLM 0.9.2, 4× A100.
- Next step: CP-0.2 Repository Structure — awaiting explicit user approval.

## 2026-09-27 — Paper replaced with ACL camera-ready
- Date: 2026-09-27
- Checkpoint: none (documentation update between CP-0.1 and CP-0.2, requested by user)
- Objective: Verify the user-supplied ACL camera-ready PDF that replaced the arXiv v2 copy, and update notes.
- Work performed: Extracted text of the new `papers/2026.acl-long.724.pdf` with PyMuPDF; compared it word-by-word and number-by-number against the earlier arXiv v2 extraction. Updated `docs/PAPER_NOTES.md` (header, §11 QA metric, §13 code availability, open question 12) and `docs/PROJECT_CONTEXT.md`.
- Configuration: n/a
- Results: New file is the ACL 2026 Long camera-ready (Proceedings of the 64th Annual Meeting of the ACL, Vol. 1, pp. 15945–15968; pdfTeX, 2026-06-09), 24 pages, SHA-256 b382fb43b207170a6fcff17ae13b830d05b6abe5f17de98bfe2ca9c7f97261a4. All 694 three-decimal numbers identical to arXiv v2. Substantive text changes: (a) §3.3 QA judge extracts concise answers "from models' outputs" (arXiv v2: "from retrieved content"); (b) App. A drops the promise to release code / share on request — code remains unreleased.
- Problems: none.
- Observations: The bootstrap entry above refers to the arXiv v2 text; it remains valid as history. Notes now cite the ACL version.
- Next step: CP-0.2 (approved by user in the same message).

## 2026-09-27 — CP-0.2 Repository Structure
- Date: 2026-09-27
- Checkpoint: CP-0.2
- Objective: Initialize Git, verify the project structure, finalize `.gitignore` and the documentation scaffold.
- Work performed:
  - `git init -b main` (local repo only; global Git config untouched).
  - Added `.gitattributes` (LF normalization, CRLF for .ps1/.bat, binary PDFs/images/parquet).
  - Extended `.gitignore`: `papers/*.pdf`, `.claude/settings.local.json`.
  - Added `papers/README.md` listing the paper with source IDs and SHA-256.
  - Recorded D-004 (repository hygiene) in `docs/DECISIONS.md`; updated `README.md`.
  - Verified all 33 planned paths exist; verified ignore rules with `git check-ignore` (8 must-ignore paths ignored, 5 must-track paths not ignored).
- Configuration: Git 2.53.0.windows.2, branch `main`.
- Results: `git status` works; 33 files untracked and ready for an initial commit; no PDFs, data, or secrets among them.
- Problems: Global Git identity is `user.name=clickbyte`, `user.email=clickbytedev@gmail.com`, which may not be the intended author identity for this project. Initial commit deliberately not made — awaiting user approval and identity confirmation.
- Observations: Scaffold files were created during bootstrap (before CP-0.1, at user request); CP-0.2 verified rather than recreated them.
- Next step: (1) user approves initial commit and author identity; (2) CP-0.3 Python Project Setup — awaiting explicit user approval.

## 2026-09-27 — CP-0.2A Repository Scope Realignment
- Date: 2026-09-27
- Checkpoint: CP-0.2A (new checkpoint inserted between CP-0.2 and CP-0.3 at user request; CP-0.2 remains completed and unchanged)
- Objective: Realign the repository from a LAD-RAG reproduction project to the main repository of the Master's research on Multimodal Document Extraction, with LAD-RAG reproduction as Study 01.
- Work performed:
  - Moved: `src/ladrag_reproduction/` → `src/multimodal_document_extraction/`; `papers/2026.acl-long.724.pdf` → `papers/ladrag/` (SHA-256 unchanged); `docs/PAPER_NOTES.md` → `docs/studies/ladrag/PAPER_NOTES.md`; `experiments/{configs,runs,results}/` → `experiments/ladrag/{configs,runs,results}/` (old folders held only `.gitkeep`).
  - Created: `src/multimodal_document_extraction/agents/`, `studies/`, `studies/ladrag/` (empty packages with docstrings only), `experiments/technical/{configs,runs,results}/`.
  - Modified: `pyproject.toml` (name `multimodal-document-extraction`), package `__init__.py` docstring, `.gitignore` (`papers/**/*.pdf`, `experiments/*/runs/*`), `README.md` (rewritten), `CLAUDE.md` (scope + code-layout rule), `docs/PROJECT_CONTEXT.md` (rewritten), `docs/RESEARCH_PLAN.md` (Phases 0–7), `docs/CHECKPOINTS.md` (CP-0.2A added; phase headings renamed; Phase 7 placeholder; CP IDs unchanged), `docs/EXPERIMENT_PROTOCOL.md` (`study` field, per-study paths), `docs/DECISIONS.md` (D-005 added; status lines of D-002 and D-004 updated), `experiments/README.md`, `papers/README.md`, `notebooks/README.md`, `docs/studies/ladrag/PAPER_NOTES.md` (header path).
  - Verified: no stale references outside historical entries; ignore rules re-checked with `git check-ignore` (7 must-ignore, 5 must-track paths correct); old directories removed.
- Configuration: n/a
- Results: Repository scope is now "Multimodal Document Extraction"; 39 untracked files ready for an initial commit (no PDFs, data, or secrets).
- Problems: none. Initial commit still not made (pending user approval and Git identity confirmation, see CP-0.2 entry).
- Observations: Historical entries in this log and D-002 still mention `ladrag_reproduction` and old paths; they are left unchanged by design. CP-6.3–6.5 kept their IDs; they may move to Phase 7 once Phase 7 is defined. No research direction (Graph RAG, cross-page retrieval, cost efficiency, ...) has been selected.
- Next step: CP-0.3 Python Project Setup — awaiting explicit user approval.

## 2026-09-27 — Repository published to GitHub (between checkpoints)
- Date: 2026-09-27
- Checkpoint: none (user-requested housekeeping after CP-0.2A; CP-0.3 not started)
- Objective: Create the initial commit and push to the remote repository for progress tracking.
- Work performed: Set repo-local Git identity `hanstjand <hanstjand@gmail.com>` (global config unchanged, user's choice); initial commit of all tracked files on `main`; added remote `origin` = https://github.com/hanstjand/multimodal-document-extraction.git and pushed.
- Configuration: Git 2.53.0.windows.2; Git Credential Manager.
- Results: see git history (commit hash is recorded by Git itself).
- Problems: none.
- Observations: Paper PDFs, data, run outputs, `.env`, and `.claude/settings.local.json` are excluded by `.gitignore` and were not pushed.
- Next step: CP-0.3 Python Project Setup — awaiting explicit user approval.

## 2026-09-27 — CP-0.3 Python Project Setup
- Date: 2026-09-27
- Checkpoint: CP-0.3
- Objective: Create an isolated Python environment, finalize `pyproject.toml`, define minimal dependencies, install the package, verify imports.
- Work performed:
  - Decision D-006: conda env `mmde`, Python 3.11 (conda-forge), dependencies added on demand.
  - Added `environment.yml`; updated `pyproject.toml` (`requires-python >=3.11`, `dev` extra with pytest>=8 and ruff>=0.6, ruff config).
  - Added `tests/test_imports.py` (package + 9 subpackages); removed `tests/.gitkeep`.
  - `conda env create -f environment.yml --yes` → created env and ran `pip install -e .[dev]`.
  - Updated `README.md` (setup), `docs/ENVIRONMENT.md` (project environment), `docs/DECISIONS.md`, `docs/CHECKPOINTS.md`.
- Configuration: conda 26.1.1; env `mmde` at `C:\Users\Hanz\miniconda3\envs\mmde`; Python 3.11.16; pip 26.2.1; setuptools 84.0.0.
- Results:
  - Editable install of `multimodal-document-extraction 0.0.1` succeeded.
  - `import multimodal_document_extraction` (run from %TEMP%, outside the repo) resolves to `src/multimodal_document_extraction/__init__.py`; all 9 subpackages import.
  - `pytest -q`: 10 passed in 0.03 s. `ruff check .`: all checks passed; `ruff format --check .`: 25 files already formatted. `pip check`: no broken requirements.
  - Installed: pytest 9.1.1, ruff 0.16.9, colorama 0.4.6, iniconfig 2.3.0, pluggy 1.6.0, Pygments 2.21.0, packaging 26.3.
- Problems: none blocking. conda printed "3 channel Terms of Service accepted" during env creation (conda's own ToS handling for configured channels; no manual acceptance was performed). conda also reported a newer conda (26.7.2) — not updated (system software left unchanged).
- Observations: The global `defaults` channel was listed alongside conda-forge during solving; the env pins only Python/pip, so this has no effect on project packages. No runtime/GPU dependencies installed yet; PyTorch etc. will be added by the checkpoint that first needs them. Phase 0 is complete.
- Next step: CP-1.1 Core data models — awaiting explicit user approval.

## 2026-09-27 — CP-1.1 Core data models
- Date: 2026-09-27
- Checkpoint: CP-1.1
- Objective: Define method-agnostic, validated data models for documents, pages, questions with gold evidence pages, retrieved items, and retrieval results.
- Work performed:
  - (Before starting: committed and pushed CP-0.3 as `89d62ee`, per user approval.)
  - Decision D-007: frozen stdlib dataclasses; 1-based physical page numbers; explicit retrieval unit type; RetrievalResult invariants; JSON round-trip.
  - Added `src/multimodal_document_extraction/data_models.py` (`Document`, `Page`, `Question`, `RetrievedItem`, `RetrievalResult`, `RETRIEVAL_UNITS`).
  - Added `tests/test_data_models.py` (construction, validation errors, frozen/equality semantics, evidence-page coercion, `retrieved_pages`, `pages_in_rank_order`, `top_k`, JSON round-trip).
- Configuration: conda env `mmde`, Python 3.11.16, pytest 9.1.1, ruff 0.16.9. No new dependencies.
- Results: `pytest -q`: 47 passed (37 new + 10 import smoke tests). `ruff check .` and `ruff format --check .` clean.
- Problems: First ruff run flagged RUF009 (function call in dataclass default) and TRY004 (TypeError for type checks); fixed by inlining `field(...)` and raising `TypeError` for wrong container/item types.
- Observations: The page-indexing convention of MMLongBench-Doc is not verified yet; the loader in CP-2.2 must convert to 1-based and CP-2.1 must document the native convention. Whether LAD-RAG's Figure 3 "k" counts items or pages remains open (PAPER_NOTES §15.9); both views are supported (`top_k`, `pages_in_rank_order`). No metrics implemented yet.
- Next step: CP-1.2 Perfect Recall metric — awaiting explicit user approval.

## 2026-09-27 — CP-1.2 Perfect Recall metric
- Date: 2026-09-27
- Checkpoint: CP-1.2
- Objective: Implement LAD-RAG's Perfect Recall (PR = 1 if P ⊆ P̂ else 0) with explicit edge-case handling and aggregation.
- Work performed:
  - User chose the policy for questions without gold evidence pages: exclude (D-008).
  - Added `src/multimodal_document_extraction/evaluation/retrieval_metrics.py`: `perfect_recall` (page sets), `perfect_recall_for` (Question + RetrievalResult, checks matching question/doc IDs), generic `summarize` + `MetricSummary`, `mean_perfect_recall`.
  - Added `tests/test_perfect_recall.py` (exact/superset/missing/empty retrieval, empty gold → None, invalid pages, element-level results mapped to pages, top-k dependence, mismatched pairs, exclusion counting, all-excluded/empty input, generators, duplicate questions).
- Configuration: conda env `mmde`, Python 3.11.16. No new dependencies.
- Results: `pytest -q`: 68 passed (21 new). `ruff check .` clean; formatting applied.
- Problems: none.
- Observations: The policy may make our PR differ from the paper's if the paper counted unanswerable questions as trivially recalled; any `[PAPER]` vs `[REPRO]` comparison must state D-008. `summarize`/`MetricSummary` are generic and will be reused for IPR. CP-1.1 and CP-1.2 changes are not yet committed (user has not requested a commit since CP-0.3).
- Next step: CP-1.3 Irrelevant Pages Ratio metric — awaiting explicit user approval.

## 2026-09-27 — CP-1.3 Irrelevant Pages Ratio metric
- Date: 2026-09-27
- Checkpoint: CP-1.3
- Objective: Implement LAD-RAG's Irrelevant Pages Ratio (IPR = |P̂ \ P| / |P̂|) with explicit edge cases, and evaluate no-evidence questions without using Perfect Recall.
- Work performed:
  - User specified the edge-case policy (D-009): P≠∅,P̂=∅ → PR 0, IPR 0.0; P=∅,P̂=∅ → IPR 0.0, NoEvidenceCorrect 1; P=∅,P̂≠∅ → IPR 1.0, NoEvidenceCorrect 0; PR never used for no-evidence questions; paper-compatible (evidence) subset reported separately from no-evidence evaluation.
  - Extended `src/multimodal_document_extraction/evaluation/retrieval_metrics.py`: `irrelevant_pages_ratio[_for]`, `no_evidence_correct[_for]`, `mean_irrelevant_pages_ratio` (evidence subset), `RetrievalEvaluation`, `evaluate_retrieval`.
  - Added `tests/test_irrelevant_pages_ratio.py` (formula cases, page-vs-item counting, the three D-009 cases, subset-separated aggregation, subset consistency, generators, duplicates).
  - Updated `docs/EXPERIMENT_PROTOCOL.md` (subset fields, edge-case table), `docs/DECISIONS.md` (D-009; D-008 status note).
- Configuration: conda env `mmde`, Python 3.11.16. No new dependencies.
- Results: `pytest -q`: 85 passed (17 new). `ruff check .` and `ruff format --check .` clean.
- Problems: none.
- Observations: IPR = 0 for an empty retrieval means IPR is only meaningful together with PR on the same subset. NoEvidenceCorrect can only be 1 for an empty retrieval, so fixed-top-k baselines score 0 on it by construction; it becomes informative for dynamic retrievers. Whether MMLongBench-Doc's unanswerable questions actually have empty evidence-page annotations is to be verified in CP-2.1. Phase 1 (evaluation foundation) is complete.
- Next step: CP-2.1 Inspect MMLongBench-Doc — awaiting explicit user approval.

## 2026-09-27 — CP-2.1 Inspect MMLongBench-Doc
- Date: 2026-09-27
- Checkpoint: CP-2.1
- Objective: Obtain MMLongBench-Doc reproducibly and document source, license, format, evidence-page indexing, unanswerable-question handling, statistics, and data-quality issues.
- Work performed:
  - Added `scripts/download_mmlongbench_doc.py` (pinned GitHub commit d73f0dc0 + HF revision 2ff6aa92; git-blob verification; sha256 manifest) and `scripts/inspect_mmlongbench_doc.py` (report → `data/processed/mmlongbench-doc/inspection.json`).
  - Added runtime dependency `pymupdf>=1.24` (installed 1.28.2) per D-006; recorded D-010.
  - Wrote `docs/studies/ladrag/MMLONGBENCH_DOC.md` (dataset card) and updated `data/README.md`, `docs/ENVIRONMENT.md`.
  - Rendered pages 1 and 7 of `dr-vorapp…pdf` (scratch, not in repo) to confirm its content visually.
- Configuration: conda env `mmde`, Python 3.11.16, PyMuPDF 1.28.2. Data: 138 files, 666.9 MB in `data/raw/mmlongbench-doc/`.
- Results (dataset facts, not experiments):
  - 1,082 questions / 135 PDFs / 6,529 pages (mean 48.36, median 28, min 9, max 468). 360 multi-page (33.3%), 494 single-page, 228 empty evidence, 223 "Not answerable".
  - Evidence pages are 1-based physical pages: answer found on annotated page in 46/55 tested questions under 1-based vs 0/55 under 0-based.
  - "Not answerable" ≠ empty evidence: 7 unanswerable questions have evidence pages; 12 answerable questions have none. D-009 subsets: 854 evidence / 228 no-evidence.
  - HF split has 1,091 rows (26 new, 11 edited, 17 absent vs GitHub); GitHub's 1,082 matches the LAD-RAG paper.
- Problems:
  - HF `/resolve` endpoint served wrong bytes for some PDFs (e.g. `mi_phone.pdf` → `NYU_graduate.pdf`); first download attempts aborted on verification. Switched PDF source to GitHub; 120 PDFs already fetched from HF were deleted and re-downloaded. A first comparison flagged 24 false mismatches (small non-LFS files on HF); fixed by comparing git blob hashes for those.
  - `dr-vorapptchapter1emissionsources…pdf` is byte-identical to `digitalmeasurementframework…pdf` in both sources (confirmed visually: "Making Sense of Data … Digital Measurement Framework"); its 10 questions (vehicle emissions) are not answerable from the shipped file.
  - 9 questions have invalid evidence pages (three `[0]`, six beyond the page count — likely printed page labels or a typo such as 1418).
  - 28 of 135 PDFs have no text layer.
  - One transient network reset during download (recovered by retry). PyMuPDF printed non-fatal color-space warnings.
- Observations: Mean page count differs from the paper (48.36 vs 47.5); the wrong 196-page `dr-vorapp` file would explain the difference if the paper-era file had ~80 pages (plausible, unverified). Text-based baselines over raw PDF text cannot cover the 28 image-only PDFs — a text-source decision is needed before CP-3.1. VS Code's Pylance reports `pymupdf` unresolved because the editor interpreter is not the `mmde` env (editor setting only; tests and scripts run in `mmde`).
- Next step: CP-2.2 Dataset loader — awaiting explicit user approval (needs policies for question IDs, invalid evidence pages, and the `dr-vorapp` questions).

## 2026-09-27 — CP-4.0 Reproduction Resource Strategy (out of order)
- Date: 2026-09-27
- Checkpoint: CP-4.0 (new checkpoint added by the user as the first step of Phase 4; executed now, before CP-2.2, because it constrains the pilot subset and model choices)
- Objective: Decide, before implementing LAD-RAG, what is reproduced exactly, what is substituted given available resources, the pilot size, and how substituted results are reported.
- Work performed:
  - Checked current API prices (OpenAI pricing page; DeepSeek pricing page) on 2026-09-27: GPT-4o $2.50/$10.00, gpt-4o-mini $0.15/$0.60, gpt-5-mini $0.25/$2.00 per 1M tokens (Batch −50%); deepseek-flash (vision) $0.15–0.30/$0.60–1.20, deepseek-v4-pro (no vision) $0.66–1.32/$1.98–3.96.
  - Counted short documents for pilot sizing: 87 of 135 documents have ≤ 40 pages (2,098 pages, 690 questions); every doc_type has ≥ 3 such documents.
  - Wrote `docs/studies/ladrag/REPRODUCTION_PROTOCOL.md` (requirements, unavailable resources, component levels C1–C16, ingestion tiers I-0..I-4, pilot/calibration sets, budget with 80% stop rule, reporting rules, separation of paper vs. reproduced results, upgrade path).
  - Recorded D-011; added `reproduction_level` and `components` fields to `EXPERIMENT_PROTOCOL.md`; linked CP-2.3 acceptance to protocol §5.
- Configuration: n/a (documentation only; no installs, no API calls).
- Results: Planning estimate for a faithful full GPT-4o run ≈ $350 ingestion (≈ $175 Batch) + ≈ $45 agent, vs. available credit $4.68 (OpenAI) + $3.78 (DeepSeek). Selected: primary ingestion gpt-4o-mini, GPT-4o on a 2-document calibration set, agent = local 7–8B model for development and DeepSeek API for pilot evaluation. Pilot = 10 stratified documents ≤ 40 pages.
- Problems: Cost figures are estimates from prompt sizes, not measurements; image tokenization for deepseek-flash is unknown. Lab GPU availability is unknown (to be asked by the user).
- Observations: The reproduced system is named LAD-RAG†; only relative comparisons with paper numbers are meaningful. Credit balances were reported by the user, not verified by me.
- Next step: CP-2.2 Dataset loader — awaiting explicit user approval.

## 2026-09-27 — CP-2.2 Dataset loader
- Date: 2026-09-27
- Checkpoint: CP-2.2
- Objective: Load MMLongBench-Doc into the CP-1.1 data models with explicit handling of the defects found in CP-2.1.
- Work performed:
  - User chose policies (D-012): IDs `mmlb-<index:04d>-<sha1[:8]>`; load all questions; drop out-of-range evidence pages and flag `invalid_evidence_pages`; flag `wrong_document` for the dr-vorapp questions; flagged questions excluded from the clean set.
  - Added `src/multimodal_document_extraction/datasets/mmlongbench_doc.py`: `load_mmlongbench_doc` (MANIFEST checksum check for samples.json, optional for PDFs; doc_type consistency check; page counts via PyMuPDF; safe list parsing; `validate_against` per question), `MMLongBenchDoc` (`clean_questions`, `flagged_questions`, `questions_for`, `question`), `load_pages` (1-based pages with PyMuPDF text), `KNOWN_WRONG_DOCUMENTS`.
  - Added `tests/test_mmlongbench_doc.py`: 9 tests on a synthetic fixture (PDFs generated with PyMuPDF) + 4 tests on the real download (skipped if absent), incl. an oracle-retrieval sanity check through `evaluate_retrieval`.
  - Updated MMLONGBENCH_DOC.md §8, REPRODUCTION_PROTOCOL.md §6, DECISIONS.md (D-012).
- Configuration: conda env `mmde`, Python 3.11.16, PyMuPDF 1.28.2; data per D-010.
- Results: Loader output matches CP-2.1: 1,082 questions, 135 documents, 6,529 pages, 1,082 unique IDs; 19 flagged questions (9 invalid pages, 10 wrong document; no overlap); clean set 1,063. Subsets: full 846 evidence / 236 no-evidence; clean 837 / 226. Oracle retrieval on the clean set gives PR 1.0, IPR 0.0, NoEvidenceCorrect 1.0 (sanity check of loader + metrics, not an experiment). `pytest -q`: 98 passed; ruff clean.
- Problems: One ruff TRY004 finding fixed (TypeError for non-list fields).
- Observations: Dropping invalid pages moves 8 questions into the no-evidence subset of the full set, so full-set no-evidence metrics are slightly contaminated; the clean set is the primary evaluation set (D-012). CP-2.1, CP-4.0 and CP-2.2 changes are not yet committed.
- Next step: CP-2.3 Pilot subset — awaiting explicit user approval.

## 2026-09-27 — CP-2.3 Pilot subset
- Date: 2026-09-27
- Checkpoint: CP-2.3
- Objective: Create a fixed, versioned, stratified pilot subset and a 2-document calibration subset per REPRODUCTION_PROTOCOL.md §5.
- Work performed:
  - Added `src/multimodal_document_extraction/datasets/subsets.py` (`Subset` JSON I/O + `select`; `DocumentStats`, `SelectionConstraints`, seeded `select_documents`, `select_calibration`).
  - Added `scripts/make_mmlongbench_pilot.py` (eligibility: all questions clean; image-only detection via empty PyMuPDF text on every page; PDF checksums verified; refuses to overwrite existing versions).
  - Generated `data/splits/mmlongbench-doc/pilot-v1.json` and `calib-v1.json` (committed directory).
  - Added `tests/test_subsets.py` (8 synthetic tests + 2 real-data tests incl. re-deriving the pilot from seed).
  - Recorded D-013; updated REPRODUCTION_PROTOCOL.md §5, data/README.md.
- Configuration: seed 0; constraints: 10 docs, ≤ 40 pages each, 200–250 pages, 70–90 questions, multi-page share ≥ 0.25, ≥ 5 no-evidence, ≥ 1 image-only, one per doc type. 128 of 135 documents are fully clean.
- Results: pilot-v1 accepted at attempt 2: 10 documents, all 7 doc types, 241 pages, 80 questions (28 multi-page = 35%, 14 no-evidence), 1 image-only PDF (`reportq32015-…_95.pdf`). calib-v1: `2305.14160v4.pdf` (16 p, 6 q) + `f8d3a162ab9507e021d83dd109118b60.pdf` (17 p, 10 q) = 33 pages, 16 questions, 7 multi-page. `pytest -q`: 106 passed; ruff clean.
- Problems: The first run failed at calibration: my code additionally required one image-only + one text-layer document, which is infeasible within 35 pages (the only image-only pilot PDF has 34 pages) and was not in the protocol. Removed that extra requirement (seed unchanged, pilot unchanged); nothing had been written before the fix.
- Observations: The calibration set contains no image-only PDF; image-only behaviour will be observed only on one pilot document. Pilot/calibration estimates for D-011 budget: ≈ 241 pages for substitute ingestion and 33 pages for GPT-4o calibration. Phase 2 complete. Changes since the last push (CP-2.1, CP-4.0, CP-2.2, CP-2.3) are not yet committed.
- Next step: CP-3.1 BM25 baseline — awaiting explicit user approval (needs a decision on the text source, given image-only PDFs).

## 2026-09-27 — CP-3.1 BM25 baseline
- Date: 2026-09-27
- Checkpoint: CP-3.1
- Objective: Implement a BM25 page retriever as the first conventional baseline.
- Work performed:
  - (Before starting: committed and pushed Phase 2 + CP-4.0 as `3453137`, per user request.)
  - User approved the recommended text source (D-014): PyMuPDF page text now (`bm25-pagetext`); paper-style element-summary BM25 after Phase 4.
  - Added dependency `bm25s>=0.2` (installed 0.3.11, MIT; pulls numpy 2.4.6).
  - Probed bm25s behaviour: empty pages and out-of-vocabulary queries score 0; an all-empty corpus raises `ValueError` in bm25s → handled explicitly.
  - Added `src/multimodal_document_extraction/retrieval/bm25.py` (`BM25PageRetriever`, `BM25Config`) and `tests/test_bm25.py`.
  - Fixed `Subset.save` to always write LF line endings (Git had warned about CRLF in the committed split files; content unchanged).
- Configuration: bm25s 0.3.11, lucene scoring, k1 = 1.5, b = 0.75, lowercase, English stopwords, no stemming; one index per document; all pages ranked; ties by page number.
- Results: `pytest -q`: 114 passed (8 new); ruff clean. Pilot smoke test: every pilot question receives a full ranking of its document's pages; the image-only document (`reportq32015-…_95.pdf`) yields an empty index (all-zero scores). No retrieval metrics computed yet (CP-3.2).
- Problems: none.
- Observations: On image-only documents the BM25 ranking degenerates to page order, so `bm25-pagetext` is an internal lower-bound baseline, not paper-comparable (D-014).
- Next step: CP-3.2 BM25 evaluation — awaiting explicit user approval.

## 2026-09-27 — CP-3.2 BM25 evaluation (EXP-0001)
- Date: 2026-09-27
- Checkpoint: CP-3.2
- Objective: Evaluate `bm25-pagetext` on pilot-v1 with PR/IPR across k, following EXPERIMENT_PROTOCOL.
- Work performed:
  - Added `evaluate_retrieval_at_k` and `first_perfect_recall_k` (evaluation/retrieval_metrics.py); `utils/run_recording.py` (git state + diff snapshot, run dir, JSON/JSONL writers, append-only results.csv with header/ID checks); `scripts/run_retrieval_eval.py`; config `experiments/ladrag/configs/EXP-0001-bm25-pagetext-pilot-v1.json`; tests `tests/test_run_recording.py`. Recorded D-015 (JSON configs, run layout); updated EXPERIMENT_PROTOCOL.md.
  - Ran EXP-0001 on the uncommitted working tree (CP-3.1/3.2 changes); `git_diff.patch` saved in the run dir. HEAD at run time: 3453137.
- Configuration: EXP-0001-bm25-pagetext-pilot-v1; MMLongBench-Doc github@d73f0dc0; subset pilot-v1 (10 docs, 241 pages), question_set clean (80 q: 66 evidence, 14 no-evidence); bm25s 0.3.11, lucene, k1 1.5, b 0.75, English stopwords, no stemming; k = 1..37; CPU only; source_label REPRO, reproduction_level substituted (page text instead of element summaries).
- Results [REPRO, bm25-pagetext, pilot-v1 — not paper-comparable] (from the script output; rows in experiments/ladrag/results/results.csv):
  | k | PR | IPR | single-page PR | multi-page PR |
  |---|---|---|---|---|
  | 1 | 0.167 | 0.621 | 0.289 | 0.000 |
  | 2 | 0.318 | 0.720 | 0.395 | 0.214 |
  | 3 | 0.348 | 0.783 | 0.447 | 0.214 |
  | 5 | 0.439 | 0.833 | 0.474 | 0.393 |
  | 10 | 0.561 | 0.898 | 0.658 | 0.429 |
  | 15 | 0.773 | 0.911 | 0.868 | 0.643 |
  | 20 | 0.848 | 0.922 | 0.921 | 0.750 |
  | 30 | 0.970 | 0.926 | 1.000 | 0.929 |
  - No-evidence subset (14 q): IPR 1.000 and NoEvidenceCorrect 0.000 at every k (by construction for a fixed-k retriever, D-009).
  - First k with PR = 1 (66 evidence q): mean 10.4, median 9, max 33; on average 44% of a document's pages must be retrieved to reach PR = 1.
  - Text-layer documents (58 evidence q): PR@1 0.190, PR@5 0.500, PR@10 0.586, median first-k 6.5. Image-only document (8 evidence q): PR@1 0.000, PR@5 0.000, PR@10 0.375, median first-k 21 (ranking = page order).
  - Latency: mean 0.11 ms per query (CPU); indexing times in run_meta.json.
- Problems: none in the run. The run was made on a dirty tree (documented by the saved patch).
- Observations: Multi-page questions are much harder for BM25 (PR@5 0.393 vs 0.474 single-page; PR@10 0.429 vs 0.658). Because pilot documents are short (≤ 40 pages), high PR at large k largely reflects retrieving most of the document (IPR ≈ 0.93 at k = 30); IPR must be read alongside PR. The LAD-RAG paper's BM25 baseline uses element summaries on the full dataset, so no numerical comparison with [PAPER] is made. Figure 3 of the paper is not transcribed (image only).
- Next step: CP-3.3 Dense retrieval — awaiting explicit user approval.

## 2026-09-27 — CP-3.3 Dense retrieval
- Date: 2026-09-27
- Checkpoint: CP-3.3
- Objective: Implement dense page retrieval with the paper's dense baseline models (E5-large-v2, BGE-large-en).
- Work performed:
  - (Before starting: committed and pushed CP-3.1/3.2 as `5766b59`, per user request.)
  - User chose chunk + max (MaxP) for long pages and the GPU install (D-016).
  - Installed torch 2.14.0+cu126 (CUDA index) and sentence-transformers 6.1.0 (transformers 5.17.0) into `mmde` via new optional extra `dense`; `pip check` clean. Downloaded and pinned intfloat/e5-large-v2 @ f169b11e and BAAI/bge-large-en @ abe7d9d8 (both MIT); verified prefixes on the official model cards and pooling (E5 mean, BGE CLS) from the loaded configs.
  - Added `src/multimodal_document_extraction/retrieval/dense.py` and `tests/test_dense.py`; updated README (dense install), ENVIRONMENT.md, DECISIONS.md (D-016).
  - GPU feasibility run on pilot-v1 documents (scratch script, no metrics).
- Configuration: max_seq_length 512, 64-token window overlap, cosine similarity on normalized embeddings, fp32, device cuda:0 (Quadro RTX 4000).
- Results: `pytest -q`: 129 passed (9 new, including a real E5 smoke test where evidence at the end of a ~1,500-token page ranks first); ruff clean. Pilot feasibility (both models): 241 pages → 244 chunks, 49 pages without text (34 from the image-only document + 15 image pages in other documents), indexing ≈ 12 s per model, ≈ 18 ms per query, peak VRAM 1.64 GiB; every question gets a full page ranking.
- Problems:
  - Two new tests failed initially because the fake 12-token model was used with the default 64-token overlap (the validation correctly rejected it); tests fixed. One ruff RUF046 fixed.
  - Twice, a PowerShell command whose inline text contained a Python object-removal keyword was blocked by the shell safety check (misread as a file deletion on drive D:); rewritten via files / rephrased. Nothing was deleted.
  - transformers prints "Token indices sequence length is longer than … (866 > 512)" when computing token offsets for a whole page before windowing; no model input exceeds 512 tokens.
- Observations: Only 3 pages in the pilot exceed one window, so MaxP rarely matters on pilot-v1; it will matter more on text-dense technical datasheets later. No retrieval metrics computed yet (CP-3.4).
- Next step: CP-3.4 Dense retrieval evaluation — awaiting explicit user approval.

## 2026-09-27 — CP-3.4 Dense retrieval evaluation (EXP-0002, EXP-0003, CMP-0001)
- Date: 2026-09-27
- Checkpoint: CP-3.4
- Objective: Evaluate the dense page-text baselines (E5-large-v2, BGE-large-en) with the same protocol as EXP-0001 and compare all three baselines.
- Work performed:
  - Extended `scripts/run_retrieval_eval.py` with method `dense-pagetext` (retriever factory; records torch / sentence-transformers / transformers versions and device).
  - Configs + runs: EXP-0002-dense-e5-pagetext-pilot-v1, EXP-0003-dense-bge-pagetext-pilot-v1 (dirty tree; git_diff.patch saved; HEAD 5766b59).
  - Added `scripts/compare_retrieval_runs.py` (paired bootstrap CIs, W/T/L, subgroups; D-017) and produced `experiments/ladrag/results/comparisons/CMP-0001-pagetext-baselines-pilot-v1.json`.
  - Checked an apparent coincidence (identical first-k W/T/L totals for E5 and BGE vs BM25): not a bug — 14 questions differ in category between E5 and BGE and the totals happen to cancel.
  - Measured how many evidence questions have a gold page without a text layer (scratch analysis from per_query files + PyMuPDF text).
- Configuration: pilot-v1, clean question set (80 q: 66 evidence, 14 no-evidence), k = 1..37; E5 @ f169b11e / BGE @ abe7d9d8, 512-token windows, 64 overlap, MaxP cosine, fp32 on cuda:0; bootstrap 10,000 resamples, seed 0.
- Results [REPRO, page-text baselines, pilot-v1 — not paper-comparable]:
  | Method | PR@1 | PR@3 | PR@5 | PR@10 | PR@20 | IPR@5 | median first-k | latency/query |
  |---|---|---|---|---|---|---|---|---|
  | bm25-pagetext (EXP-0001) | 0.167 | 0.348 | 0.439 | 0.561 | 0.848 | 0.833 | 9 | 0.11 ms |
  | dense-e5-large-v2-pagetext (EXP-0002) | 0.212 | 0.303 | 0.379 | 0.470 | 0.803 | 0.852 | 11 | 18.1 ms |
  | dense-bge-large-en-pagetext (EXP-0003) | 0.197 | 0.333 | 0.379 | 0.561 | 0.818 | 0.845 | 8.5 | 18.5 ms |
  - Paired vs BM25 (all 66 evidence q): E5 PR@5 −0.061, CI95 [−0.167, +0.045], W/T/L 4/54/8; PR@10 −0.091 [−0.182, +0.000]. BGE PR@5 −0.061 [−0.182, +0.061], W/T/L 6/50/10; PR@10 +0.000 [−0.106, +0.106]. All CIs include 0 → no clear difference among the three baselines on pilot-v1.
  - Multi-page questions (28): PR@10 BM25 0.429, E5 0.357, BGE 0.464; PR@1 = 0 for all.
  - No-evidence subset (14 q): IPR 1.0 and NoEvidenceCorrect 0 at every k for all methods (fixed-k retrievers).
  - 16 of 66 evidence questions (24%) have at least one gold page with no text layer (8 in the image-only document, 8 in text-layer documents): PR@5 = 0.000 for all three methods on them. On the other 50 questions: PR@5 BM25 0.580, E5 0.500, BGE 0.500; PR@10 0.680 / 0.560 / 0.680. 15 of the 26 questions with identical first-k across methods have such a textless gold page.
- Problems: none in the runs. HF Hub printed an unauthenticated-request warning (models were already cached; pinned revisions resolved).
- Observations: On this pilot, dense page-text retrieval does not clearly beat BM25; the sample is small (D-017). A recurring failure for all text-only baselines is evidence on pages without extractable text (charts, figures, scanned slides) — relevant context for LAD-RAG's LVLM ingestion and for the later technical-domain study, recorded as an observation only (no research direction implied). Phase 3 page-text baselines complete; paper-style element-summary baselines remain for after Phase 4 ingestion.
- Next step: CP-4.1 Paper implementation review — awaiting explicit user approval. Uncommitted: CP-3.3 and CP-3.4.

## 2026-09-27 — CP-4.1 Paper implementation review
- Date: 2026-09-27
- Checkpoint: CP-4.1
- Objective: Turn the paper into an implementable specification for LAD-RAG†, closing every unpublished detail with a documented choice; no code, no API spend.
- Work performed:
  - (Before starting: committed and pushed CP-3.3/3.4 as `5e22c37`, per user request.)
  - Rendered and inspected PDF pages 4, 7, 15, 16 (Figs. 2, 3, 5, 6, 7); Fig. 7 re-checked at 300 DPI after a first low-resolution reading (corrected LAD-RAG multi-page point from PR ≈ 0.77 to ≈ 0.75 before recording).
  - Transcribed the four App. H prompts word-exact with `scripts/transcribe_ladrag_prompts.py` (re-joins lines wrapped by LaTeX listings using the `,→` markers; per-block consistency check: 0 mismatches; identical output for thresholds 100–110; 115 produced a mismatch and was rejected). Saved to `src/multimodal_document_extraction/studies/ladrag/prompts/` with a README (provenance, sha256, fidelity limits, templating rules).
  - Wrote `docs/studies/ladrag/IMPLEMENTATION_SPEC.md`; added PAPER_NOTES §16; recorded D-018 (Proposed).
- Configuration: n/a.
- Results:
  - Figure-only facts: agent node IDs look like `page_22-obj_002` (Fig. 6); chart filter `node.get('type') == 'figure'` (Fig. 5); Fig. 3 plots PR (y) vs IPR (x); [PAPER-FIG, approximate] LAD-RAG on MMLongBench-Doc ≈ PR 0.83 at IPR ≈ 0.79 (all questions), ≈ PR 0.75 at IPR ≈ 0.73 (multi-page, Fig. 7); baseline k labels average 22 pages, matching the text.
  - Spec: pipeline A–D per page (node extraction, section_queue update, deterministic intra-page relations, graph construction), Louvain after the last page, E5 neural index, Fig. 12 agent with sandboxed tools; 20 reconstruction items (R1–R20); all 12 open questions from PAPER_NOTES §15 resolved or explicitly deferred (Table 1 score formula remains unknown).
- Problems: Prompt indentation/blank lines are not recoverable from the PDF (word-exact only). The "> 90% PR on average" claim is an average over four datasets; on MMLongBench alone the plotted LAD-RAG PR is ≈ 0.83.
- Observations: Our target operating point for Study 01 is therefore PR ≈ 0.83 at IPR ≈ 0.79 (paper, full MMLongBench, GPT-4o) — only relative trends will be comparable (D-011). D-018 needs user approval before implementation starts.
- Next step: user review of D-018 / IMPLEMENTATION_SPEC; then CP-4.2 Document graph schema — awaiting explicit approval.

## 2026-09-27 — CP-4.2 Document graph schema
- Date: 2026-09-27
- Checkpoint: CP-4.2
- Objective: Implement the LAD-RAG† graph data structures and the prompt renderers specified in IMPLEMENTATION_SPEC.md, without any API use.
- Work performed:
  - (Before starting: committed and pushed CP-4.1 as `dc98dec`, per user request.) User approved D-018 / the implementation spec without changes → status Accepted.
  - Added `src/multimodal_document_extraction/studies/ladrag/schema.py`: `make_node_id` / `parse_node_id` / `page_prefix`, `assign_ids` (keeps valid claimed IDs, deterministically reassigns missing, malformed, off-page or duplicate ones; R1), `normalize_object` (Fig. 9 fields; type lower-cased; non-text content serialized as JSON text), `initial_memory` (R6), `DocumentGraph` (validated nodes with plain-dict attributes as used in the paper's Fig. 5 filter; undirected edges merging relation `types` and `sources` with explicit rejection reasons — unknown endpoint, self-loop, missing type, non-object (R7); community storage/lookup (R8); deterministic node-link JSON `ladrag-graph/1`; stats).
  - Added `src/multimodal_document_extraction/studies/ladrag/prompts/__init__.py`: renderers for Figs. 9–12 (Figs. 9/12 via `str.format`; Figs. 10/11 fill verbatim f-string placeholders and unescape only literal template text, so inserted JSON/page text is never altered; `json.dumps(..., indent=2)` with default ensure_ascii as in the printed code).
  - Made `networkx>=3.2` an explicit dependency (previously only transitive via torch); declared prompt files as package data. Tests: `tests/test_ladrag_schema.py`, `tests/test_ladrag_prompts.py` (template sha256 pinned to the CP-4.1 transcription).
- Configuration: conda env `mmde`, Python 3.11.16, networkx 3.6.1. No API calls, no data written.
- Results: 23 new tests passed on the first run; full suite 152 passed; ruff clean; `pip check` clean. A Louvain run from networkx on a toy graph is accepted by `set_communities`.
- Problems: none.
- Observations: The Fig. 10 template renders `...page_{ page number}...` literally after unescaping, exactly as the paper's f-string would. Node IDs follow the paper's figure (`page_22-obj_002`), while the Fig. 12 prompt text still describes a folder/document-prefixed format (kept verbatim; noted in D-018 R1).
- Next step: CP-4.3 Graph construction (ingestion pipeline with mocked LLM tests, then the first paid calls: calibration on calib-v1 with GPT-4o and gpt-4o-mini) — awaiting explicit user approval; will need an OpenAI API key in `.env`.

## 2026-09-27 — CP-4.1A Resource-Constrained Phase 4 Revision
- Date: 2026-09-27
- Checkpoint: CP-4.1A (new documentation-only checkpoint requested by the user, between CP-4.1 and CP-4.2)
- Objective: Adapt Phase 4 to the resources of an unfunded Master's project: pipeline completable with $0 API spend; APIs optional validation only.
- Work performed:
  - Rewrote `docs/studies/ladrag/IMPLEMENTATION_SPEC.md` (status Proposed): "Local-first, API-last" principle; labels [PAPER-EXACT] / [RECONSTRUCTED] / [SUBSTITUTED] / [OPTIONAL-REFERENCE]; vendor-neutral VisionModel/AgentModel interfaces with mock/scripted implementations first; page-level checkpoint/resume; all paper-unspecified parameters config-driven (defaults explicitly ours: semantic_search.top_k 10, Louvain resolution 1.0 / seed 0, agent max_output_tokens 1024, context budget 100k, observation_max_nodes 50, …); substitutions S1–S4; revised Phase 4 plan; research-interpretation note. All CP-4.1 technical findings kept.
  - Rewrote `docs/studies/ladrag/REPRODUCTION_PROTOCOL.md` (CP-4.0 version preserved in git history, commit 3453137): resource-constrained partial reproduction position, local-first principle, updated resources, component levels with new labels, new ingestion priority (mock → local VLM → local calibration → local pilot; API VLM only as optional reference on 3–5 pages), 10 hard API-spending rules (DeepSeek cumulative < USD 5, OpenAI optional, no automatic runs, approval per paid experiment, abort before budget, recheck prices), reporting with component lists, internal comparisons as primary.
  - `docs/CHECKPOINTS.md`: added CP-4.1A; replaced former CP-4.3 / 4.5 / 4.6 with CP-4.3A–D, 4.4, 4.5, 4.6A–C, optional 4.7 (none of the replaced ones had started).
  - `docs/DECISIONS.md`: D-018 revised in place and returned to **Proposed**; new D-019 (resource strategy + API policy) **Proposed**; D-011 marked pending supersession by D-019.
- Configuration: n/a (no code changes, no installs, no downloads, no API calls, no spending).
- Results: Revised Phase 4 plan in which every checkpoint has a $0 acceptance path; paid runs limited to optional CP-4.6C (20 questions, DeepSeek) and an optional reference VLM comparison.
- Problems / status corrections:
  - **D-018 status reversal:** in the previous turn the user's message "lanjut 4.2 masih tidak perlu dirubah untuk 4.2" was recorded as approval of D-018 (status set to Accepted) and CP-4.2 was implemented (schema.py, prompt renderers, 23 tests; full suite 152 passed; uncommitted). The user's CP-4.1A instruction states D-018 was not accepted and CP-4.2 had not started. D-018 is therefore back to Proposed; the historical CP-4.2 log entry above is left unchanged (append-only).
  - **CP-4.2 on hold:** the CP-4.2 code remains in the working tree untouched and uncommitted; its scope matches the revised CP-4.2 definition. Checkpoint status set to [!] (on hold) until the user decides whether to keep, revise or redo it.
- Observations: The revised plan moves the first real-model work to local feasibility tests (CP-4.3B) on 3–5 pages; the model choice is deliberately deferred until the current small-VLM ecosystem has been checked.
- Next step: user decisions — approve D-018 and D-019 (or request changes), and decide the fate of the on-hold CP-4.2 work; no further checkpoint starts before that.

## 2026-09-27 — CP-4.1A decisions finalized (user approval)
- Date: 2026-09-27
- Checkpoint: CP-4.1A (finalization) → start of CP-4.2 review
- Objective: Record the user's explicit decisions on the CP-4.1A proposals.
- Work performed: Updated DECISIONS.md (D-018 Proposed → Accepted; D-019 Proposed → Accepted; D-011 annotated with exactly which parts are superseded and which remain), status headers of IMPLEMENTATION_SPEC.md and REPRODUCTION_PROTOCOL.md, CHECKPOINTS.md.
- Configuration: n/a.
- Results:
  - User approved the revised Phase 4 plan, D-018 (revised, resource-constrained form) and D-019.
  - D-019 supersedes only D-011's model/resource/budget parts (GPT-4o calibration, gpt-4o-mini primary ingestion and CP-4.0 tier priority, default agent model plan, CP-4.0 budget plan and stop rule, GPT-4o upgrade path). Still valid from D-011: LAD-RAG† naming, explicit substitution reporting, Study 01 = MMLongBench-Doc, component levels, pilot/calibration definitions, PAPER vs REPRO separation, deferred QA / ColPali / RAPTOR, other datasets not reproduced.
  - User decided to KEEP the existing CP-4.2 implementation, to be reviewed against the final spec before CP-4.2 is marked complete; git strategy: one commit for CP-4.1A documentation, a second for CP-4.2.
- Problems: none.
- Observations: The approval is explicit, unlike the earlier inferred one that was withdrawn in CP-4.1A.
- Next step: CP-4.2 review against the accepted spec (add graph metadata object; no ingestion logic).

## 2026-09-27 — CP-4.2 review and completion
- Date: 2026-09-27
- Checkpoint: CP-4.2 (review of the implementation kept after CP-4.1A; see the earlier CP-4.2 entry, which is left unchanged)
- Objective: Verify the existing CP-4.2 code against the accepted D-018/D-019 spec, fix only conflicting parts, add the graph-metadata object, and complete CP-4.2.
- Work performed:
  - Committed the CP-4.1A documentation separately first (commit 1).
  - Reviewed `studies/ladrag/schema.py` and `studies/ladrag/prompts/__init__.py` against 11 review points. Passing unchanged: 1-based pages; `page_{n}-obj_{k:03d}` IDs; location under `studies.ladrag`; duplicate node detection; prompt rendering without any model/API call (imports: stdlib + networkx only, verified by grep); no ingestion logic.
  - Fixed in `schema.py` (targeted changes, no rebuild): unknown extracted keys are preserved in `extra_fields` and the model's ID in `claimed_object_id` (previously dropped); strict `from_dict` (unknown/duplicate edges, unknown attributes, doc_id mismatch now rejected — previously an edge to an unknown node silently created that node); `validate()` for all invariants; byte-deterministic `to_json` / `save` / `load`; `GraphMetadata`; `validate_memory` + `MEMORY_KEYS`; `DEFAULT_SECTION_TYPES` (R3 config default instead of a hard-coded constant); `order_on_page` and page ≤ num_pages validation; ID helpers reject bools/floats and page 0; paper-exact vs reconstructed node-field groups labelled; failed `set_communities` calls no longer leave partial assignments.
  - Rewrote `tests/test_ladrag_schema.py` for the new constructor and added tests for each review point (round-trip byte identity, insertion-order independence, 10 invalid-graph cases, memory validation, metadata validation). Prompt tests unchanged.
  - Documented the graph file format in IMPLEMENTATION_SPEC §4.7.
- Configuration: conda env `mmde`, Python 3.11.16, networkx 3.6.1. No model inference, downloads or API calls.
- Results: CP-4.2 tests 39 passed (previously 23); full suite 168 passed; `ruff check` and `ruff format --check` clean.
- Problems: One ruff TRY004 fixed. Commit 1 initially failed because PowerShell 5.1 split a commit message containing double quotes; re-done with a message file (no partial commit).
- Observations / deviations from the spec: (1) `claimed_object_id` and `extra_fields` are additions to the node attributes listed in the spec (now documented there); (2) `content`, `summary`, `title_or_heading` are coerced to text; (3) community IDs are numbered by the smallest member ID (deterministic). The Fig. 9 field `object_id` is stored with its canonical value (R1).
- Next step: CP-4.3A Ingestion framework (mock/scripted models only) — awaiting explicit user approval.

## 2026-09-27 — CP-4.3A Ingestion framework
- Date: 2026-09-27
- Checkpoint: CP-4.3A
- Objective: Build the complete LAD-RAG† ingestion orchestration (PDF → graph) without a real VLM, with caching, logging and page-level resume.
- Work performed:
  - (Before starting: pushed CP-4.1A `4ab890c` and CP-4.2 `10b0212`; the first push attempt failed with a connection reset, the retry succeeded.)
  - Added `src/multimodal_document_extraction/studies/ladrag/models.py`: `VisionModel` protocol with `GenerationRequest` (task, prompt, images, params) / `ModelReply`; `ScriptedVisionModel` (replies from a function); `MockVisionModel` (deterministic, schema-valid replies derived from the rendered Fig. 9–11 prompts: 3 nodes/page, section-queue append, is_part_of_section + continues relations).
  - Added `src/multimodal_document_extraction/utils/model_cache.py`: content-addressed permanent cache (sha256 of model id, task, prompt, image hashes, params; atomic writes).
  - Added `src/multimodal_document_extraction/studies/ladrag/ingestion.py`: `IngestionConfig` (paper-exact render DPI/temperature/tokens/Louvain; reconstruction defaults), `render_page` (1-based, optional max side), `parse_json_reply` (fence/prose tolerant; skips whole values of the wrong type), `ModelClient` (cached, logged calls), `DocumentIngestor` (steps A–D, ID normalization, relation validation with reasons, memory handling, Louvain, graph.json, summary.json, atomic page records, fingerprinted resume, restart).
  - Added `tests/test_ladrag_ingestion.py` (20 tests); documented implementation details in IMPLEMENTATION_SPEC §4.8.
- Configuration: conda env `mmde`; PyMuPDF 1.28.2, networkx 3.6.1. No real model, no downloads, no API calls; synthetic PDFs generated in tests only.
- Results: 20/20 ingestion tests pass; full suite 188 passed; ruff clean. Synthetic 3-page PDF with MockVisionModel → valid graph (9 nodes, 11 edges: next_on_page 6, is_part_of_section 6, continues 2), 9 model calls (A, B, D per page), graph.json reload byte-identical. Cache: second run 0 model calls, identical graph. Crash on page 3 → pages 1–2 persisted; resume made 3 calls (page 3 only) and produced a graph identical to an uninterrupted run.
- Problems: One test initially failed because my test helper inferred the page from the first "page_N" in any prompt (Fig. 10/11 prompts contain earlier pages' IDs in memory); the helper now reads the Fig. 9 prefix — the ingestion code was correct. One ruff RUF007 fixed (itertools.pairwise). Also fixed during development before the tests ran: `restart=True` previously only cleared records on a fingerprint mismatch; `parse_json_reply` could return an object nested inside a list when an object was expected.
- Observations: The framework never needs a real model to be tested; CP-4.3B only has to provide a `VisionModel` implementation. Memory size per page is recorded (`memory_chars`) for the CP-4.3C growth analysis.
- Next step: CP-4.3B Local VLM feasibility — awaiting explicit user approval (includes an ecosystem check before any model download).

## 2026-09-28 — CP-4.3B Local VLM feasibility
- Date: 2026-09-27 (start) – 2026-09-28 (end)
- Checkpoint: CP-4.3B
- Objective: Determine whether a lightweight local VLM can run LAD-RAG† ingestion (Figs. 9–11) on the 8 GB Quadro RTX 4000; honest verdict; no API.
- Work performed:
  - (Before starting: committed and pushed CP-4.3A as `65ff534`.)
  - Ecosystem check (HF model API/cards, web overviews) documented in `docs/studies/ladrag/LOCAL_VLM_FEASIBILITY.md` before any download: Qwen3.5-2B/4B, Qwen3-VL-2B/4B, MiniCPM-V-4, Gemma-3-4B (gated), Qwen3.5-0.8B; Turing → fp16; 4B only quantized.
  - User approved downloading both 2B candidates; I then found Pillow and torchvision missing (I had wrongly said no new packages were needed) and asked; user approved installing both (torchvision 0.29.0+cu126 matched to torch 2.14.0; pillow 12.3.0; optional extra `vlm`). Downloads pinned: Qwen3.5-2B @ 15852e8c (4.26 GB), Qwen3-VL-2B-Instruct @ 89644892 (3.97 GB); HF connections were unstable (resets/timeouts), retries succeeded.
  - Added `studies/ladrag/local_vlm.py` (`TransformersVisionModel`, fp16, greedy, thinking disabled for Qwen3.5), `scripts/ladrag_vlm_feasibility.py`, `tests/test_ladrag_local_vlm.py`.
  - Smoke tests (1 Fig. 9 call): Qwen3.5-2B 20.5 tok/s, 4.42 GiB; Qwen3-VL-2B 25.2 tok/s, 4.41 GiB.
  - Full run on 5 pages (2305.14160v4 p3–4 text+chart pair, p7 table; reportq32015 p10 chart slide without text layer; Campaign_038 p9 brochure). A first background launch was stopped (tool timeout risk) and relaunched as a detached process.
  - The first run exposed parsing problems in my framework; fixed and tested (R17b container normalization, R17c column-0 parsing + lenient escapes, R21 skip Fig. 11 without nodes; record version 3; 11 new ingestion tests). While fixing I introduced and then caught a bug (the first R17b parser salvaged a nested object from a truncated reply); fixed before any results were used. The old-parser Qwen3-VL run was stopped and both models re-run with `--restart` (cached replies reused).
  - Manual inspection against rendered pages and the PDF text layer.
- Configuration: fp16, greedy, max_new_tokens 8192, images ≤ 1280 px, PyMuPDF 300 DPI; transformers 5.17.0, torch 2.14.0+cu126; cache `data/processed/ladrag/llm_cache`. API cost $0.
- Results (final re-run; reports `experiments/ladrag/results/feasibility/FEAS-qwen3.5-2b.json`, `FEAS-qwen3-vl-2b.json`):
  - Qwen3.5-2B: 5/5 pages with nodes (15, 2, 5, 1, 8); node-extraction JSON valid on 5/5 (one repair); graph construction valid 5/5; peak 4.74 GiB allocated; model time per page 69–554 s (mean ≈ 240 s); 1 runaway (8192-token) call. Text coverage 0.78–1.00. Table: 59/59 extracted numbers present in the PDF, 48/53 PDF numbers recovered. Chart slide: all 8 bar values correct. Dense academic p4: Figure 3 omitted, Figure 4 values hallucinated.
  - Qwen3-VL-2B: 3/5 pages with nodes; 7/11 heavy calls ran into repeated newlines until 8192 tokens; table and chart slide empty; graph construction failed on both academic pages; reserved VRAM 7.75 GiB; mean ≈ 585 s/page.
  - Verdict: Qwen3.5-2B feasible with limitations (proposed for CP-4.3C); Qwen3-VL-2B not feasible. Recorded as D-020 (Proposed).
- Problems: see Work performed (dependency misstatement, network instability, parser issues and my intermediate bug, old run discarded). Qwen3.5 fast kernels (flash-linear-attention, causal_conv1d) unavailable → slower reference implementation.
- Observations: Local ingestion is feasible at ≈ 4 min/page (pilot-v1 ≈ 16 h). The main quality risk for LAD-RAG† is figure omission / chart-value hallucination on dense academic pages; runaway repetition is the main latency risk. Recorded as observations only.
- Next step: user decisions on D-020 and on CP-4.3C options (repetition mitigation, image resolution, 20–30 page sample) — CP-4.3C not started.

## 2026-09-28 — CP-4.3C Local ingestion calibration
- Date: 2026-09-28
- Checkpoint: CP-4.3C
- Objective: Calibrate local ingestion (Qwen3.5-2B) on ~27 pages: stability, JSON failure rate, runaways, memory growth, cross-page edges, latency, VRAM, total time, resume, determinism; 1280 vs 1600 px.
- Work performed: Pushed CP-4.3B (`eb4b315`). User approved D-020 and chose: measure runaways only; 1280 main + 1600 comparison. Added `DocumentIngestor.extract_nodes` (+ test), `scripts/ladrag_ingestion_calibration.py` (+ `--mock` dry run, used before the real run), plans CAL-0001/CAL-0002. Ran CAL-0001 (27 contiguous pages, 5 documents, full pipeline) with a deliberate kill after page 3 and restart; then CAL-0002 (7 pages, step A, 1600 px). Manual visual checks (mi_phone p4, 2305 p4, 2305 p8). Report: docs/studies/ladrag/INGESTION_CALIBRATION.md.
- Configuration: Qwen3.5-2B @ 15852e8c fp16 greedy, max tokens 8192, 1280 px (CAL-0001) / 1600 px (CAL-0002); $0 API.
- Results: CAL-0001: 27/27 pages with nodes (268 nodes), 0 unrecoverable JSON, 6 pages repaired, 11 container normalizations; 6/78 runaway calls (8.3 % of first attempts); mean 312 s/page (max 920 s); wall 1.9 h; peak 5.62 GiB allocated / 7.62 GiB reserved; text coverage mean 0.87; 44 cross-page relations accepted, 6 rejected; memory grew to 12.8k chars on the academic paper. Resume verified (pages 1–3 untouched, continued at page 4). Determinism 2/2 identical. CAL-0002 vs 1280: nodes 35→42, figure nodes 3→6, text coverage 0.71→0.83, heatmap values read (visually checked), +21 % time; grouped-bar values still mis-bound.
- Problems: Monitor/scheduler temporarily unavailable (classifier errors) — run unaffected. "Numbers in PDF text" metric is only a lower bound for raster figures (documented).
- Observations: Pilot-v1 estimate ≈ 21 h at 1280 px, ≈ 23–25 h at 1600 px; VRAM close to the limit in the full pipeline.
- Next step: user decisions for CP-4.3D (resolution, runaway mitigation, OOM handling); changes uncommitted.

## 2026-09-28 — CP-4.3C completion: relation audit and timing clarification (analysis only)
- Date: 2026-09-28
- Checkpoint: CP-4.3C (analysis-only completion requested by the user; no new VLM inference, no API, no pilot ingestion)
- Objective: (1) small diagnostic audit of accepted cross-page relations of CAL-0001; (2) clarify the latency fields of the calibration reports.
- Work performed: Added `scripts/ladrag_relation_audit_sample.py` (seed 0; all `references`/`is_part_of_section`, 12 of 37 `continues` round-robin over documents) → 19 of 44 relations in `experiments/ladrag/results/calibration/CAL-0001-qwen3.5-2b-1280-relation-audit-sample.json`. Judged each manually from both nodes, all nodes of both pages and the PDF text layer; judgements and reasons stored in that file. Renamed timing fields in `scripts/ladrag_ingestion_calibration.py` (`model_seconds_all` → `est_no_cache_model_seconds`, `model_seconds_uncached` → `model_seconds_this_run`, aggregate renamed accordingly + `cached_calls`, `model_seconds_this_run_total`, `wall_seconds_scope`); verified with `--mock` dry runs of both plans and ruff. Committed reports CAL-0001/0002 left unchanged (old names; mapping documented). INGESTION_CALIBRATION.md: §2 table corrected, new §2.1 (timing) and §3A (audit), conclusion 6.
- Configuration: no model runs; read-only analysis of existing page records, reports and PDFs.
- Results: Audit (sample only, n = 19): correct 1, plausible 5, uncertain 0, incorrect 13, hallucinated 0 (`continues` 1/1/0/10/0, `references` 0/4/0/2/0, `is_part_of_section` 0/0/0/1/0). Full-set structure: 21 of 37 `continues` point backwards; one f8d3 p1 paragraph receives 11 links; the 6 `references` are the 2 × 3 product of two p4 and three p1 nodes. Timing CAL-0001: estimated no-cache model time 8,436 s (312 s/page) = 7,580 s actually spent + 856 s reused latency of 6 cached calls; report `wall_seconds` 6,770 s covers only the second invocation; total wall ≈ 2 h 10 min. CAL-0002: no cache hits. Pilot projection (≈ 21 h at 1280 px) unchanged, since it is based on the no-cache estimate.
- Problems: My earlier report text called the 312 s/page "model time" and 1.9 h "wall time (27 pages incl. restart)"; both were imprecise (corrected). The audit is a single-annotator judgement on a non-proportional sample.
- Observations: Cross-page relations are structurally valid but semantically weak with the 2B model; retrieval experiments should compare graph expansion with and without them.
- Next step: user review; CP-4.3D decisions (resolution, runaway mitigation, OOM handling) not started; changes uncommitted.

## 2026-09-28 — CP-4.3D planning: ground-truth evaluation strategy and Stage-1 design (analysis only)
- Date: 2026-09-28
- Checkpoint: CP-4.3D (planning part only; no ingestion)
- Objective: Per user instruction, switch the primary evaluation of generated graphs to downstream page-level retrieval against the official MMLongBench-Doc `evidence_pages`; design Stage 1 on the five CAL-0001 documents.
- Work performed: Added `scripts/ladrag_stage1_design_stats.py` (read-only) → `experiments/ladrag/results/design/retrieval-eval-v1-stage1-stats.json`. Wrote `docs/studies/ladrag/RETRIEVAL_EVAL_V1.md` (subset, full-document requirement and cache reuse, conditions A/B/C/D, budget control, metrics, reachability diagnostic, time estimate, informativeness, dependencies). Recorded D-021 (Proposed). Relabelled the CP-4.3C relation audit as an AI-assisted qualitative diagnostic audit in INGESTION_CALIBRATION.md, CHECKPOINTS.md and the audit JSON (`audit.status`); this corrects the framing of the previous log entry, whose counts stay as recorded. CHECKPOINTS: CP-4.3D revised (staged), CP-4.5A proposed. pilot-v1 unchanged.
- Configuration: no model runs, no API, no ingestion.
- Results (dataset statistics, not experiment results): retrieval-eval-v1 Stage 1 = 5 documents, 132 pages (27 ingested in CAL-0001, 105 not yet), 43 questions: 35 evidence (17 single-page, 18 multi-page, 13 of them adjacent-only), 8 no-evidence; all 35 evidence questions have valid gold pages; gold-page counts 1:17, 2:14, 3:1, 4:2, 6:1; sources (multi-label) text 18, figure 12, chart 10, layout 8, table 3. Estimated Stage-1 ingestion ≈ 6 h (range 6–9 h) at CAL-0001 settings, reusing 14 fully cached prefix pages and step-A replies of 13 mid-document pages.
- Problems: One no-evidence question (2305) has an empty gold list but answer format `Str` / source `Table`; kept as no-evidence per D-008, noted.
- Observations: 13 of 18 multi-page questions have only adjacent gold pages, so a p ± 1 layout control (condition D) is required before crediting the graph. Intra-page-only expansion (C) equals semantic-only (A) at page level by construction; the cross-page effect is B vs C/D. Stage 1 is a go/no-go diagnostic, underpowered for confirmatory claims.
- Next step: user approval of D-021 and of Stage-1 settings (resolution, runaway handling, OOM handling); then Stage-1 ingestion. CP-4.4/CP-4.5 not started.

## 2026-09-29 — CP-4.3D Stage 1: full-document graph construction (ING-0001)
- Date: 2026-09-28 18:37 → 2026-09-29 04:12
- Checkpoint: CP-4.3D (Stage 1 only)
- Objective: Build the evaluation graphs of retrieval-eval-v1: full-document ingestion of the five CAL-0001 documents (132 pages) with the approved settings; retrieval-eval-v1 protocol frozen beforehand.
- Work performed: User accepted D-021 and the Stage-1 design; RETRIEVAL_EVAL_V1.md frozen (B neighbour order seed rank → page → node ID; D order p − 1, p + 1; exploratory statistics). Implemented R22 OOM policy (`ResourceExhaustedError` in models.py; CUDA OOM conversion with memory statistics and cache release in local_vlm.py; one same-configuration retry on a graph copy, then persisted `status = resource_failure`, listed in summary/progress/graph metadata; record version 4; 3 tests). Extended `scripts/ladrag_ingestion_calibration.py` (plan `run_id`, `records_root`, `report_dir`, `"pages": "all"`, run.log, page status counts); plan ING-0001; mock dry run. First launch stopped after 3 cached pages because of a found reproducibility bug (key-sorted page records → resumed runs render memory in a different key order than uninterrupted runs; CAL-0001 2305 p4–8 were produced after such a resume) → fixed as R23 (records keep key order; test that crash + resume sends exactly the uninterrupted prompts, verified to fail without the fix); restarted with --restart. Added `scripts/ladrag_stage1_graph_check.py`. Report: docs/studies/ladrag/PILOT_INGESTION.md.
- Configuration: Qwen/Qwen3.5-2B @ 15852e8c fp16 greedy, thinking off, 1280 px, 8192 tokens, R22, R23; $0 API. Git commit of the run: working tree on top of 2c81370 (uncommitted changes, recorded in the report's git_commit field).
- Results: 132/132 pages completed; 0 resource failures; 129 pages with nodes, 3 without (JSON failure of node extraction: 2305 p11, p14, reportq3 p32; none gold); graph-construction JSON failure on 5 pages (2305 p4, p9, f8d3 p11, reportq3 p6, Campaign p25); 23 pages repaired; 846 nodes, 1,593 edges, 714 cross-page edges (92 adjacent, 622 non-adjacent), 206 rejected relations; runaways 30/362 calls, 6.5 % of first attempts, all 8 JSON failures = runaway + runaway repair; 49/362 calls from cache; wall 9.57 h; model time 34,444 s (est. no-cache 40,422 s); peak 5.82 GiB allocated / 8.06 GiB reserved; memory up to 11.8k characters (mi_phone). All 35 evidence questions have every gold page represented by ≥ 1 node. Tests 204 passed; ruff clean.
- Problems: R23 bug (fixed before the evaluation run; CAL-0001 calibration pages affected, not used for evaluation). Wall time above the 6–9 h estimate. Reserved VRAM reached 8.06 GiB (no OOM). Gold page 2305 p4 degraded (2 nodes, no Fig. 11 output; 3 questions) and Campaign p25 without Fig. 11 output (1 question) — kept as method outcomes.
- Observations: Most cross-page edges link non-adjacent pages (mostly is_part_of_section to earlier section headers). No retrieval evaluation was run.
- Next step: user review of Stage 1; CP-4.4 / CP-4.5 / CP-4.5A and Stage 2 not started; changes uncommitted.

## 2026-09-29 — CP-4.4 Symbolic graph retrieval utilities
- Date: 2026-09-29
- Checkpoint: CP-4.4 (user approved CP-4.3D Stage 1; Stage 2 not started)
- Objective: Deterministic, safe, CPU-only graph utilities for retrieval-eval-v1 graph expansion and the later agent's symbolic tools; no model, no API, no retrieval numbers.
- Work performed: Provenance clarifications first — PILOT_INGESTION.md: ING-0001 executed from an uncommitted working tree based on 2c81370, implementation (R22, R23) committed afterwards as 9522b2b, no rerun (corrects the impression that could arise from the 2026-09-29 Stage-1 entry); INGESTION_CALIBRATION.md §3A: the CP-4.3C audit uses calibration data predating R23, qualitative/debugging only. Added `studies/ladrag/graph_retrieval.py` (GraphIndex: node→page validated against the ID, ordered unique pages, neighbours with scope all/cross-page/intra-page + relation-type/origin filters, edges(scope), ordered one-hop expansion R24, get_community_for_node) and `studies/ladrag/graph_query.py` (R13 sandbox: static AST allow-list, read-only NetworkX-like facade, restricted builtins with numbers-only sum, trace-based 10 s timeout, result cap). 52 unit tests on synthetic graphs. `scripts/ladrag_graph_utilities_smoke.py` → `experiments/ladrag/results/ingestion/ING-0001-stage1-qwen3.5-2b-1280-graph-utilities-smoke.json`. Docs: IMPLEMENTATION_SPEC §5 (CP-4.4 implementation, R24), RETRIEVAL_EVAL_V1.md implementation note (no results seen).
- Configuration: CPU only; Stage-1 graphs read-only; no gold evidence used.
- Results: Tests 256 passed (52 new); ruff clean. Smoke test on the five Stage-1 graphs: all load and validate; degree sums = 2 × edges per scope; cross + intra = all; cross-page edges by utility = graph-check counts (49, 271, 113, 106, 175; total 714); expansion deterministic and duplicate-free; communities cover all nodes; Fig. 5 filter via sandbox returns exactly the figure nodes (0–35 per document).
- Problems: None blocking. Documented limits: the sandbox exposes a NetworkX-like subset rather than the raw NetworkX object (agent code using other NetworkX APIs gets an ERROR); in-process timeout cannot interrupt a single C-level operation (mitigated by static rules).
- Observations: Intra-page count includes Fig. 11 edges between nodes of the same page (cross-page status comes from endpoint pages only).
- Next step: user review; CP-4.5 not started.
