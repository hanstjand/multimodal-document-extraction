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
