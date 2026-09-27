# Experiments

Follow `docs/EXPERIMENT_PROTOCOL.md`. One folder per study:

| Study folder | Study |
|---|---|
| `ladrag/` | Study 01 — LAD-RAG reproduction on MMLongBench-Doc (plus baselines on that benchmark) |
| `technical/` | Study 02 — technical-domain evaluation |

Inside each study folder:

| Directory | Contents | Committed |
|---|---|---|
| `configs/` | One config per experiment ID | yes |
| `runs/` | Raw outputs, logs, per-query JSONL | no |
| `results/` | Aggregated machine-readable results (CSV/JSONL) | yes |

No experiments have been run yet.
