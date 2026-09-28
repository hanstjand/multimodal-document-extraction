# Local VLM Feasibility for LAD-RAG† Ingestion (CP-4.3B)

Status: **completed 2026-09-28** — verdict in §5. Model download and the two small dependencies
(Pillow, torchvision) were approved by the user before installation.
Policy: D-019 — local-first, $0; no model is mandatory; honest verdict required.

## 1. Constraints

- GPU: NVIDIA Quadro RTX 4000, **8 GB VRAM, Turing (compute 7.5)** — no native bf16, no
  FlashAttention-2 → models run in **fp16** (or quantized).
- Windows 10; existing env `mmde`: torch 2.14.0+cu126, transformers 5.17.0 (no bitsandbytes,
  no accelerate installed).
- Task: LAD-RAG Fig. 9 / Fig. 11 prompts — long instructions, one page image, **long structured JSON
  output** (full content + self-contained summaries of every element), temperature 0.

## 2. Ecosystem check (2026-09-27)

Sources: Hugging Face model API/cards (checked 2026-09-27); overviews
[BentoML](https://www.bentoml.com/blog/multimodal-ai-a-guide-to-open-source-vision-language-models),
[DataCamp](https://www.datacamp.com/blog/top-vision-language-models),
[Labellerr](https://www.labellerr.com/blog/top-open-source-vision-language-models/).

| Model | Params | License / access | Released / revision | Supported by installed transformers | fp16 weights | Fits 8 GB? |
|---|---|---|---|---|---|---|
| **Qwen/Qwen3.5-2B** | 2.27 B | Apache-2.0, open | 2026-03-02, `15852e8c` | yes (`qwen3_5`) | ≈ 4.6 GB | yes (fp16) |
| **Qwen/Qwen3-VL-2B-Instruct** | 2.13 B | Apache-2.0, open | 2025-10-23, `89644892` | yes (`qwen3_vl`) | ≈ 4.3 GB | yes (fp16) |
| Qwen/Qwen3.5-4B | 4.66 B | Apache-2.0, open | 2026-03-02, `851bf6e8` | yes | ≈ 9.3 GB | only quantized (needs bitsandbytes / GGUF runtime) |
| Qwen/Qwen3-VL-4B-Instruct | 4.44 B | Apache-2.0, open | 2025-10-15, `ebb281ec` | yes | ≈ 8.9 GB | only quantized |
| openbmb/MiniCPM-V-4 | 4.06 B | Apache-2.0, `trust_remote_code` | 2026-08-18 | remote code | ≈ 8.1 GB | only quantized |
| google/gemma-3-4b-it | 4.30 B | Gemma license, **gated (manual approval)** | 2025-03-21 | — | ≈ 8.6 GB | only quantized |
| Qwen/Qwen3.5-0.8B | ≈ 0.8 B | Apache-2.0 | 2026-02-28 | yes | ≈ 1.7 GB | yes (quality risk) |

Also noted (not candidates for Fig. 9/11): dedicated document parsers (e.g. Docling-style models,
OCR-VL models) output Markdown/doctags rather than LAD-RAG's JSON with summaries; they remain a possible
cheaper fallback (REPRODUCTION_PROTOCOL §4, option I-4-like) if general VLMs fail.

## 3. Proposed feasibility design

**Candidates (fp16, transformers, no new packages):**
1. `Qwen/Qwen3.5-2B` @ `15852e8c` — newest, natively multimodal, structured-output oriented;
   **thinking mode must be disabled** (`enable_thinking=False`) — it is on by default.
2. `Qwen/Qwen3-VL-2B-Instruct` @ `89644892` — instruct VLM with strong OCR focus, no thinking mode.

4B-class models are **not** required (D-019); a quantized 4B would only be tried if both 2B models
fail on quality and the user approves an extra dependency.

**Runtime settings ([RECONSTRUCTED], recorded per run):** fp16, greedy decoding (temperature 0 →
`do_sample=False`), `max_new_tokens` 8192 (paper) unless VRAM forces lower, SDPA attention;
page images rendered by PyMuPDF at 300 DPI and downscaled to longest side
**`image_max_side_px = 1280`** (≈ 1–1.5k visual tokens instead of ≈ 8k at full 300 DPI; R2).

**Pages (3–5, chosen deterministically from pilot/calibration documents using question metadata):**
text-heavy, table, figure/chart (incl. the image-only slide deck), layout-heavy (brochure), and two
consecutive pages of one multi-page question (cross-page behaviour).

**Measurements per model × page:** loads (yes/no), peak VRAM, latency per call and per page,
output tokens, JSON validity (with/without repair), node count and types, text coverage vs. the PDF
text layer (where one exists), manual quality notes (content fidelity, summaries, missed
visual/layout elements), cross-page relations produced.

**Verdict rules:** a model is *feasible* for CP-4.3C if it loads within 8 GB, produces valid JSON
(after ≤ 1 repair) on ≥ 4/5 pages, and extracts the main text/table/figure content without gross
omissions on manual inspection. Otherwise report "not feasible" and propose a cheaper alternative.

## 4. Results (2026-09-27/28)

Setup: `scripts/ladrag_vlm_feasibility.py <model> --restart`; full LAD-RAG† ingestion (A–D) via
`DocumentIngestor`; fp16, greedy, `max_new_tokens` 8192, images ≤ 1280 px; transformers 5.17.0,
torch 2.14.0+cu126; Quadro RTX 4000. Reports: `experiments/ladrag/results/feasibility/FEAS-<model>.json`
(committed); page records and cached replies under `data/processed/ladrag/` (not committed).
**API cost: $0.** Downloads: Qwen3.5-2B 4.26 GB, Qwen3-VL-2B 3.97 GB (HF cache).

### 4.1 Framework issues found and fixed during the run (not model quality)

The first run exposed parsing strictness in *our* framework; replies were kept in the cache and
re-parsed after the fixes (decision D-020):
- **R17b container normalization** — Qwen3.5-2B returned correct objects as a single JSON object
  (chart slide) or as `{object_id: object}` (brochure) instead of a list → both pages had 0 nodes.
- **R17c column-0 parsing + lenient escapes** — (i) LaTeX in JSON strings (`$\mathcal{L}$`, `\(`)
  made academic pages invalid; (ii) my first R17b parser silently salvaged one nested object from a
  truncated reply; now only JSON starting at the beginning of a line is considered, so broken
  structures fail loudly and trigger a repair call.
- **R21** — Fig. 11 is skipped for pages with no nodes (the model otherwise invents IDs and loops).

### 4.2 Metrics (final re-run with the fixed parser)

| | **Qwen3.5-2B** | Qwen3-VL-2B-Instruct |
|---|---|---|
| Loads in 8 GB (fp16) | yes — peak 4.74 GiB allocated / 4.99 GiB reserved | yes — peak 5.53 / **7.75 GiB reserved** |
| Load time | 7–9 s | 7 s |
| Decoding speed (smoke test) | ≈ 20 tok/s (reference kernels; fast kernels unavailable on Windows) | ≈ 25 tok/s |
| Pages with nodes | **5/5** | 3/5 |
| Node-extraction JSON valid (≤ 1 repair) | **5/5** | 3/5 |
| Graph-construction JSON valid | **5/5** (after R21) | 1/3 |
| Calls hitting 8192 tokens (runaway) | 1 of 12 non-cached heavy calls | 7 of 11 |
| Model time per page (uncached) | 69–554 s, mean ≈ 240 s | 124–758 s, mean ≈ 585 s |

Per page, Qwen3.5-2B:

| Page | Role | Nodes (types) | Text coverage | Notes |
|---|---|---|---|---|
| 2305.14160v4 p3 | text + chart | 15 (7 para, 5 header, 3 eq.) | 0.82 | 42 relations, no rejections |
| 2305.14160v4 p4 | text + chart | 2 (1 figure, 1 para) | 0.78 | **Figure 3 (two line charts) missed; Figure 4 bar values hallucinated ("all at 100")**; text merged into one node; 5 `continues` + 6 `explains` to p3 |
| 2305.14160v4 p7 | table | 5 (2 table, 3 para) | 0.85 | first call runaway → repair OK; **59/59 extracted numbers exist in the PDF; 48/53 PDF numbers recovered** |
| reportq3 p10 | chart slide, no text layer | 1 (figure) | n/a | **all 8 bar values, title, legend, unit and paragraph correct**; text + chart merged in one node; 5 relations rejected (invented IDs) |
| Campaign_038 p9 | layout-heavy brochure | 8 (5 para, 2 header, 1 figure) | **1.00** | returned as `id_map` (normalized) |

Qwen3-VL-2B: p3 10 nodes (0.88), p4 10 nodes incl. 4 figures (0.86), brochure 10 nodes (1.00), but the
table page and the chart slide produced **no nodes** (both calls degenerated into repeated `\n` until
8192 tokens), and graph construction failed on both academic pages (no cross-page relations).

### 4.3 Manual inspection notes (Qwen3.5-2B)

- Strong on large, clearly rendered content: slide charts (exact values), tables (no invented numbers),
  brochure text.
- Weak on dense two-column academic pages with several small figures: whole figures can be omitted and
  small-chart values invented (p4). This matters for chart questions such as mmlb-0973/0974.
- Granularity is coarser than the paper implies (text + chart merged; multi-paragraph nodes).
- `page_metadata.page_number` is sometimes hallucinated; `is_part_of_section` edges were rare on the
  academic pages (mostly `explains` / `continues` / copied `next_on_page`).

## 5. Verdict

- **Qwen3.5-2B: feasible, with limitations** → proposed as the local ingestion model for CP-4.3C.
  It meets the load and JSON criteria (5/5 pages, ≤ 1 repair) and extracts text, tables and slide
  charts well; it fails the "no gross omission" criterion on 1/5 pages (dense academic figure page).
  Estimated pilot-v1 time ≈ 241 pages × ≈ 4 min ≈ 16 h (overnight runs; runaway calls add up to ≈ 6 min each).
- **Qwen3-VL-2B-Instruct: not feasible** in this setting (runaway repetition on 7/11 heavy calls,
  2/5 pages without nodes, reserved VRAM near the 8 GB limit).
- No stronger model is required to proceed; a quantized 4B model or an [OPTIONAL-REFERENCE] API model
  remain options only if CP-4.3C shows the figure-omission problem is frequent.

**Open questions for CP-4.3C (need approval; they change decoding/config):**
1. Runaway repetition mitigation: e.g. `repetition_penalty` ≈ 1.05 (deterministic), a lower
   `max_output_tokens` for Fig. 11, or a stop rule for long runs of blank lines.
2. Image resolution: 1280 px vs. ≈ 1600 px (VRAM headroom ≈ 3 GB) to reduce figure omissions.
3. Page sample of ≈ 20–30 pages for calibration (stratified by the same roles, from pilot-v1).
