# Neural node index and element baselines — CP-4.5 (NIDX-0001)

Date: 2026-09-29. Plan: `experiments/ladrag/configs/NIDX-0001-stage1.json`. Report:
`experiments/ladrag/results/node_index/NIDX-0001-stage1.json`. Script:
`scripts/ladrag_build_node_index.py`. Code: `src/multimodal_document_extraction/studies/ladrag/node_retrieval.py`.
Saved dense indices (embeddings + node records, reused by CP-4.5A so that seeds are identical):
`data/processed/ladrag/node_index/NIDX-0001-stage1/<retriever>/` (not committed).

Input: the five Stage-1 evaluation graphs of ING-0001 only (graph SHA-256 recorded per document);
CP-4.3C partial graphs are not used. **No question text, no gold evidence, no PR/IPR, no API.**
Code provenance: NIDX-0001 was run from an uncommitted working tree based on commit `d583c03` (the
value in the report's `git_commit`); the exact CP-4.5 implementation was committed afterwards as
`5eaff0e` (the only later edit was removing an unused import from the build script, no behaviour
change). No rerun was made or is required; CP-4.5A uses the saved NIDX-0001 indices.

## 1. Retrievers

| Name | Text | Role |
|---|---|---|
| `e5-large-v2-r10` | `summary + "\n" + content` (R10) | **primary** LAD-RAG† neural node index; semantic seeds for retrieval-eval-v1 |
| `bm25-summary` | element summary | paper-style BM25 element-summary baseline (D-014 `bm25-elements`) |
| `e5-large-v2-summary` | element summary | paper-style dense element baseline (D-016) |
| `bge-large-en-summary` | element summary | paper-style dense element baseline (D-016); same infrastructure |

All are node-level (unit = node) and kept separate from the Phase-3 page-text baselines. Mapping nodes
to a page ranking (R19 page-level k, D-021 truncation) is CP-4.5A's job.

## 2. Configuration and provenance

- E5: `intfloat/e5-large-v2` @ `f169b11e22de13617baa190a028a32f3493550b6` (the Phase-3 pin), prefixes
  `query: ` / `passage: ` (model card, as in Phase 3); BGE: `BAAI/bge-large-en` @ `abe7d9d8…`, query
  instruction `Represent this sentence for searching relevant passages: `, no passage prefix.
- Embedding dimension 1024, dtype float32, device cuda:0 (Quadro RTX 4000), batch size 16,
  L2-normalized embeddings, cosine similarity.
- R10 windows: `window_tokens = 512` (model input incl. prefix and special tokens), `overlap_tokens =
  64`, node score = max cosine over windows (MaxP); no truncation (every token is in a window).
- BM25: Phase-3 settings (bm25s 0.3.11, lucene, k1 1.5, b 0.75, English stopwords, lowercase).
- Versions: Python 3.11.16, torch 2.14.0+cu126, transformers 5.17.0, sentence-transformers 6.1.0,
  numpy 2.4.6. API cost $0.

## 3. Index statistics

| Document | Nodes | R10 multi-window nodes | R10 tokens median / p95 / max |
|---|---|---|---|
| 2305.14160v4 | 119 | 4 | 97 / 390 / 1,036 |
| Campaign_038… | 187 | 0 | 60 / 176 / 286 |
| f8d3a162… | 264 | 3 | 29 / 140 / 1,031 |
| mi_phone | 193 | 0 | 46 / 213 / 507 |
| reportq32015… | 83 | 3 | 38 / 237 / 1,069 |
| **Total** | **846** | **10** (836 fit one window; max 3 windows; 861 windows) | |

- R10 text: 0 unscored nodes; 0 non-string fields needed serialization.
- Summary text: 3 nodes (reportq3) have no summary → unscored (ranked last) in the summary baselines;
  they remain scored in the R10 index through their content. Summary tokens max 162 → one window each.
- The tokenizer warning "sequence length 518 > 512" comes from counting tokens of whole long texts;
  the model only ever receives windows within the limit.

## 4. Search behaviour

`semantic_search(question, doc_id, top_k_nodes=10)` returns `NodeHit(rank, node_id, page, node_type,
score)`; `rank_nodes` returns all nodes. Ranking: score descending; **ties by canonical node ID order**
(page, object index); unscored nodes last in node ID order; `top_k_nodes` larger than the node count
returns all nodes; invalid `top_k_nodes` raises. No page mapping inside the retriever.

## 5. Validation (non-gold) — all checks passed

Per retriever and document: all graph nodes indexed (846), unique node IDs, node-ID index order,
node → page preserved, finite scores, identical re-ranking, top-k > node count safe; for dense indices
also: index rebuilt from scratch → max absolute embedding difference **0.0** and identical rankings,
index loaded from disk → identical rankings. Smoke searches used five neutral, non-benchmark queries.

## 6. Cost

Wall time 66.8 s for all four retrievers (model loading 1.5–8.1 s); R10 index 13.2 s for 846 nodes;
query latency ≈ 20–32 ms mean per query and document (dense, GPU), < 1 ms (BM25). Peak VRAM 3.87 GiB
allocated / 3.95 GiB reserved.
