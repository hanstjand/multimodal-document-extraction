# LAD-RAG† Implementation Specification (CP-4.1)

Status: **draft for user approval** (2026-09-27). Decision record: D-018 (Proposed).
Scope: what Phase 4 will build, derived from the paper (`PAPER_NOTES.md`), its figures, and the
verbatim prompts (`src/multimodal_document_extraction/studies/ladrag/prompts/`), within the resource
strategy of `REPRODUCTION_PROTOCOL.md` (D-011). No code is written in CP-4.1.

Labels: **[P]** stated in the paper · **[F]** visible only in a paper figure · **[R#]** our
reconstruction (paper silent) — each R item needs approval.

---

## 1. New evidence from the paper's figures (not in the text)

| Finding | Source | Consequence |
|---|---|---|
| Node IDs used by the agent look like `page_22-obj_002` (no document prefix), e.g. `get_community_for_node("page_22-obj_002", doc_graph)` | [F] Fig. 6 | per-document graphs with short IDs (R1) |
| Graph filter used for charts: `node.get('type') == 'figure'` — charts are typed `figure` | [F] Fig. 5 | node attributes are plain dict keys; `type` values as extracted |
| Relation categories: structural hierarchy, content/section grounding, cross-page references, semantic continuation | [F] Fig. 2 | matches Fig. 11 edge types |
| Fig. 3 axes: x = Irrelevant Pages Ratio, y = Perfect Recall; baselines trace k = 1…; LAD-RAG is a single point | [F] Fig. 3 | our reporting: PR-vs-IPR curves + LAD-RAG† point |
| LAD-RAG on MMLongBench-Doc at ≈ **PR 0.83, IPR 0.79** (read off the plot, ±0.01) | [F] Fig. 3 | target operating point; paper's "> 90% PR on average" averages 4 datasets |
| Baseline k labels on MMLongBench: E5 20, ColPali 17, BM25 24, BGE 38, RAPTOR 11 (mean 22 = text's "k = 22"); caption calls k "the number of retrieved pages" | [F] Fig. 3 | page-level k for element baselines (R19) |

Values read from figures are `[PAPER-FIG]` approximations and are recorded as such in
`experiments/ladrag/results/paper_reported.csv` when that file is created (CP-4.6).

## 2. Pipeline overview

```
PDF ──render(300 DPI)──► page image ─┐
                                      ├─► [A] node extraction (Fig. 9, image)      → page objects (nodes)
                                      │   [B] section_queue update (Fig. 10)        → memory.section_queue
                                      │   [C] intra-page relations (R4, no LLM)     → intra-page edges
                                      └─► [D] graph construction (Fig. 11, image)   → memory + cross-page edges
 after last page:  NetworkX graph  ─► Louvain communities (R8)   ─► symbolic index G
                   node texts       ─► embeddings (R10)           ─► neural index E
 question ─► agent (Fig. 12) ◄─► tools {do_semantic_search, doc_graph filter, get_community_for_node}
          ─► selected node IDs ─► pages P̂ ─► PR / IPR (D-008/D-009)
```

LLM calls per page: A (always, image), B (only if the page has section-like objects), D (always,
image). Ingestion is cached and done once per (document, ingestion model) (R16).

## 3. Ingestion

### 3.1 Page images
- [P] PyMuPDF at 300 DPI.
- **R2** Before sending, downscale so the longer side is ≤ 2048 px (to my knowledge the OpenAI API
  resizes to this bound for `detail="high"` anyway — to be verified against the current API docs in
  CP-4.3), PNG, `detail="high"`. Rendering DPI and sent size are logged.

### 3.2 [A] Node extraction — Fig. 9 [P]
- Prompt: `fig09_node_extraction.txt`, `.format(prefix, prefix)`; user message = prompt text + page
  image. Temperature 0, max tokens 8192 [P].
- **R1** IDs: one graph per document; `prefix = "page_{n}"` (1-based physical page, D-007), so node IDs
  are `page_{n}-obj_{k:03d}` as in Fig. 6. After parsing, IDs that do not start with the prefix or are
  duplicated are reassigned deterministically in output order (count logged).
- Node attributes = extracted fields (`type`, `content`, `title_or_heading`, `position_on_page`,
  `layout_relation`, `summary`, `visual_attributes`, `page_metadata`, `content_type`,
  `document_context`) + ours: `page` (int), `doc_id`, `object_id`, `order_on_page`.
- **R17** Output parsing: strip Markdown code fences, parse the first JSON list. If invalid: one repair
  call with the same messages plus "Your previous output was not valid JSON. Return only the JSON
  list." If still invalid, the page gets no nodes and is flagged. Invalid-JSON rate per model is a
  calibration criterion (> 10% → switch model, protocol §4).

### 3.3 [B] Running memory: `section_queue` — Fig. 10 [P]
- **R3** Candidate section objects = nodes of the page with `type` ∈ {`title`, `section_header`},
  passed as `[{"text": title_or_heading or content, "object_id": ...}]`. No candidates → no call,
  memory unchanged.
- Placeholders rendered with `json.dumps(..., indent=2)` exactly as printed.
- **R6** Initial memory: `{"section_queue": [], "active_entities": [], "semantic_topics": [],
  "unresolved_objects": []}`.

### 3.4 [C] Intra-page relationships — **R4** (prompt not published)
Deterministic, no LLM call:
- `next_on_page` edge between consecutive objects in extraction order (reading-order adjacency);
- the per-object `layout_relation` strings from [A].
Both are serialized as a JSON list into `{extracted_relations_text}` of Fig. 11; `next_on_page`
edges are also added to the graph (they are intra-page structure, §2.1 of the paper).
Alternative (not chosen): a fourth, reconstructed LLM prompt per page (+~33% cost).

### 3.5 [D] Graph construction — Fig. 11 [P]
- Inputs: `{extracted_objects_text}` = **R5** JSON list of the page's nodes (all extracted fields);
  `{extracted_relations_text}` = R4; `{json.dumps(working_memory, indent=2)}`; page image.
- Output: `updated_memory` (replaces memory, **except** `section_queue`, which is forced to the result
  of [B] — the prompt says not to change it) and `cross_page_relationships`.
- **R7** Edges: keep relationships whose endpoints both exist (current or earlier pages); drop
  self-loops and unknown IDs (counts logged). Undirected `networkx.Graph` [P]; parallel relations are
  merged into edge attributes `types` (sorted list) and `sources` (`fig11`, `intra_page`).
- Memory growth is not capped (faithful); prompt tokens per page are logged to detect blow-up.

### 3.6 After the last page
- **R8** Communities: `networkx.community.louvain_communities(G, weight=None, resolution=1.0,
  seed=0)` [P: Louvain; parameters ours], computed once; `community` id stored on every node;
  isolated nodes are singletons.
- **R9** `aggregated_section` nodes (named in Fig. 12, construction unpublished): **not created**; the
  type name stays in the verbatim prompt.
- **R10** Neural index: E5-large-v2 (pinned, D-016) over node text `summary + "\n" + content`
  (fallback to whichever exists), same MaxP windows; cosine similarity.
- Persisted per document: `graph.json` (node-link data), `memory_trace.jsonl` (memory after each
  page), `calls.jsonl` (every LLM call: model, tokens, latency, cache key), embeddings `.npy`.

## 4. Retrieval agent — Fig. 12 [P]

- Prompt: `fig12_retriever_agent.txt`, `.format(doc_id, question)`; sent as the first user message;
  temperature 0 [P]; max 20 rounds [P]; **R15** max output tokens per call 1024 (not published).
- Loop: parse the reply for `<step>` → `<step_keyword>` and `<code>`; execute the first step's code;
  send back **R11** a compact observation; repeat. Stop on `DONE`, 20 rounds [P], or a context budget
  (**R15**: 100k prompt tokens) [P: "nearing the context window"].
- **R11** Observation format (unpublished): one line per node
  `object_id | type | page | title_or_heading | summary[:300]`, at most 50 nodes per observation with
  a truncation note; errors are returned as `ERROR: <message>`.
- **R12** Final answer: `ast.literal_eval` of the DONE `<code>` → list of node IDs (strings or
  `(id, attrs)` pairs). If DONE is missing or unparseable, fall back to the union of all nodes
  returned by tool calls, in first-seen order (consistent with the prompt's recall-first instruction);
  fallbacks are counted.
- **R13** Sandbox for LLM-written code: parse with `ast` in `eval` mode (expressions only, as the
  prompt demands); reject names/attributes starting with `_`; restricted builtins (`len, set, list,
  dict, tuple, sorted, any, all, str, int, float, bool, min, max, sum, enumerate, range, zip,
  isinstance, round`); namespace = `{doc_graph (frozen), do_semantic_search, get_community_for_node}`;
  10 s timeout. Violations are returned to the agent as errors.
- Tools:
  - `do_semantic_search(query, pdf_name)` → **R10** top-**10** nodes by cosine (k unpublished).
  - graph filter → the evaluated expression (list of nodes / `(id, attrs)` pairs).
  - `get_community_for_node(node_id, doc_graph)` → all nodes in the node's community [P].
- **R14** Output: nodes in DONE order → `RetrievalResult` with `unit_type="node"`, ranks in output
  order (D-007); pages from node attribute `page`; metrics per D-008/D-009.
- Ablations [P]: **R20** "w/o C" removes `get_community_for_node` from the namespace and deletes the
  lines describing operation 3 / `graph_contextualize` from the prompt; "w/o G" likewise for graph
  filtering; "w/o C & G" = semantic search only.

## 5. Paper-style baselines on element summaries (after ingestion)

- `bm25-elements`, `dense-e5-elements`, `dense-bge-elements`: rank nodes by their text (R10 text).
- **R19** k counts retrieved **pages** (Fig. 3 caption): cut the node ranking at the first k distinct
  pages (`pages_in_rank_order`), so curves are comparable with page-text baselines and Fig. 3.
- ColPali and RAPTOR remain deferred (D-011).

## 6. Engineering rules

- **R16** LLM cache: key = sha256 of (model, messages incl. image hashes, parameters); cached replies
  and usage stored under `data/processed/ladrag/llm_cache/`; re-runs are free and deterministic.
- Every call logs prompt/completion tokens and latency (EXPERIMENT_PROTOCOL `token_usage`).
- **R18** Exact model snapshot returned by the API is recorded (e.g. `gpt-4o-2024-08-06`); models
  and prices re-checked before any spending (D-011).
- Budget guard: ingestion refuses to start if the estimated cost of the job exceeds the remaining
  budget under the 80% stop rule (D-011).
- API keys only from `.env` (never logged).

## 7. Resolution of the open questions in PAPER_NOTES §15

| # | Open question | Resolution |
|---|---|---|
| 1 | Embedding model / top-k of neural index | R10: E5-large-v2, top-10 |
| 2 | Intra-page relation prompt | R4: deterministic reading-order + layout_relation |
| 3 | `aggregated_section` nodes | R9: not created |
| 4 | Louvain parameters / timing | R8: resolution 1.0, seed 0, unweighted, at ingestion |
| 5 | Edge types vs. undirected graph | R7: types as edge attributes; communities unweighted |
| 6 | Node → page mapping | R1/R14: `page` attribute (from ID prefix) |
| 7 | Unanswerable questions in metrics | D-008/D-009 |
| 8 | Table 1 score formula | still unknown — Table 1 not reproduced numerically; ablations reported as PR/IPR |
| 9 | Baseline k: elements vs. pages | R19: pages (Fig. 3 caption) |
| 10 | Context-window handling | R11 caps + R15 budget |
| 11 | How QA consumes evidence | deferred with the QA stage (D-011) |
| 12 | ACL vs. arXiv | resolved (numbers identical) |

## 8. Phase 4 checkpoint plan

| CP | Content | API spend |
|---|---|---|
| CP-4.2 | Graph schema: node/edge dataclasses, node-link JSON I/O, validation, prompt renderer + tests | none |
| CP-4.3 | Ingestion pipeline (A–D, R1–R8, R16–R18) with mock LLM tests; then calibration on `calib-v1` with GPT-4o and gpt-4o-mini (≈ 33 pages each); choose ingestion model; ingest `pilot-v1` | ≈ $1.5–3.5 (OpenAI) |
| CP-4.4 | Symbolic retrieval: graph filter sandbox (R13), `get_community_for_node` + tests | none |
| CP-4.5 | Neural index + `do_semantic_search`; element baselines (R19) evaluated on pilot | none (local GPU) |
| CP-4.6 | Agent loop (R11–R15, R20), local-model development, pilot evaluation with DeepSeek (full + 3 ablations), CMP vs. baselines | ≈ $1–3 (DeepSeek) |
