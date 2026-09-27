# CLAUDE.md — Working Rules for This Repository

This is the main repository of a Master's research project on **Multimodal Document
Extraction**. Work is organized into studies: Study 01 reimplements and partially reproduces
**LAD-RAG** (ACL 2026); Study 02 evaluates it on technical documents / datasheets. Later phases
analyse failures and develop a proposed method. The final research contribution is
**not yet decided**, and LAD-RAG is not assumed to be the final method.

## Mandatory reading order

1. Read `docs/PROJECT_CONTEXT.md` before any substantial work.
2. Read `docs/CHECKPOINTS.md` before doing anything.
3. Read the **latest** entry in `docs/RESEARCH_LOG.md`.
4. Check `docs/DECISIONS.md` before changing architecture, dependencies, data formats, or metrics.

## Checkpoint discipline

5. Work on **ONLY ONE** checkpoint at a time.
6. **Never** automatically continue to the next checkpoint.
7. After completing a checkpoint:
   - update `docs/CHECKPOINTS.md` (status + acceptance criteria ticks),
   - append an entry to `docs/RESEARCH_LOG.md`,
   - summarize the work to the user,
   - **STOP**,
   - wait for explicit user approval before starting anything else.

Status markers: `[ ]` not started · `[~]` in progress · `[x]` completed · `[!]` blocked.
A checkpoint is marked `[x]` only if all of its acceptance criteria are met.
If blocked, mark `[!]` and record the reason in the log.

## Scientific integrity

8. **Never fabricate experiment results.** No placeholder numbers presented as results.
   If something was not run, say so.
9. Always label numbers by source, clearly distinguishing:
   - **[PAPER]** — paper-reported results (e.g. LAD-RAG: `papers/ladrag/2026.acl-long.724.pdf`),
   - **[REPRO]** — our reproduction results on the original benchmark(s),
   - **[TECH]** — our results on technical-domain documents,
   - **[PROPOSED]** — results of our proposed method(s).
   Never mix these in a table without an explicit source column.
10. Preserve reproducibility: follow `docs/EXPERIMENT_PROTOCOL.md`; record git commit,
    config, seed, model versions, hardware; write machine-readable results (CSV/JSONL).

## Other rules

- `docs/RESEARCH_LOG.md` is **append-only**. Never rewrite historical entries;
  corrections go in a new entry that references the old one.
- Do not download datasets or models unless the current checkpoint requires it.
- Do not modify system software (drivers, CUDA, global Python) without explicit approval.
- Secrets live in `.env` (never committed); `.env.example` documents the variables.
- Raw data goes in `data/raw/` and is never modified in place; derived data goes in `data/processed/`.
- Do not treat any research direction (cost efficiency, graph retrieval / Graph RAG, cross-page
  retrieval, selective VLM use, ...) as the final topic. The direction is chosen only after
  failure analysis (Phase 6).
- Code layout: shared, method-agnostic code goes in the top-level subpackages of
  `src/multimodal_document_extraction/`; method-specific code goes in `studies/<study>/`.
  Study material follows the same pattern: `docs/studies/<study>/`, `papers/<study>/`,
  `experiments/<study>/`.
