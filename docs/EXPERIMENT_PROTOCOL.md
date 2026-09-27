# Experiment Protocol

Every experiment must be reproducible from the repository state and its recorded config.

## Required fields per experiment

| Field | Notes |
|---|---|
| `experiment_id` | e.g. `EXP-0001-bm25-mmlb-pilot`; unique, never reused |
| `study` | e.g. `ladrag` (Study 01), `technical` (Study 02) — matches `experiments/<study>/` |
| `date` | ISO 8601 |
| `git_commit` | full hash; working tree must be clean (or diff saved with the run) |
| `source_label` | `REPRO` / `TECH` / `PROPOSED` (paper numbers are never produced by experiments) |
| `dataset` | e.g. `MMLongBench-Doc` |
| `dataset_version` | HF revision / commit / download date + checksum |
| `dataset_subset` | `full` / `pilot-v1` / ... (subset definition file path) |
| `num_documents` | |
| `num_queries` | after any filtering; filtering rule recorded in notes |
| `retrieval_method` | e.g. `bm25-page`, `e5-large-v2-element`, `ladrag-full`, `ladrag-noC`, ... |
| `retrieval_unit` | page / element / node (how units are mapped to pages) |
| `models` | every model with exact version/checkpoint (embedder, LVLM, agent LLM, QA model) |
| `top_k` | value or list of values; `dynamic` for agent retrieval |
| `seed` | when any randomness is involved (sampling, Louvain, subset selection) |
| `hardware` | GPU / CPU / RAM (reference `docs/ENVIRONMENT.md` + any differences) |
| `perfect_recall` | mean PR over queries |
| `ipr` | mean IPR over queries |
| `qa_accuracy` | when applicable; with judge model + version |
| `latency` | wall-clock per query (mean, p50, p95), and ingestion time per document |
| `token_usage` / `api_cost` | prompt/completion tokens per stage; API cost if applicable |
| `notes` | deviations from the paper, known issues |

## Files

```
experiments/<study>/                  # ladrag/ (Study 01), technical/ (Study 02), ...
  configs/<experiment_id>.yaml        # the exact config used (committed)
  runs/<experiment_id>/               # raw outputs, logs, per-query predictions (NOT committed)
    per_query.jsonl                   # one line per query: ids, retrieved pages, PR, IPR, latency, tokens
    run_meta.json                     # all required fields above
  results/
    results.csv                       # one row per (experiment_id, k) — committed, append-only
```

Shared baselines (e.g. BM25 on MMLongBench-Doc) are filed under the study whose benchmark they
run on (`ladrag/` for MMLongBench-Doc, `technical/` for technical documents).
Experiment IDs are unique across the whole repository, not just within a study.

- Results must be **machine-readable** (CSV or JSONL). Tables in docs are generated from these.
- Aggregate numbers are always computed from `per_query.jsonl` by code, never typed by hand.
- Failed or aborted runs are recorded too (with status), not silently deleted.
- Paper numbers used for comparison live in a separate file (e.g. `experiments/ladrag/results/paper_reported.csv`)
  with `source_label = PAPER` and a page/table reference.

## Metrics (per paper, §3.3)

- **Perfect Recall:** `PR = 1 if P ⊆ P̂ else 0`, averaged over queries.
- **Irrelevant Pages Ratio:** `IPR = |P̂ \ P| / |P̂|`, averaged over queries.
- Node/element-level retrieval is mapped to the **set of pages** containing retrieved items before scoring.
- Edge-case conventions: to be fixed in CP-1.2 / CP-1.3 and recorded in `DECISIONS.md`.
