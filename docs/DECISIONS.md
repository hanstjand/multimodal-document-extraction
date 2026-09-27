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

## Open (to be decided in later checkpoints)
- Python version and environment manager (CP-0.3). Paper used Python 3.10.12 / PyTorch 2.7.0+cu126 / vLLM 0.9.2.
- PR/IPR edge cases: questions with no gold evidence pages (unanswerable); empty retrievals (CP-1.2/1.3).
- LVLM / LLM used for ingestion and agent (GPT-4o as in paper vs. open/local model) — cost and hardware dependent (Phase 4).
- Embedding model for the LAD-RAG neural index (not specified in the paper) (Phase 4).
