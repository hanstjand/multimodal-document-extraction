# Local Ingestion Calibration (CP-4.3C)

Date: 2026-09-28. Model: Qwen/Qwen3.5-2B @ 15852e8c, fp16, greedy, thinking disabled (D-020).
Settings approved by the user: paper decoding (temperature 0 → greedy, `max_output_tokens` 8192);
runaway generations **measured only**; main run at 1280 px plus a 1280 vs 1600 px comparison.
API cost: **$0**.

Plans (committed): `experiments/ladrag/configs/CAL-0001-qwen3.5-2b-1280.json`,
`CAL-0002-qwen3.5-2b-1600-figures.json`. Reports (committed):
`experiments/ladrag/results/calibration/CAL-0001-qwen3.5-2b-1280.json`, `CAL-0002-…json`.
Script: `scripts/ladrag_ingestion_calibration.py` (full pipeline or step A only; `--mock` dry run).
Page records and cached replies: `data/processed/ladrag/calibration/`, `data/processed/ladrag/llm_cache/`
(not committed).

## 1. Sample (27 pages, contiguous ranges from pilot-v1)

| Document | Pages | Role |
|---|---|---|
| 2305.14160v4.pdf | 1–8 | academic paper, two columns, charts, table, heatmaps |
| f8d3a162…pdf | 1–6 | administration file, text-dense; multi-page questions 1–2, 4–6 |
| reportq32015-…_95.pdf | 7–10 | slide deck without text layer, charts |
| mi_phone.pdf | 4–7 | guidebook with figures/tables; multi-page questions 4–5, 6–9 |
| Campaign_038_…_v5e.pdf | 5–9 | layout-heavy brochure; multi-page question 5–6 |

Contiguous ranges let the working memory and cross-page relations develop as in real ingestion.

## 2. CAL-0001 — full pipeline at 1280 px

| Metric | Result |
|---|---|
| Pages with nodes | **27/27** (268 nodes) |
| Pages with unrecoverable JSON | **0**; 6 pages needed one repair call; container normalized on 11 pages (7 `id_map`, 4 `single_object`) |
| Runaway calls (8192 tokens) | 6/78 calls; 8.3 % of first attempts (4 in graph construction, 1 node extraction, 1 other) |
| Model time per page | mean 312 s, median 253 s, max 920 s (pages with a runaway ≈ 500–920 s) |
| Wall time (27 pages incl. restart) | 6,770 s ≈ 1.9 h |
| Peak VRAM | 5.62 GiB allocated / **7.62 GiB reserved** (of 8 GiB) |
| Text coverage (pages with text layer) | mean **0.87** (0.46–1.00) |
| Numbers in nodes also in PDF text | mean 0.89 — **lower bound**: numbers read from raster figures (phone screen, chart axes, heatmaps) are counted as "not in PDF" |
| PDF numbers recovered | mean 0.63 |
| Cross-page relations accepted | 44 (37 `continues`, 6 `references`, 1 `is_part_of_section`); 6 rejected (`unknown endpoint`) |
| Graph (5 documents) | 268 nodes, 341 edges, communities per document 2–10 |

Node types: paragraph 160, section_header 62, figure 19, title 5, equation 5, bullet_list 5, table 4, others 8.

**Stability / resume (requirement of CP-4.3C):** the run was killed deliberately at 12:49:16 after
page 3 of 2305.14160v4.pdf (page 4 in progress) and restarted. Page records 1–3 were not rewritten
(timestamps unchanged), the run continued at page 4 (finished 12:50:52) and `pages_resumed = 3`.
Only the page in progress was lost.

**Determinism:** node extraction for 2305.14160v4 p1 and mi_phone p4 re-run without cache produced
byte-identical text (2/2).

**Memory growth:** the working memory grows with the document: academic paper 3.5k → 12.8k characters
over 8 pages; administration file 3.1k → 4.5k; slides 1.5k → 2.7k; guidebook 0.6k → 1.2k; brochure
0.7k → 1.7k. Graph construction (Fig. 11) rewrites the whole memory each page (3–7k output tokens),
which dominates latency and drives the runaway calls.

**Quality observations (manual checks):** tables and slide charts remain accurate; text-dense
administration pages reach 0.94–0.99 coverage; on figure-dominated pages the model sometimes omits the
surrounding text (mi_phone p4: figure correct, heading and paragraph missing, coverage 0.46) or omits a
figure (2305 p4 at 1280 px); image-only slides become one merged node per slide.

## 3. CAL-0002 — 1280 vs 1600 px (step A only, 7 figure-rich pages)

| | 1280 px | 1600 px |
|---|---|---|
| Nodes | 35 | **42** |
| Figure nodes | 3 | **6** |
| Text coverage (5 pages with text) | 0.71 | **0.83** |
| PDF numbers recovered (mean) | — | 0.84 |
| Visual prompt tokens per call | ≈ 1.5–1.9k | ≈ +0.6k |
| Model time, 7 pages (excl. one repair call) | ≈ 468 s | ≈ 568 s (**+21 %**) |
| JSON repairs | 0 | 1 |
| Peak VRAM (step A only) | — | 4.55 / 4.80 GiB |

Page-level: 2305 p4 — Figure 3 (two line charts) is **found at 1600 px** with correct trends (it was
missed at 1280 px), but grouped-bar values of Figure 4 are still mis-bound to legend colours;
right-column text is duplicated into both figure nodes. 2305 p8 — at 1600 px the model reads the two
**heatmaps' cell values** (checked visually: mostly correct), which lowers the "numbers in PDF text"
ratio because the heatmaps are raster images. mi_phone p4 — text coverage 0.46 → 0.80.

## 4. Conclusions for pilot ingestion (CP-4.3D)

1. The local pipeline is **stable** (0 unrecoverable pages, crash/resume and determinism verified).
2. **Time:** ≈ 5.2 min/page at 1280 px → pilot-v1 (241 pages) ≈ **21 h**; at 1600 px ≈ +10–20 %
   (≈ 23–25 h). Two overnight runs; resume makes interruptions harmless.
3. **1600 px improves recall of visual content** (more figures, higher text coverage, heatmap values)
   at ≈ +21 % step-A time. Grouped-bar chart values remain unreliable at either resolution.
4. **VRAM risk:** at 1280 px the full pipeline already reserved 7.62 of 8 GiB (long Fig. 11 prompts on
   the academic paper). 1600 px adds ≈ 0.6k visual tokens to each image call; an out-of-memory error
   on long documents is possible — resume limits the damage but a page could fail repeatedly.
5. **Runaway calls** (≈ 8 % of first attempts) cost ≈ 5–6 min each; mostly graph construction.

**Open decisions for CP-4.3D (need user approval):**
- Resolution for the pilot: 1280 px (safer, faster) or 1600 px (better visual recall, VRAM risk).
- Whether to keep measuring runaways only, or add a mitigation now (e.g. cap Fig. 11 output tokens,
  stop rule for repeated blank lines) — any change is [RECONSTRUCTED] and must be reported.
- OOM handling: e.g. retry the failed page once at a lower resolution (logged) vs. flag and skip.
