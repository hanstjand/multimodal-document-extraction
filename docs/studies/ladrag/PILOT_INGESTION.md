# Pilot graph construction — CP-4.3D Stage 1 (ING-0001)

Date: 2026-09-28/29. Plan: `experiments/ladrag/configs/ING-0001-stage1-qwen3.5-2b-1280.json`.
Report: `experiments/ladrag/results/ingestion/ING-0001-stage1-qwen3.5-2b-1280.json`; graph check:
`…/ING-0001-stage1-qwen3.5-2b-1280-graph-check.json` (`scripts/ladrag_stage1_graph_check.py`).
Graphs and page records: `data/processed/ladrag/graphs/ING-0001-stage1-qwen3.5-2b-1280/<doc>/`
(not committed; `graph.json`, `pages/`, `summary.json`, `progress.json`, `run.log`).

Settings (approved, D-021): the five retrieval-eval-v1 documents, full documents from page 1,
Qwen/Qwen3.5-2B @ 15852e8c fp16 greedy, thinking off (D-020), 1280 px, 8192 output tokens, runaways
measured only, cache reuse only for identical requests, R22 OOM policy. API cost **$0**.
These are the evaluation graphs for retrieval-eval-v1; the CAL-0001 partial graphs are not used.

**Code provenance (clarified 2026-09-29):** ING-0001 was executed from an **uncommitted working
tree based on commit `2c81370`** (the value recorded in the report's `git_commit` field). The
implementation used for the run — including R22 (resource-failure policy) and R23 (key-order-preserving
page records) — was committed **afterwards** as `9522b2b`, together with the run's outputs. The run was
not executed from `9522b2b`; the ingestion code in that commit (`src/`, `scripts/ladrag_ingestion_calibration.py`)
is the code that was in the working tree during the run — only the post-run analysis script
`scripts/ladrag_stage1_graph_check.py` and documentation were added after the run started. No rerun
was made or is required.

## 1. Run history

- 18:33 first launch; after 3 pages (all from cache) a reproducibility bug was found: page records
  were key-sorted, so a resumed run rendered the working memory into prompts in a different key order
  than an uninterrupted run (CAL-0001 2305 p4–8 had been produced that way). Run stopped, fixed as
  **R23** (records keep key order; test: crash + resume sends exactly the uninterrupted prompts),
  restarted with `--restart` at 18:37. Log of the aborted attempt: `run.aborted-sortedkeys.log`.
- 18:37:32 → 04:11:46 (2026-09-29): one uninterrupted invocation; exit code 0.

## 2. Results per document

| Document | Pages | Pages with nodes | Nodes | Edges | Calls (cached) | JSON repairs | Wall |
|---|---|---|---|---|---|---|---|
| 2305.14160v4 | 16 | 14 | 119 | 166 | 45 (16) | 7 | 1.62 h |
| f8d3a162… | 17 | 17 | 264 | 408 | 49 (20) | 4 | 1.35 h |
| reportq32015… | 34 | 33 | 83 | 229 | 89 (4) | 5 | 1.76 h |
| mi_phone | 37 | 37 | 193 | 348 | 97 (4) | 2 | 2.24 h |
| Campaign_038… | 28 | 28 | 187 | 442 | 82 (5) | 5 | 2.61 h |
| **Total** | **132** | **129** | **846** | **1,593** | **362 (49)** | 23 pages | **9.57 h** |

Page status: 132 completed; **0 resource failures** (no OOM, no retry needed); 129 `ok` with nodes;
3 `ok` without nodes, all caused by JSON failure of node extraction (2305 p11, p14; reportq3 p32 —
none is a gold page). JSON failure of graph construction (nodes kept, no Fig. 11 output, memory
unchanged) on 5 pages: 2305 p4 and p9, f8d3 p11, reportq3 p6, Campaign p25. All 8 JSON failures are
pages where both the first call and the repair call hit the 8192-token limit.

## 3. Graph, relations, memory

- Edge types in the merged graphs: next_on_page 717, is_part_of_section 867, continues 414,
  explains 196, references 166, summarizes 87, updates 42 (an edge can carry several types).
- **Cross-page edges** (origin Fig. 11, endpoints on different pages): **714**, of which 92 join
  adjacent pages and 622 non-adjacent pages. Accepted cross-page relations by type:
  is_part_of_section 460, continues 207, references 118, summarizes 41, explains 17, updates 5.
- Rejected relations: 206 (unknown endpoint 155, missing relation type 50, self-loop 1).
- Working memory (characters, first → max → last page): 2305 3,519 → 5,363; f8d3 3,147 → 7,168;
  reportq3 243 → 3,102; mi_phone 441 → 11,807 → 9,438; Campaign 709 → 5,682. Full per-page series in
  the report (`memory_chars_series`).
- Node types: paragraph 406, section_header 217, figure 82, title 32, footnote 26, table 21, footer 21,
  others 41.

## 4. Runaways, time, VRAM

- Runaway calls (8192 tokens): **30 of 362** (graph construction 19, node extraction 11); first
  attempts 22/339 = **6.5 %**; 22 pages had at least one runaway.
- Wall time **34,454 s = 9.57 h** (one invocation, incl. model loading) — above the 6–9 h estimate;
  late pages of long documents took up to ≈ 17 min (memory growth + runaways).
- Model time actually spent 34,444 s; estimated no-cache model time 40,422 s (306 s/page mean, median
  259 s, max 1,021 s).
- Cache reuse (identical requests only): 49 of 362 calls — 2305 p1–3 fully, f8d3 p1–6 fully, and step-A
  node extraction of the CAL-0001 pages (2305 p4–8 and the 13 mid-document pages), as planned.
- Peak VRAM: **5.82 GiB allocated / 8.06 GiB reserved** (of 8 GiB) — at the limit, but no OOM.

## 5. Gold-page coverage (retrieval-eval-v1)

All **35/35** evidence questions have every gold page represented by at least one graph node
(no gold page lies on a resource-failed or node-less page).

Degraded gold pages (reported, not excluded; JSON/model failures are part of the method's outcome):
- 2305 p4 — only 2 nodes and no Fig. 11 output (both calls runaway); gold page of 3 questions
  (2 multi-page, 1 single-page). No cross-page edges originate from p4 (edges from later pages to p4
  nodes are possible).
- Campaign p25 — nodes present, no Fig. 11 output; gold page of the 6-page question.

## 6. Issues that would invalidate retrieval-eval-v1

None found: complete documents, no resource failures, every gold page has nodes, protocol frozen
before any retrieval result. Caveats to carry into CP-4.5A: the two degraded gold pages above; three
distractor pages without nodes (slightly fewer distractors); VRAM headroom ≈ 0 for Stage 2.
