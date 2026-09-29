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
| Estimated no-cache model time per page | mean 312 s, median 253 s, max 920 s (pages with a runaway ≈ 500–920 s) — see §2.1 |
| Model time actually spent (27 page records) | 7,580 s (≈ 281 s/page) |
| Wall time | 6,770 s for the report invocation (pages 4 ff. of 2305 onward); ≈ 7,800 s ≈ 2 h 10 min incl. the interrupted first invocation |
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

### 2.1 How to read the timing numbers (clarified after CP-4.3C review)

The committed reports CAL-0001/CAL-0002 keep their original field names; the calibration script now
writes clearer names (no re-run was made for the rename):

| Field in CAL-0001/0002 reports | New name | Meaning |
|---|---|---|
| `model_seconds_all`, `aggregate.model_seconds_per_page`, `aggregate.model_seconds_total` | `est_no_cache_model_seconds…` | Sum of the latencies stored with **every** call of a page record, including the *original* latency of replies served from the cache. An **estimate of model time without any cache**, not time spent in this run. |
| `model_seconds_uncached` | `model_seconds_this_run` | Model time of calls that actually ran when the page record was written. |
| `wall_seconds` (top level) | unchanged + `wall_seconds_scope` | Wall clock of **one invocation** only. |

CAL-0001 in these terms: 78 calls, 6 served from the cache (node extraction of 2305 p3, p4, p7 (2),
reportq3 p10, Campaign p9 — replies from CP-4.3B feasibility runs and from the interrupted first
invocation, same model/prompt/settings). Estimated no-cache model time 8,436 s = actually spent 7,580 s
+ 856 s of reused cached latency. The report's `wall_seconds` = 6,770 s covers only the second
invocation (12:49–14:42, incl. model loading and the two determinism re-runs, 167 s); the first
invocation (12:32–12:49, ≈ 1,020 s) produced pages 1–3 of 2305 and part of page 4. Total wall
≈ 2 h 10 min. CAL-0002 had no cache hits (estimate = actual = 755 s; wall 756 s).

For projecting a fresh pilot run (empty cache for the pilot pages) the **estimated no-cache** figure
is the relevant one: ≈ 312 s/page → 241 pages ≈ 21 h (unchanged). It is an estimate: the reused
latencies were measured in earlier runs of the same configuration.

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

## 3A. AI-assisted qualitative diagnostic audit of cross-page relations (CAL-0001)

**Status (2026-09-28, D-021):** this is an AI-assisted qualitative diagnostic audit, kept only as
failure-analysis evidence. It is **not** official ground truth, **not** edge precision or edge
accuracy, and **not** a benchmark metric. The generated graph is evaluated downstream against the
official `evidence_pages` (`RETRIEVAL_EVAL_V1.md`).

**Data provenance (clarified 2026-09-29):** the audited relations come from CAL-0001 calibration
data, produced **before R23** (the fix that makes resumed runs send the same prompts as uninterrupted
runs; 2305 p4–8 of CAL-0001 were produced after a resume with key-sorted memory). The audit is
qualitative/debugging evidence only and must not be used as a benchmark result or compared with
evaluation graphs (ING-0001).

Small diagnostic audit, **not** a ground-truth dataset; counts describe the 19 sampled relations only
and must not be generalised. Judgements were made by the AI assistant (Claude), not by a human
annotator. Sample: `scripts/ladrag_relation_audit_sample.py` (seed 0) over the 44
accepted cross-page relations (origin Fig. 11); all `references` (6) and `is_part_of_section` (1) kept,
12 of 37 `continues` drawn round-robin over the five documents (stratified, not proportional).
Judgements (by inspecting both nodes, all nodes of both pages and the PDF text layer; relation judged
as stated, i.e. type and direction) are stored with reasons in
`experiments/ladrag/results/calibration/CAL-0001-qwen3.5-2b-1280-relation-audit-sample.json`.
Categories: correct (holds as stated) / plausible (genuinely related, type implicit or loose) /
uncertain / incorrect (endpoints exist, relation does not hold) / hallucinated (endpoint content not in
the document).

| ID | Document | Source → target | Type | Source / target (short) | Judgement | Reason (short) |
|---|---|---|---|---|---|---|
| R01 | 2305 | p1 obj_009 → p2 obj_003 | continues | intro "Paragraph 2" / header "2 Label Words are Anchors" | incorrect | paragraph continues in p2 obj_002, not in the header |
| R02 | Campaign | p5 obj_008 → p6 obj_002 | continues | "18 data centers…" paragraph / call-out "Alibaba Cloud has 18 data centers" | plausible | same fact, but no textual continuation |
| R03 | f8d3 | p2 obj_017 → p1 obj_019 | continues | objective J / course-overview paragraph | incorrect | backward; list item of another sub-section |
| R04 | mi_phone | p6 obj_001 → p7 obj_001 | continues | header "Applications" / "Gallery" | correct | app list continues on p7 without new heading |
| R05 | reportq3 | p8 obj_001 → p9 obj_001 | continues | Android version chart / "Developers mindshare" title | incorrect | separate slides, different topics |
| R06 | 2305 | p1 obj_005 → p2 obj_001 | continues | Figure 1 caption / Figure 2 | incorrect | two separate complete figures |
| R07 | Campaign | p8 obj_002 → p5 obj_004 | continues | "Supporting business transformation" / "Alibaba Cloud's background" | incorrect | backward, different sections |
| R08 | f8d3 | p2 obj_005 → p1 obj_019 | continues | course objective / course-overview paragraph | incorrect | backward; p1 paragraph complete |
| R09 | mi_phone | p5 obj_002 → p6 obj_001 | continues | header "Installing the SIM…" / header "Applications" | incorrect | two different sections |
| R10 | reportq3 | p9 obj_001 → p10 obj_001 | continues | "Developers mindshare" title / "Apps by number" chart | incorrect | separate slides, different topics |
| R11 | 2305 | p1 obj_004 → p2 obj_002 | continues | Abstract / "scores to portray…" | incorrect | abstract complete; p2 text continues Paragraph 2 |
| R12 | Campaign | p8 obj_002 → p5 obj_002 | continues | "Supporting business transformation" / "Backing business transformation" | incorrect | backward; similar wording, different sections |
| R13 | mi_phone | p5 obj_002 → p6 obj_001 | is_part_of_section | header "Installing the SIM…" / header "Applications" | incorrect | sibling sections (same pair also as R09) |
| R14 | 2305 | p4 obj_001 → p1 obj_005 | references | Figure 4 / Figure 1 caption | plausible | implicit: Fig. 4 tests what Fig. 1 illustrates |
| R15 | 2305 | p4 obj_001 → p1 obj_006 | references | Figure 4 / footnote 1 (code URL) | incorrect | nothing refers to the footnote |
| R16 | 2305 | p4 obj_001 → p1 obj_009 | references | Figure 4 / intro "Paragraph 2" | plausible | implicit: evidence for the stated claim |
| R17 | 2305 | p4 obj_002 → p1 obj_005 | references | aggregation-validation paragraph / Figure 1 caption | plausible | implicit, no explicit citation |
| R18 | 2305 | p4 obj_002 → p1 obj_006 | references | aggregation-validation paragraph / footnote 1 | incorrect | nothing refers to the footnote |
| R19 | 2305 | p4 obj_002 → p1 obj_009 | references | aggregation-validation paragraph / intro "Paragraph 2" | plausible | implicit reference to the hypothesis |

**Counts (sample only, n = 19):** correct 1, plausible 5, uncertain 0, incorrect 13, hallucinated 0.
By type: `continues` 1 / 1 / 0 / 10 / 0 (n = 12); `references` 0 / 4 / 0 / 2 / 0 (n = 6);
`is_part_of_section` 0 / 0 / 0 / 1 / 0 (n = 1).

Patterns seen in the sample (descriptive, full-set counts are structural, not judgements):
- **One-to-one pairing:** 2305 p1→p2 links four p1 nodes one-to-one to the first four p2 nodes
  (R01, R06, R11 + one unsampled); the true continuation (Paragraph 2 → "scores to portray…") is
  present in the data but attached to the wrong endpoints.
- **Backward `continues`:** in the full set 21 of 37 `continues` point to an earlier page; one p1
  paragraph of f8d3 receives 11 links (hub).
- **Cartesian `references`:** the six references are the full 2 × 3 product of two p4 nodes and three
  p1 nodes, i.e. not chosen pair by pair.
- No hallucinated endpoints: all endpoints exist (unknown endpoints are already rejected, 6 cases).

Consequence for later work: cross-page relations from the 2B model are an unreliable signal as
produced; any use in retrieval (graph expansion) should be evaluated with and without them. No change
to the pipeline is made in CP-4.3C.

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
6. **Qualitative diagnostic only:** in the AI-assisted audit sample (§3A; 1 correct, 5 plausible,
   13 incorrect of 19) cross-page relations were structurally valid but often semantically wrong. Not
   an accuracy estimate; whether the relations help is measured against `evidence_pages` (D-021).

**Open decisions for CP-4.3D (need user approval):**
- Resolution for the pilot: 1280 px (safer, faster) or 1600 px (better visual recall, VRAM risk).
- Whether to keep measuring runaways only, or add a mitigation now (e.g. cap Fig. 11 output tokens,
  stop rule for repeated blank lines) — any change is [RECONSTRUCTED] and must be reported.
- OOM handling: e.g. retry the failed page once at a lower resolution (logged) vs. flag and skip.
