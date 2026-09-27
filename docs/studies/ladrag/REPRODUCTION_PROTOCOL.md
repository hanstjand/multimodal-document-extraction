# LAD-RAG Reproduction Protocol (Study 01)

Checkpoint CP-4.0, 2026-09-27. Decision record: D-011.

This document fixes, **before any LAD-RAG code is written**, what we reproduce exactly, what we
substitute because resources are missing, how large the pilot is, and how substituted results are
reported. It is the reference for every `[REPRO]` number in Study 01.

Cost figures in §2 and §5 are **planning estimates** derived from the paper's prompts, not
measurements. They must be replaced by measured token usage after the first calibration run.

---

## 1. Original LAD-RAG compute requirements (from the paper)

Source: `papers/ladrag/2026.acl-long.724.pdf`, §2–3, App. H (see `PAPER_NOTES.md`).

| Component | Paper setting |
|---|---|
| Page rendering | PyMuPDF, 300 DPI; downscaled to 50% (rarely 20%) under GPU memory limits |
| Ingestion LVLM | **GPT-4o**, temperature 0, max tokens 8192 |
| Ingestion calls per page | 3 prompts: node extraction (Fig. 9, page image), section-queue update (Fig. 10), graph construction / cross-page relations (Fig. 11, page image + memory) |
| Intra-page relations | consumed by Fig. 11 ("CURRENT PAGE RELATIONSHIPS") — **prompt not published** |
| Graph | NetworkX, undirected; Louvain communities (parameters not published) |
| Neural index | vector index over node summaries — **embedding model not published** |
| Retrieval agent | **GPT-4o**, temperature 0, max 20 rounds; tools: semantic search, graph filter (LLM-written Python), community contextualization |
| Baselines | BM25 (bm25s), E5-large-v2, BGE-large-en (over element summaries), ColPali (page images), RAPTOR |
| QA models | Phi-3.5-Vision-4B, Pixtral-12B, InternVL2-8B, GPT-4o; greedy decoding, max 2048 tokens |
| QA judge | GPT-4o answer extraction + rule-based scoring (MMLongBench protocol) |
| Serving / hardware | vLLM 0.9.2, **4× NVIDIA A100**, Python 3.10.12, PyTorch 2.7.0+cu126 |
| Datasets | MMLongBench-Doc, LongDocURL, DUDE, MP-DocVQA |
| Code | **not released** (App. A) |

Scale for MMLongBench-Doc (our release, `MMLONGBENCH_DOC.md`): 135 documents, **6,529 pages**,
1,082 questions → ≈ 19,600 LVLM ingestion calls with images, plus 2–5 agent calls per question
(paper Fig. 4).

**Estimated cost of a faithful full run with GPT-4o** (assumption: ≈ 7.5k input tokens incl. two page
images and ≈ 3.5k output tokens per page; ≈ 15k input and ≈ 300 output tokens per question for the
agent; prices checked 2026-09-27: GPT-4o $2.50 / $10.00 per 1M tokens):
ingestion ≈ $350 (≈ $175 with the 50% Batch API discount), agent ≈ $45.

## 2. Available and unavailable resources (as of 2026-09-27)

| Resource | Status |
|---|---|
| Local GPU | NVIDIA Quadro RTX 4000, **8 GB VRAM**, Turing (no bf16, no FlashAttention-2), Windows |
| CPU / RAM / disk | i7-10700 8C/16T, 31.8 GB RAM, ~168 GB free |
| OpenAI API credit | **$4.68** |
| DeepSeek API credit | **$3.78** |
| 4× A100 / multi-GPU server | **unavailable** (lab GPU server: unknown — to be asked) |
| vLLM | **unavailable** on native Windows (would need WSL2/Linux) |
| Budget for full GPT-4o run (≈ $200–400) | **unavailable** |
| Official LAD-RAG code | **unavailable** (not released) |
| Unpublished details (intra-page relation prompt, embedding model, Louvain parameters, Table 1 score formula) | **unavailable** — must be reconstructed |
| MMLongBench-Doc (1,082-question version) | available, with documented defects (19 questions affected) |

## 3. Exact vs. substituted components

Levels: **Exact** = as in the paper · **Reconstructed** = paper under-specifies; we choose and document ·
**Substituted** = paper's choice unavailable; replaced · **Deferred** = later, if resources allow ·
**Not reproduced** = out of scope for Study 01.

| # | Component | Level | Our choice |
|---|---|---|---|
| C1 | Dataset (MMLongBench-Doc, 1,082 q) | Exact | GitHub @ `d73f0dc0` (D-010); defects handled per CP-2.2 policy |
| C2 | Retrieval metrics PR / IPR | Exact definition + Reconstructed edge cases | D-008, D-009 (evidence subset = paper-compatible) |
| C3 | Page rendering | Exact tool, DPI may be reduced | PyMuPDF; 300 DPI rendering, downscaling allowed as in paper App. H.1 (recorded per run) |
| C4 | Ingestion prompts (Figs. 9–11) | Exact text | copied verbatim from App. H.2 |
| C5 | Intra-page relation extraction | Reconstructed | own prompt, documented in CP-4.2/4.3 |
| C6 | Ingestion LVLM | **Substituted** | see §4 (primary: gpt-4o-mini; GPT-4o only on calibration docs) |
| C7 | Graph library + Louvain | Exact library, Reconstructed parameters | NetworkX `louvain_communities`, fixed seed, default resolution (recorded) |
| C8 | Neural index embedding | Reconstructed | chosen in CP-4.5 among the paper's own baseline embedders (E5-large-v2 / BGE-large-en), run locally |
| C9 | Retrieval agent LLM | **Substituted** | development: local 7–8B model (e.g. Qwen2.5-Coder-7B, 4-bit, Ollama); pilot evaluation: DeepSeek API; GPT-4o agent only if budget remains |
| C10 | Agent loop (prompt Fig. 12, 20 rounds, temp 0, tools) | Exact | verbatim prompt; sandboxed execution of generated code (our addition, safety) |
| C11 | Baselines BM25 / E5 / BGE | Exact models, input text per Phase 3 decision | local CPU/GPU |
| C12 | ColPali baseline | Deferred | ~3B model; may fit 8 GB in fp16 — to verify |
| C13 | RAPTOR baseline | Deferred | needs LLM summarization budget |
| C14 | QA stage + GPT-4o judge | Deferred | retrieval is the paper's core contribution; QA only after retrieval is stable |
| C15 | LongDocURL, DUDE, MP-DocVQA | Not reproduced | Study 01 = MMLongBench-Doc only |
| C16 | Serving stack (vLLM, 4× A100) | Substituted | API models + Ollama / llama.cpp locally |

Consequence: our system is **LAD-RAG†** ("LAD-RAG with substituted models"), never plain "LAD-RAG".

## 4. Lightweight ingestion alternatives (selection)

| Tier | Model / method | Role | Cost / feasibility | Status |
|---|---|---|---|---|
| I-0 | GPT-4o (paper model) | **Calibration reference** on 2 documents | ≈ $0.05 per page → ≈ $1.6 for ~30 pages | selected (reference only) |
| I-1 | **gpt-4o-mini** (OpenAI, vision, JSON mode) | **Primary pilot ingestion** — same model family as GPT-4o, same API and prompt format | ≈ $0.004–0.007 per page (image tokens dominate) | **selected** |
| I-2 | deepseek-flash (DeepSeek, vision per pricing page) | Secondary candidate; only if I-1 quality is inadequate or for comparison | ≈ $0.003–0.007 per page; image tokenization and JSON reliability unverified | candidate |
| I-3 | Qwen2.5-VL-3B/7B, 4-bit, local (Ollama / llama.cpp) | Zero-cost fallback; paper reports InternVL2-8B extraction comparable to GPT-4o (§7) | free; slow (tens of seconds per page, estimate) | fallback |
| I-4 | PyMuPDF text blocks (+ OCR for image-only PDFs) | Non-LLM structural baseline (no summaries, no semantic cross-page edges) | free, fast | optional ablation |

Selection rule (decided before seeing results):
1. Ingest the **calibration set** (§5) with both I-0 and I-1.
2. Compare element extraction on those pages (element count, types, text coverage vs. PDF text layer,
   JSON validity) and, once retrieval runs, PR/IPR on their questions.
3. Keep I-1 as the pilot ingestion model unless it produces invalid JSON on > 10% of pages or clearly
   misses content; otherwise switch to I-2, then I-3. The outcome is logged in RESEARCH_LOG and D-011.

Model availability and prices are re-checked immediately before spending (CP-4.3).

## 5. Pilot size and budget

**Pilot set (`pilot-v1`), selected in CP-2.3:**
- **10 documents**, stratified: at least 1 per each of the 7 `doc_type`s, all ≤ 40 pages
  (87 documents qualify: 2,098 pages, 690 questions); target ≈ 200–250 pages and ≈ 70–90 questions.
- Include all questions of each selected document; ensure multi-page questions (≥ 25%) and
  no-evidence questions are represented; include ≥ 1 image-only PDF.
- Exclude `dr-vorapptchapter1emissionsources-…pdf` (wrong PDF) — it is > 40 pages anyway.
- Selection procedure and random seed recorded; the ID list is versioned.

**Calibration set (`calib-v1`):** 2 of the pilot documents, ≈ 30 pages total, with at least one
multi-page question each.

**Realized in CP-2.3 (D-013):** `data/splits/mmlongbench-doc/pilot-v1.json` — 10 documents, 241 pages,
80 questions (28 multi-page, 14 no-evidence, 1 image-only PDF), all 7 doc types, seed 0;
`calib-v1.json` — `2305.14160v4.pdf` + `f8d3a162ab9507e021d83dd109118b60.pdf`, 33 pages, 16 questions.

**Budget plan (planning estimates):**

| Item | Account | Estimated cost |
|---|---|---|
| Calibration ingestion, GPT-4o (≈ 30 pages) | OpenAI | ≈ $0.8–1.6 |
| Pilot ingestion, gpt-4o-mini (≈ 250 pages) | OpenAI | ≈ $0.9–1.8 |
| Agent runs on pilot (≈ 80 questions × ~4 variants: full, w/o C, w/o G, w/o C&G) | DeepSeek | ≈ $1–3 |
| Agent development | local model | $0 |

Spending rules: run the Batch API wherever latency does not matter; record token usage per call;
**stop and report when cumulative spend reaches 80% of an account balance** (OpenAI $3.74,
DeepSeek $3.02); never top up without user approval.

## 6. Reporting substituted results

1. Every Study 01 result row carries: `source_label = REPRO`, `reproduction_level`
   (`exact` / `substituted` / `partial`), and a component spec, e.g.
   `ingest=gpt-4o-mini@<date>; agent=deepseek-v4-pro; embed=e5-large-v2; louvain_seed=0; subset=pilot-v1`.
2. The system name in tables is **LAD-RAG†** with a footnote listing the substitutions (§3).
3. Valid comparisons: LAD-RAG† vs. **our** baselines on the **same subset**, with the same ingestion
   output and metric code. Ablations (w/o C, w/o G, w/o C&G) likewise.
4. Comparisons with `[PAPER]` numbers are **indicative only** and must state: different models,
   different subset (pilot vs. full), metric edge-case policy (D-008/D-009), known dataset defects.
   Relative trends (e.g. LAD-RAG† > BM25 at equal IPR) may be compared; absolute gaps may not be
   interpreted as reproduction failure or success.
5. Results on pilot subsets are never extrapolated to the full dataset.
6. Results are reported on the **clean** set (primary; excludes the 19 flagged questions) and,
   separately, on the full set (paper-comparable count), per D-012.

## 7. Separation of paper-reported and reproduced results

- Paper numbers live only in `experiments/ladrag/results/paper_reported.csv`
  (`source_label = PAPER`, with table/figure/page reference); our numbers only in
  `experiments/ladrag/results/results.csv` (`source_label = REPRO`).
- No script writes paper numbers into our results files, or vice versa; tables that show both are
  generated with an explicit `source` column.
- `[PAPER]` numbers are transcribed from the PDF (never from memory) and checked against
  `PAPER_NOTES.md`.
- Figure 3 values (PR vs. IPR curves) are not transcribed as numbers, since the PDF offers only an image.

## 8. Upgrade path

If more resources become available (lab GPU ≥ 24 GB with Linux/vLLM, or API budget ≈ $200–400),
upgrade in this order: (1) agent → GPT-4o on the pilot; (2) ingestion → GPT-4o on the pilot;
(3) full dataset. Each upgrade is a new experiment ID; earlier results are kept.
