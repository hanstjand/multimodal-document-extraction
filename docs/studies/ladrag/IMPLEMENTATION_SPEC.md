# LAD-RAG† Implementation Specification

Status: **Accepted** — decision D-018 (Accepted 2026-09-27). First drafted in CP-4.1; revised in
CP-4.1A (2026-09-27) for the resource-constrained, local-first Phase 4 strategy (D-019, Accepted).

Scope: what Phase 4 builds for a **resource-constrained partial reproduction** of LAD-RAG, derived from
the paper (`PAPER_NOTES.md`), its figures, and the verbatim prompts
(`src/multimodal_document_extraction/studies/ladrag/prompts/`), within `REPRODUCTION_PROTOCOL.md`.
The system is always called **LAD-RAG†**; exact reproduction is not claimed.

## 0. Principles and labels

**Local-first, API-last.** Development order for every model-dependent component:
1. deterministic implementation;
2. mocks / scripted models;
3. lightweight local model;
4. evaluate feasibility and quality;
5. optional API validation only when it provides important information.

Never spend API credits to debug normal engineering problems. Every expensive/model call is
**cached, resumable, logged, and explicitly approved before execution**. The whole Phase 4 pipeline
must be completable with **$0 API spend**; no checkpoint has a paid API or paid cloud compute as an
acceptance criterion (D-019).

Labels used below:

| Label | Meaning |
|---|---|
| **[PAPER-EXACT]** | explicitly specified by the paper (text, prompt, or figure — figure-derived items name the figure) |
| **[RECONSTRUCTED]** (R#) | the paper omits the detail; we make a documented, configurable choice |
| **[SUBSTITUTED]** (S#) | the paper's model/hardware is unavailable and replaced |
| **[OPTIONAL-REFERENCE]** | comparison with the original/stronger model, only if budget permits and the user approves |

Architecture kept as close to LAD-RAG as possible:
multimodal ingestion → structured document graph → neural index → symbolic graph retrieval →
dynamic retrieval agent.

## 1. Evidence from the paper's figures (CP-4.1)

| Finding | Label | Consequence |
|---|---|---|
| Node IDs used by the agent look like `page_22-obj_002`: `get_community_for_node("page_22-obj_002", doc_graph)` | [PAPER-EXACT] Fig. 6 | per-document graphs with short IDs (R1) |
| Chart filter: `node.get('type') == 'figure'` | [PAPER-EXACT] Fig. 5 | node attributes are plain dict keys |
| Relation categories: structural hierarchy, content/section grounding, cross-page references, semantic continuation | [PAPER-EXACT] Fig. 2 | matches Fig. 11 edge types |
| Fig. 3: x = IPR, y = PR; baselines trace k = 1…; LAD-RAG is one point | [PAPER-EXACT] Fig. 3 | report PR-vs-IPR curves + LAD-RAG† point |
| LAD-RAG on MMLongBench-Doc ≈ PR 0.83 at IPR 0.79 (read off the plot) | [PAPER-EXACT] Fig. 3, approximate | context only; not a comparable target (§8) |
| Baseline k = "number of retrieved pages" (mean 22 on MMLongBench) | [PAPER-EXACT] Fig. 3 caption | page-level k for element baselines (R19) |

## 2. Pipeline overview

```
PDF ──render──► page image ─┐
                             ├─► [A] node extraction (Fig. 9, image)       VisionModel
                             │   [B] section_queue update (Fig. 10)         TextModel or VisionModel
                             │   [C] intra-page relations (R4, deterministic, no model)
                             └─► [D] graph construction (Fig. 11, image)    VisionModel
 per page: checkpoint to disk (resume from the last completed page)
 after last page: NetworkX graph → Louvain (R8) → symbolic index G;  node texts → embeddings → neural index E
 question → agent (Fig. 12, AgentModel) ⇄ tools {do_semantic_search, doc_graph filter, get_community_for_node}
          → selected node IDs → pages P̂ → PR / IPR (D-008 / D-009)
```

Model calls per page [PAPER-EXACT structure]: A (always, image), B (only if the page has
section-like objects), D (always, image). The paper used GPT-4o for all of them; in LAD-RAG† the
model behind each interface is chosen per checkpoint (S1–S3).

## 3. Model interfaces (vendor-neutral)

- `VisionModel.generate(messages, images, params) -> ModelReply` (text + usage + model identifier).
- `AgentModel.generate(messages, params) -> ModelReply`.
- Implementations, in the order they are introduced: `ScriptedVisionModel` / `MockVisionModel`
  (CP-4.3A), local VLM (CP-4.3B–D), `ScriptedAgentModel` / `FakeAgentModel` (CP-4.6A), local LLM
  (CP-4.6B), optional API adapters (DeepSeek in CP-4.6C; any API VLM only as [OPTIONAL-REFERENCE]).
- No provider or model is hard-coded as mandatory. Each run records the exact model identifier,
  checkpoint/revision, quantization, runtime and version.
- All calls go through one cached, logged, budget-guarded client layer (§7).

## 4. Ingestion

### 4.1 Page images
- [PAPER-EXACT] PyMuPDF rendering at 300 DPI; downscaling allowed under memory limits (App. H.1).
- **R2** [RECONSTRUCTED] images are resized to the selected model's supported input size
  (`ingestion.image_max_side_px`, model-specific; documented in CP-4.3B); rendering DPI and sent size
  are logged.

### 4.2 [A] Node extraction — Fig. 9 [PAPER-EXACT prompt]
- `render_node_extraction(prefix)`; user message = prompt + page image; temperature 0 and max output
  tokens 8192 [PAPER-EXACT] (reduced only if the local model's limit requires it — logged).
- **R1** [RECONSTRUCTED from Fig. 6] one graph per document; `prefix = "page_{n}"`, node IDs
  `page_{n}-obj_{k:03d}`; invalid/duplicate claimed IDs are reassigned deterministically (count logged).
- Node attributes: the Fig. 9 fields + `page`, `doc_id`, `object_id`, `order_on_page`, plus (added in
  CP-4.2) `claimed_object_id` and `extra_fields` so nothing the model returns is silently discarded.
  `content`, `summary`, `title_or_heading` are coerced to text (non-text values become JSON text).
- **R17** [RECONSTRUCTED] parsing: strip code fences, parse the first JSON value; on failure one repair
  call ("Your previous output was not valid JSON. Return only the JSON list."); still invalid → page
  flagged, no nodes. JSON failure and repair rates are feasibility metrics (CP-4.3B/C).

### 4.3 [B] Running memory — Fig. 10 [PAPER-EXACT prompt]
- **R3** [RECONSTRUCTED] candidates = page nodes with `type` ∈ `ingestion.section_types`
  (default {`title`, `section_header`}); none → no call.
- **R6** [RECONSTRUCTED] initial memory `{"section_queue": [], "active_entities": [], "semantic_topics": [], "unresolved_objects": []}`.

### 4.4 [C] Intra-page relationships — R4 [RECONSTRUCTED; prompt not published]
Deterministic, no model call: `next_on_page` edges between consecutive objects in extraction order,
plus the objects' `layout_relation` strings, serialized as JSON into `{extracted_relations_text}`.

### 4.5 [D] Graph construction — Fig. 11 [PAPER-EXACT prompt]
- **R5** `{extracted_objects_text}` = JSON list of the page's nodes.
- Output `updated_memory` replaces memory except `section_queue` (kept from [B], as the prompt demands);
  `cross_page_relationships` added as edges.
- **R7** [RECONSTRUCTED] keep relations whose endpoints exist; drop self-loops/unknown IDs (logged);
  undirected `networkx.Graph` [PAPER-EXACT]; merged `types` / `sources` edge attributes.
- Memory is not capped (faithful); its size per page is logged (memory growth is a CP-4.3C metric).

### 4.6 After the last page
- **R8** [RECONSTRUCTED; Louvain is PAPER-EXACT] `community.algorithm = louvain`,
  `community.resolution = 1.0`, `community.seed = 0`, unweighted, computed once.
- **R9** [RECONSTRUCTED] `aggregated_section` nodes not created (construction unpublished).
- **R10** [RECONSTRUCTED] neural index: `neural_index.embedding_model` (default E5-large-v2, pinned,
  D-016) over `summary + "\n" + content`, `neural_index.window_tokens` / `window_overlap_tokens`
  (defaults 512 / 64, MaxP).
  CP-4.5 implementation (`studies/ladrag/node_retrieval.py`, NODE_INDEX.md): window = model input incl.
  prefix and special tokens (as Phase 3), no truncation; missing fields = `""`; nodes without tokens
  are unscored and ranked last; ties by node ID order; `text_field = "summary"` gives the paper-style
  element-summary baselines (BM25, E5, BGE). Nodes only — page mapping belongs to CP-4.5A.

### 4.7 Graph file format (implemented in CP-4.2)

`studies/ladrag/schema.py`, schema version `ladrag-graph/1`, deterministic JSON (sorted keys, sorted
nodes/edges, LF):

```json
{
  "schema": "ladrag-graph/1",
  "metadata": {"doc_id": "...", "num_pages": 16, "schema_version": "ladrag-graph/1",
               "created_at": null, "created_by": null, "ingestion_model": null,
               "config": {}, "provenance": {}},
  "nodes": [{"object_id": "page_1-obj_001", "doc_id": "...", "page": 1, "order_on_page": 0,
             "<Fig. 9 fields>": "...", "claimed_object_id": "...", "extra_fields": {},
             "community": 0}],
  "edges": [{"source": "page_1-obj_001", "target": "page_1-obj_002",
             "types": ["next_on_page"], "sources": ["intra_page"]}]
}
```

Node fields are split into [PAPER-EXACT] Fig. 9 fields and [RECONSTRUCTED] fields (`object_id`
canonical value, `doc_id`, `page`, `order_on_page`, `claimed_object_id`, `extra_fields`, `community`).
Unknown keys returned by the model are preserved in `extra_fields`; the model's own ID in
`claimed_object_id`. Loading re-validates everything (IDs, pages within `num_pages`, doc_id, unknown
attributes, unknown/duplicate edge endpoints, community completeness) and fails on any violation.
Working memory is validated against the four Fig. 11 keys and the Fig. 10 `section_queue` shape.

### 4.8 Checkpointing, caching, resume (CP-4.3A requirement)

Implemented in CP-4.3A: `studies/ladrag/ingestion.py` (`DocumentIngestor`, `IngestionConfig`,
`render_page`, `parse_json_reply`, `ModelClient`), `studies/ladrag/models.py` (`VisionModel` protocol,
`ScriptedVisionModel`, `MockVisionModel`), `utils/model_cache.py` (content-addressed cache).
Output per document: `pages/page_NNNN.json` (nodes, accepted relations with origin, rejected
relations with reasons, memory after the page, flags, repairs, call records incl. cache keys and
usage), `progress.json` (run fingerprint = sha256 of doc, PDF hash, pages, model id, config),
`graph.json`, `summary.json`. Implementation details (all [RECONSTRUCTED]):
- CP-4.3B additions (D-020): **R17b** node-extraction replies in another container (single object,
  `{object_id: object}` map, one-key wrapper) are normalized to a list and flagged
  `container_normalized:<shape>`; **R17c** only JSON starting at the beginning of a line is parsed (no
  salvage from inside truncated/broken structures), with one lenient-escape attempt for LaTeX
  backslashes (flag `json_lenient_escapes:<task>`); **R21** Fig. 11 is not called for pages without
  nodes (flag `graph_construction_skipped:no_nodes`). Record version 3.
- CP-4.3D addition (D-021): **R22** [RECONSTRUCTED] resource failures — the model adapter converts
  CUDA OOM into `ResourceExhaustedError` (memory statistics, CUDA cache released); the page is retried
  once with the identical configuration on a fresh copy of the graph; a second failure persists
  `status = resource_failure` (no nodes, memory unchanged, `resource_failures` details) and ingestion
  continues. Every page record has `status` (`ok` / `resource_failure`); failed pages are listed in
  `summary.json`, `progress.json` and `graph.json` metadata (`provenance.resource_failed_pages`,
  `provenance.pages_without_nodes`). Record version 4 (prompts and cache keys unchanged).
- **R23** (fix found at the start of CP-4.3D Stage 1): page records are written **without key
  sorting**, so a resumed run restores the working memory with its original key order. Before, records
  were key-sorted; the memory is rendered into Figs. 10/11 with `json.dumps` in insertion order, so a
  resumed run sent different prompts than an uninterrupted run (CAL-0001 2305 pages 4–8 were produced
  that way). Test: a crash + resume sends exactly the prompts of an uninterrupted run.
- Local VLM adapter: `studies/ladrag/local_vlm.py` (`TransformersVisionModel`, `LOCAL_VLMS`), fp16,
  greedy, Qwen3.5 thinking disabled; model id encodes repo@revision+dtype+thinking flag.
- JSON repair (R17) is a single-turn call: the original prompt + "Your previous output was not valid
  JSON. Return only the JSON list/object." (the failed output is not echoed back).
- `{extracted_objects_text}` = JSON (indent 2, UTF-8) of `object_id` + Fig. 9 fields per node (R5);
  `{extracted_relations_text}` = JSON list of the `next_on_page` relations followed by
  `{object_id, layout_relation}` entries (R4).
- Fig. 10 is called without an image (the paper's prompt contains no image reference).
- Invalid `updated_memory` keys keep their previous value (flagged); an invalid `section_queue` from
  [B] is rejected (flagged) and the previous queue kept.
- Resume replays the contiguous prefix of completed page records; a fingerprint mismatch aborts
  unless `restart=True`.
- After each page: nodes, memory, edges, call log and a `progress.json` are written atomically under
  `data/processed/ladrag/ingestion/<ingestion_config_id>/<doc_id>/`.
- A restart continues at the first incomplete page (e.g. crash on page 17 → resume at page 17 with
  pages 1–16 reloaded), never re-running completed pages; cached model replies make re-runs free.

## 5. Retrieval agent — Fig. 12 [PAPER-EXACT prompt]

- `render_retriever_agent(doc_id, question)` as the first user message; temperature 0 and a maximum of
  20 rounds [PAPER-EXACT]; stop on `DONE`, round limit, or nearing the context limit [PAPER-EXACT].
- **R15** [RECONSTRUCTED] `agent.max_output_tokens = 1024`, `agent.context_budget_tokens = 100000`.
- **R11** [RECONSTRUCTED] observations: `object_id | type | page | title_or_heading | summary[:300]`,
  at most `agent.observation_max_nodes = 50` per observation; errors as `ERROR: …`.
- **R12** [RECONSTRUCTED] DONE parsed with `ast.literal_eval`; if missing/invalid, fall back to the union
  of nodes returned so far (recall-first, as the prompt instructs); fallbacks counted.
- **R13** [RECONSTRUCTED] AST-restricted sandbox (expressions only, no `_` names/attributes, restricted
  builtins, frozen graph, `agent.code_timeout_s = 10`).
- Tools [PAPER-EXACT names]: `do_semantic_search(query, pdf_name)` → top `semantic_search.top_k`
  (**R10** default 10 — our choice, not a paper value); graph filter expression;
  `get_community_for_node(node_id, doc_graph)` → the node's community [PAPER-EXACT].
- **R14** output → `RetrievalResult(unit_type="node")`, pages from node attribute `page`.
- CP-4.4 implementation (`studies/ladrag/graph_retrieval.py`, `studies/ladrag/graph_query.py`):
  - `GraphIndex` over a persisted graph: `node_page` (attribute `page`, validated against the node ID),
    `pages_of` (distinct pages, first-appearance order), `neighbors(node, scope, relation_types,
    origins)`, `edges(scope)`, `ordered_one_hop_expansion(seeds, …)`, `get_community_for_node`.
  - **Cross-page edge** := its two endpoints have different `page` values; never inferred from
    relation type or origin (a Fig. 11 edge between two nodes of one page is intra-page).
  - **Node ID order** := (page, object index) numeric; neighbours are listed in this order.
  - **R24** [RECONSTRUCTED] ordered one-hop expansion (D-021): seeds in the given (semantic) order;
    per seed: the seed, then its neighbours by page, then node ID order; each node emitted once at its
    first occurrence; every seed is expanded even if already emitted. No gold information is used.
  - `get_community_for_node(node_id, doc_graph)` [PAPER-EXACT name/signature] returns
    `[(node_id, attributes), …]` of the persisted Louvain community in node ID order (no recomputation);
    unknown node → error; a node without a community assignment → itself as a singleton.
  - **R13** sandbox as implemented: `doc_graph` is a frozen, read-only NetworkX-like facade
    (`nodes(data=…)`, `nodes[id]`, `edges(data=…)`, `neighbors`, `has_node`, `degree`,
    `number_of_nodes`, `number_of_edges`) instead of the raw NetworkX object the Fig. 12 prompt
    mentions; other NetworkX APIs return an `ERROR`. Expression-only, allow-listed syntax and method
    names, no `_` names/attributes, no `*`/`**`/shifts/walrus/f-strings, bounded constants,
    restricted builtins (numbers-only `sum`), trace-based timeout `agent.code_timeout_s` (10 s),
    result-size cap. In-process: a single C-level operation cannot be interrupted (documented limit).
- **R20** ablations (w/o C, w/o G, w/o C&G) remove the tool from the namespace and its description
  lines from the prompt (paper does not say how) — only in optional CP-4.7.

## 6. Configuration (all paper-unspecified choices)

Every [RECONSTRUCTED] value is read from the experiment config (JSON, D-015) and recorded in
`run_meta.json`. Defaults below are **our reconstruction choices, never paper facts**; the paper's
own values are marked.

```json
{
  "ingestion": {
    "render_dpi": 300,
    "temperature": 0,
    "max_output_tokens": 8192,
    "image_max_side_px": null,
    "section_types": ["title", "section_header"],
    "json_repair_retries": 1
  },
  "community": {"algorithm": "louvain", "resolution": 1.0, "seed": 0, "weight": null},
  "neural_index": {"embedding_model": "e5-large-v2", "window_tokens": 512, "window_overlap_tokens": 64},
  "semantic_search": {"top_k": 10},
  "agent": {
    "max_rounds": 20,
    "temperature": 0,
    "max_output_tokens": 1024,
    "context_budget_tokens": 100000,
    "observation_max_nodes": 50,
    "observation_summary_chars": 300,
    "code_timeout_s": 10
  },
  "element_baselines": {"k_unit": "pages"}
}
```

[PAPER-EXACT] values in this block: `ingestion.render_dpi` (300), `ingestion.temperature` (0),
`ingestion.max_output_tokens` (8192; may be lowered only if a local model's limit requires it, logged),
`community.algorithm` (Louvain), `agent.max_rounds` (20), `agent.temperature` (0). Everything else
is [RECONSTRUCTED]; `ingestion.image_max_side_px` is set per model in CP-4.3B (R2).

## 7. Engineering and spending rules

- **R16** cache: key = sha256(model identifier, messages incl. image hashes, parameters); replies and
  usage stored permanently under `data/processed/ladrag/llm_cache/`.
- Every call logs model id, prompt/completion tokens, latency, VRAM (local) or cost (API).
- **R18** exact model identifiers/revisions/quantization are recorded per run.
- Paid calls pass a budget guard that aborts **before** exceeding the configured budget
  (REPRODUCTION_PROTOCOL §5 hard rules); no paid call without explicit user approval of that experiment.
- API keys only from `.env` (never logged).

## 8. Substitutions and reporting

| # | Component | Paper | LAD-RAG† |
|---|---|---|---|
| S1 | Ingestion VLM (A, D) | GPT-4o | local lightweight VLM chosen in CP-4.3B; [OPTIONAL-REFERENCE] stronger API VLM on 3–5 pages only if approved |
| S2 | Section update model (B) | GPT-4o | same local model as S1 (or a local text LLM; decided in CP-4.3B) |
| S3 | Agent LLM | GPT-4o | scripted (CP-4.6A) → local LLM (CP-4.6B) → DeepSeek, limited (CP-4.6C, optional) |
| S4 | Serving | vLLM, 4× A100 | local runtime on Quadro RTX 4000 8 GB; API for optional runs |

Results are reported as LAD-RAG† with the component list, e.g.
`ingestion = <local VLM>; embeddings = E5-large-v2; graph = reconstructed NetworkX; agent = <local | DeepSeek>`.
Primary comparisons are internal, on the same pilot subset: page-text baselines vs. element-summary
baselines vs. graph retrieval vs. dynamic LAD-RAG†. Absolute pilot numbers are never compared with
the paper as if produced under identical conditions.

## 9. Phase 4 checkpoint plan (revised in CP-4.1A)

| CP | Content | Paid API |
|---|---|---|
| CP-4.2 | Graph schema: nodes, edges, graph metadata, working-memory schema, node-link JSON, validation, deterministic IDs, prompt rendering, tests | none |
| CP-4.3A | Ingestion framework with Mock/Scripted VisionModel; end-to-end synthetic PDF → graph; JSON failure/retry/cache/persistence/resume tests | none |
| CP-4.3B | Local VLM feasibility on 3–5 pages (model chosen after an ecosystem check; ≈ 2B–4B class preferred; honest verdict) | none |
| CP-4.3C | Local ingestion calibration on ≈ 20–30 pages (after approval of 4.3B) | none |
| — | [OPTIONAL-REFERENCE] stronger API VLM on 3–5 pages | only with explicit approval |
| CP-4.3D | Pilot graph construction on pilot-v1 with the local model (after approval of 4.3C) | none |
| CP-4.4 | Symbolic retrieval tools + sandbox | none |
| CP-4.5 | Neural index + element-summary baselines (config-driven) | none |
| CP-4.6A | Agent engine with scripted models | none |
| CP-4.6B | Local agent feasibility (7B/8B optional) | none |
| CP-4.6C | Limited DeepSeek agent evaluation: 20 evidence questions, semantic-only vs. full LAD-RAG† | optional; cumulative DeepSeek < USD 5; explicit approval |
| CP-4.7 | Optional ablations (full, w/o C, w/o G, w/o C&G) | optional; explicit approval |

## 10. Resolution of the open questions in PAPER_NOTES §15

| # | Open question | Resolution |
|---|---|---|
| 1 | Embedding model / top-k of neural index | R10: config, defaults E5-large-v2 / 10 |
| 2 | Intra-page relation prompt | R4: deterministic reading-order + layout_relation |
| 3 | `aggregated_section` nodes | R9: not created |
| 4 | Louvain parameters / timing | R8: config, defaults resolution 1.0, seed 0, at ingestion |
| 5 | Edge types vs. undirected graph | R7: types as edge attributes; communities unweighted |
| 6 | Node → page mapping | R1/R14: `page` attribute |
| 7 | Unanswerable questions in metrics | D-008 / D-009 |
| 8 | Table 1 score formula | unknown — Table 1 not reproduced numerically |
| 9 | Baseline k: elements vs. pages | R19: pages (Fig. 3 caption) |
| 10 | Context-window handling | R11 + R15 (config) |
| 11 | How QA consumes evidence | deferred with the QA stage |
| 12 | ACL vs. arXiv | resolved (numbers identical) |

## 11. Research interpretation

The resource constraint is **not** the thesis contribution. Observations it may produce (e.g.
lightweight ingestion losing cross-page links; agent quality depending strongly on the LLM;
selective multimodal processing preserving quality at lower cost) are recorded as observations or
hypotheses only. The research problem remains undecided until the Phase 5–6 failure analysis.
