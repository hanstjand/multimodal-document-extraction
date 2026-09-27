# Project Context

## Research project

**Multimodal Document Extraction** (Master's research, NTUST).

This repository is the main repository for the whole Master's research, not for a single method.

## Research area

- Visually-rich document understanding
- Document retrieval
- Multi-page reasoning
- Document information extraction

## Research methodology

```
existing method reproduction
  → original-domain evaluation
  → technical-domain evaluation
  → performance degradation analysis
  → failure analysis
  → targeted literature review
  → candidate improvements
  → proposed method evaluation
```

Research problems are identified from **observed failures**, not assumed in advance.

## Studies

### Study 01 — LAD-RAG reproduction (current)

- **Paper:** Sourati et al., *LAD-RAG: Layout-aware Dynamic RAG for Visually-Rich Document
  Understanding*, ACL 2026 (Long), pp. 15945–15968 (arXiv preprint `2510.07233`).
  Local copy: `papers/ladrag/2026.acl-long.724.pdf`. Notes: `docs/studies/ladrag/PAPER_NOTES.md`.
- **Benchmark:** MMLongBench-Doc (135 PDFs, 1,082 questions per the paper).
- **Goal:** reimplement and partially reproduce LAD-RAG on MMLongBench-Doc.
  "Partial" means: reproduce the retrieval behaviour (Perfect Recall, Irrelevant Pages Ratio)
  and, where affordable, QA accuracy. Reproducing all four benchmarks and all four QA models
  is not committed to.
- LAD-RAG is the **first method studied**, not the final method of this research.

### Study 02 — Technical-domain evaluation (future, planned)

Evaluate the reproduced pipeline, unchanged, on technical documents / technical datasheets;
measure the performance degradation relative to Study 01.

### Later work (not yet defined)

Failure analysis, targeted literature review, candidate improvements (including combinations or
modifications of existing methods), and eventually a proposed method.

## Open research directions (none selected)

The final novelty is intentionally **not fixed**. The following are *possible* directions only,
to be pursued only if supported by experimental evidence:

- graph-based retrieval / Graph RAG,
- cross-page retrieval,
- cost efficiency (e.g. cheaper ingestion, selective VLM use),
- others that emerge from failure analysis.

None of these is the stated research direction or contribution.

## Result labelling

| Label | Meaning |
|---|---|
| `[PAPER]` | Numbers reported in a published paper (e.g. LAD-RAG) |
| `[REPRO]` | Our reproduction on the original benchmark(s) |
| `[TECH]` | Our results on technical-domain documents |
| `[PROPOSED]` | Results of our proposed method(s) |

## Current immediate goal

Finish the research infrastructure (Phase 0), then build the evaluation foundation, in order to
reimplement and partially reproduce LAD-RAG on MMLongBench-Doc (Study 01).
