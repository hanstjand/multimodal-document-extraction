# Multimodal Document Extraction

Master's research repository (NTUST) on multimodal document extraction:
visually-rich document understanding, document retrieval, multi-page reasoning,
and document information extraction.

## Approach

The research starts from existing methods and lets observed failures define the problem:

```
existing method reproduction → original-domain evaluation → technical-domain evaluation
→ performance degradation analysis → failure analysis → targeted literature review
→ candidate improvements → proposed method evaluation
```

The final contribution is **not yet decided**.

## Studies

| Study | Topic | Status |
|---|---|---|
| Study 01 | Reproduction of **LAD-RAG** (Sourati et al., ACL 2026, pp. 15945–15968) on MMLongBench-Doc | planned (Phase 4) |
| Study 02 | Evaluation of the reproduced pipeline on technical documents / datasheets | planned (Phase 5) |

## Status and documentation

Development proceeds checkpoint-by-checkpoint.

| File | Purpose |
|---|---|
| `CLAUDE.md` | Working rules (read first) |
| `docs/PROJECT_CONTEXT.md` | Research scope and current study |
| `docs/CHECKPOINTS.md` | Roadmap and current status |
| `docs/RESEARCH_LOG.md` | Append-only log of work performed |
| `docs/DECISIONS.md` | Architecture / methodology decisions |
| `docs/RESEARCH_PLAN.md` | Phased research plan |
| `docs/EXPERIMENT_PROTOCOL.md` | What every experiment must record |
| `docs/ENVIRONMENT.md` | Hardware / software environment |
| `docs/studies/<study>/` | Study-specific notes (e.g. `ladrag/PAPER_NOTES.md`) |

## Layout

```
data/                    raw / processed / technical data (not committed; see data/README.md)
docs/                    project documentation; docs/studies/<study>/ for study notes
experiments/<study>/     configs, runs (not committed), results (machine-readable)
notebooks/               exploratory notebooks
papers/<study>/          reference papers (PDFs not committed; see papers/README.md)
scripts/                 CLI entry points
src/multimodal_document_extraction/
    datasets/ ingestion/ retrieval/ graph/ evaluation/ agents/ utils/   shared components
    studies/<study>/                                                    method-specific code
tests/                   unit tests
```

## Setup

Requires conda (Miniconda/Anaconda).

```bash
conda env create -f environment.yml   # creates env "mmde" (Python 3.11) and installs the package editable with dev tools
conda activate mmde
pytest                                # smoke tests
ruff check . && ruff format --check .
```

Dependencies are declared in `pyproject.toml` and added only when a checkpoint needs them
(decision D-006). Copy `.env.example` to `.env` and fill in values when needed.
