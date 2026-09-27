# LAD-RAG Reproduction Protocol (Study 01)

Created in CP-4.0 (D-011); **revised in CP-4.1A (2026-09-27, D-019, Accepted)** for a
resource-constrained, local-first strategy. The CP-4.0 version (GPT-4o calibration + gpt-4o-mini
ingestion) is preserved in git history (commit `3453137`); only its model/resource/budget parts are
superseded (see D-011 in DECISIONS.md).

This document fixes what Study 01 reproduces exactly, what is reconstructed or substituted, the pilot
size, the API spending policy, and how results are reported. It is the reference for every `[REPRO]`
number in Study 01.

**Position:** Study 01 is a **resource-constrained partial reproduction** of LAD-RAG. The system is
always called **LAD-RAG†**; exact reproduction is never claimed.

---

## 0. Principle: "Local-first, API-last"

Development order for every model-dependent component:
1. deterministic implementation;
2. mocks / scripted models;
3. lightweight local model;
4. evaluate feasibility and quality;
5. optional API validation only when it provides important information.

- **The Phase 4 pipeline must be completable with USD 0 of API spend.** External APIs are optional
  validation only; no checkpoint may require GPT-4o, the OpenAI API, the DeepSeek API or paid cloud
  compute as an acceptance criterion.
- Never spend API credits to debug normal engineering problems.
- All expensive/model calls are cached, resumable, logged, and explicitly approved before execution.

Labels: **[PAPER-EXACT]** explicitly specified by the paper · **[RECONSTRUCTED]** detail missing,
documented choice · **[SUBSTITUTED]** original model/hardware unavailable, replaced ·
**[OPTIONAL-REFERENCE]** comparison with the original/stronger model if budget permits.

## 1. Original LAD-RAG compute requirements (from the paper)

Source: `papers/ladrag/2026.acl-long.724.pdf`, §2–3, App. H (see `PAPER_NOTES.md`).

| Component | Paper setting |
|---|---|
| Page rendering | PyMuPDF, 300 DPI; downscaled to 50% (rarely 20%) under GPU memory limits |
| Ingestion LVLM | **GPT-4o**, temperature 0, max tokens 8192 |
| Ingestion calls per page | node extraction (Fig. 9, image), section-queue update (Fig. 10), graph construction (Fig. 11, image + memory) |
| Intra-page relations | consumed by Fig. 11 — prompt not published |
| Graph | NetworkX, undirected; Louvain communities (parameters not published) |
| Neural index | vector index over node summaries — embedding model not published |
| Retrieval agent | **GPT-4o**, temperature 0, max 20 rounds; semantic search, graph filter, community contextualization |
| Baselines | BM25 (bm25s), E5-large-v2, BGE-large-en (over element summaries), ColPali, RAPTOR |
| QA models / judge | Phi-3.5-Vision-4B, Pixtral-12B, InternVL2-8B, GPT-4o; GPT-4o answer extraction |
| Serving / hardware | vLLM 0.9.2, **4× NVIDIA A100**, Python 3.10.12, PyTorch 2.7.0+cu126 |
| Code | **not released** (App. A) |

Scale for MMLongBench-Doc (our release): 135 documents, 6,529 pages, 1,082 questions → ≈ 19,600
image-bearing model calls for ingestion. Planning estimate (CP-4.0) for a faithful GPT-4o run:
≈ $350 ingestion + ≈ $45 agent — **not affordable and not pursued**.

## 2. Available resources (as of 2026-09-27)

| Resource | Status |
|---|---|
| Local machine | Windows 10, i7-10700, 32 GB RAM, NVIDIA Quadro RTX 4000 **8 GB VRAM** (Turing) |
| DeepSeek API | optional; **cumulative research spend must stay below USD 5** |
| OpenAI API | small remaining credit; **optional only** |
| Funding | none |
| Lab A100/H100, paid cloud GPU | **not assumed** |
| vLLM | not available on native Windows |
| Official LAD-RAG code | not released |

## 3. Component levels

| # | Component | Level | LAD-RAG† |
|---|---|---|---|
| C1 | Dataset MMLongBench-Doc (1,082 q) | [PAPER-EXACT] | GitHub @ `d73f0dc0` (D-010); defects handled per D-012 |
| C2 | PR / IPR | [PAPER-EXACT] definitions; [RECONSTRUCTED] edge cases | D-008, D-009 |
| C3 | Page rendering | [PAPER-EXACT] tool/DPI | PyMuPDF 300 DPI; resizing to the model's input size logged |
| C4 | Prompts Figs. 9–12 | [PAPER-EXACT] | verbatim transcription (CP-4.1) |
| C5 | Intra-page relations | [RECONSTRUCTED] | deterministic (IMPLEMENTATION_SPEC R4) |
| C6 | Ingestion VLM | [SUBSTITUTED] | local lightweight VLM chosen in CP-4.3B; mocks before that |
| C7 | Graph + Louvain | [PAPER-EXACT] library/algorithm; [RECONSTRUCTED] parameters | NetworkX; config-driven resolution/seed |
| C8 | Neural index embedding | [RECONSTRUCTED] | config-driven; default E5-large-v2 (local GPU) |
| C9 | Agent LLM | [SUBSTITUTED] | scripted → local LLM → optional limited DeepSeek |
| C10 | Agent loop (prompt, 20 rounds, temp 0, tools) | [PAPER-EXACT] + [RECONSTRUCTED] sandbox/observations | IMPLEMENTATION_SPEC §5 |
| C11 | Baselines BM25 / E5 / BGE | [PAPER-EXACT] models; inputs per phase | page-text (Phase 3) and element-summary (CP-4.5), kept separate |
| C12 | ColPali | deferred | — |
| C13 | RAPTOR | deferred | — |
| C14 | QA stage + judge | deferred | — |
| C15 | LongDocURL, DUDE, MP-DocVQA | not reproduced | — |
| C16 | Serving (vLLM, 4× A100) | [SUBSTITUTED] | local runtime on 8 GB GPU |

## 4. Ingestion strategy

Old priority (CP-4.0, superseded): GPT-4o → cheaper API → local fallback.

**New priority (CP-4.1A):**
mock implementation → local lightweight VLM (feasibility, CP-4.3B) → local calibration (CP-4.3C) →
local pilot ingestion (CP-4.3D).

Optional only: a stronger API VLM as an **[OPTIONAL-REFERENCE]** on 3–5 pages, if remaining OpenAI
credit permits and the user explicitly approves. It is never an acceptance criterion.

No provider/model (GPT-4o, GPT-4o-mini, DeepSeek vision, Qwen, or any other) is hard-coded as the
mandatory ingestion model. The local model is chosen in CP-4.3B by availability, license, 8 GB
feasibility, structured-output capability and vision support, preferring ≈ 2B–4B class models (with
quantization if useful); 7B/8B is not a requirement. If no suitable VLM runs reliably on 8 GB, that is
reported honestly with a cheaper alternative (e.g. the non-LLM I-4 option: PyMuPDF text blocks + OCR).

## 5. Pilot, budget and API spending policy

**Subsets (D-013):** `pilot-v1` — 10 documents, 241 pages, 80 questions;
`calib-v1` — 2 documents, 33 pages. Local feasibility (CP-4.3B) uses 3–5 representative pages and
calibration (CP-4.3C) ≈ 20–30 pages; completing all 241 pilot pages is **not** a prerequisite for
proving the framework (CP-4.3D).

**API spending policy — hard rules:**
1. The research pipeline must remain executable with $0 API spending.
2. No API experiment starts automatically.
3. User approval is required before every new paid experiment.
4. DeepSeek cumulative research spend must remain below USD 5.
5. OpenAI API usage is optional only.
6. No automatic account top-up.
7. Actual (not estimated) usage is logged after each paid run.
8. Responses are cached permanently for reproduction.
9. A run aborts before exceeding its configured budget.
10. API pricing and model availability are rechecked immediately before each paid experiment.

**Planned paid use (all optional):** limited DeepSeek agent evaluation (CP-4.6C: 20 evidence
questions, semantic-only vs. full LAD-RAG†) and possibly an [OPTIONAL-REFERENCE] VLM comparison on
3–5 pages. Expansion (more questions, ablations in CP-4.7) only after explicit approval.

## 6. Reporting

1. Every Study 01 result carries `source_label = REPRO`, `reproduction_level`
   (`exact` / `substituted` / `partial`) and a component spec, e.g.
   `LAD-RAG†: ingestion=<local VLM id@rev, quant>; embeddings=e5-large-v2@f169b11e; graph=reconstructed NetworkX (louvain res=1.0 seed=0); agent=<scripted | local id | deepseek model id>`.
2. The system name is **LAD-RAG†** with a footnote listing substitutions and reconstructions.
3. Primary comparisons are internal, on the same pilot subset, same metric code:
   page-text baselines vs. element-summary baselines vs. graph retrieval vs. dynamic LAD-RAG†.
4. Comparisons with `[PAPER]` numbers are indicative only; absolute pilot numbers are never compared
   with the paper as if produced under identical conditions (different models, subset, edge-case
   policy, dataset defects).
5. Pilot results are never extrapolated to the full dataset.
6. Results are reported on the clean set (primary) and the full set (D-012).
7. [OPTIONAL-REFERENCE] results are reported separately and labelled as such.

## 7. Separation of paper-reported and reproduced results

- Paper numbers live only in `experiments/ladrag/results/paper_reported.csv` (`source_label = PAPER`,
  with table/figure/page reference; figure read-offs marked approximate); ours only in `results.csv`.
- No script writes paper numbers into our results files, or vice versa; tables showing both carry an
  explicit `source` column.

## 8. If resources change

If more resources appear later (e.g. a lab GPU or funding), stronger components can be added as new
experiments with new IDs (agent → stronger LLM; ingestion → stronger VLM; more pages). Earlier
results are kept. This is optional and never assumed.

## 9. Research interpretation

The resource constraint is **not** the thesis contribution. Observations it may yield — e.g.
lightweight ingestion losing cross-page links, agent quality depending strongly on LLM capability,
selective multimodal processing preserving quality at lower cost — are recorded as observations or
hypotheses only. The research problem remains undecided until the Phase 5–6 failure analysis.
