# Paper Notes — LAD-RAG

**Citation:** Zhivar Sourati, Zheng Wang, Marianne Menglin Liu, Yazhe Hu, Mengqing Guo,
Sujeeth Bharadwaj, Kyu Han, Tao Sheng, Sujith Ravi, Morteza Dehghani, Dan Roth.
*LAD-RAG: Layout-aware Dynamic RAG for Visually-Rich Document Understanding.* ACL 2026 (long).
USC + Oracle AI.

**Study:** Study 01 of the Multimodal Document Extraction research (see `docs/PROJECT_CONTEXT.md`).

**Local file:** `papers/ladrag/2026.acl-long.724.pdf` — 24 pages, **ACL 2026 camera-ready**:
*Proceedings of the 64th Annual Meeting of the ACL (Volume 1: Long Papers)*, pages 15945–15968,
July 2–7, 2026 (PDF produced by pdfTeX, 2026-06-09). Replaced the earlier arXiv v2 copy on
2026-09-27. Page references below ("p.N") are PDF page N = proceedings page 15944+N.

**Differences vs. arXiv v2 (`arXiv:2510.07233v2`, checked 2026-09-27):** all 694 three-decimal
numbers in the text/tables are identical; text changes are copy-edits except
(a) QA evaluation wording (§3.3, see §11 below) and (b) App. A no longer promises a code release.

All numbers in this file are **[PAPER]** numbers. None of them are our results.

---

## 1. Motivation (§1, p.1–3)

Conventional RAG over visually-rich documents (VRDs) has three limitations:

1. **Loss of layout and structural context.** Chunks are encoded in isolation; cross-page
   continuity and layout hierarchies are lost. Example: "How many businesses are shown as
   examples of transformation by big data?" — retriever returns only the title slide, missing the
   following pages with the examples.
2. **Over-reliance on embeddings.** Queries relying on symbolic/structural cues (chart
   references, page numbers, table sources) are poorly served. Example: "How many charts and tables
   in this report are sourced from Annual totals of Pew Research Center survey data?"
3. **Static top-k.** Retrieval depth ignores question complexity (3 pages vs. 12 pages needed).

Idea: build a **symbolic document graph** at ingestion alongside a **neural index**, and at
inference use an **LLM agent** that iteratively queries both, choosing semantic, symbolic, or hybrid
retrieval, with no fixed k.

## 2. Ingestion pipeline (§2.1, p.3; App. H)

- An LVLM (**GPT-4o**) processes the document **page by page, in order**.
- For each page it extracts **all visible elements** with self-contained descriptions → graph nodes.
- A **running memory M** accumulates document-level state across pages.
- Each new page's elements are linked to relevant parts of M → inter-page edges.
- After the full pass: document graph **G** (intra + inter-page structure), stored as
  (a) the symbolic graph object and (b) a neural index over node summaries.
- Page rendering: **PyMuPDF at 300 DPI**; downscaled to 50% (rarely 20%) under GPU memory limits.
- Ingestion is offline, once per document; it does not affect inference latency.

Inferred per-page procedure (from the prompts in Figs. 9–11; order is our reading, not stated explicitly):
1. Node extraction prompt (Fig. 9) on the page image → JSON list of objects.
2. Section-like objects on the page → memory-update prompt (Fig. 10) → updated `section_queue`.
3. Graph-construction prompt (Fig. 11) with current page objects, **current page relationships**
   (intra-page), working memory, and the page image → `updated_memory` + `cross_page_relationships`.

## 3. Graph nodes (§2.1; Fig. 9)

Each node = a localized element on a page (paragraph, figure, table, section title, footnote, ...).
Fields in the extraction prompt:

| Field | Description |
|---|---|
| `type` | title, section_header, paragraph, figure, table, footnote, metadata, etc. |
| `content` | full raw content; for tables/figures includes captions, data values, axis labels, legends |
| `title_or_heading` | short heading of the object |
| `position_on_page` | e.g. 'top-left', 'center-bottom' |
| `layout_relation` | position relative to other elements ('below the main title') |
| `summary` | complete, self-contained summary usable when retrieved alone |
| `visual_attributes` | font size, emphasis, colour, spacing |
| `page_metadata` | document_title, page_number, watermark, source_url |
| `object_id` | unique, prefixed by a given prefix, e.g. `{prefix}-obj_003` |
| `content_type` (opt.) | 'contact_info', 'citation', 'statistical_summary', ... |
| `document_context` (opt.) | brief broader-context reference |

Node types listed in the agent prompt (Fig. 12): aggregated_section, paragraph, section_header, title,
figure, metadata, table, footnote, footer, list, note, quote, citation, link, contact_info, code,
warning, map, page_number, code_block.
Object ID format (Fig. 12): `[main folder]/[document]/page_[page number]-obj_[object number]`.

## 4. Graph edges (§2.1; Fig. 11)

Edges encode symbolic, layout, or semantic relationships:
- **Reference** relationships (paragraph → figure, footnote → section).
- **Layout/structural** relationships (same section, cross-page continuation).

Edge types explicitly named in Fig. 11:
- `is_part_of_section` — every object on the current page → most relevant section/subsection in
  `section_queue` (prefer leaf; may link to both leaf and parent).
- `explains` — e.g. paragraph explains a table on an earlier page.
- Object-level semantic links: `continues`, `references`, `summarizes`, `updates`, ... (open set).

The graph used at inference is an **undirected NetworkX** graph (Fig. 12).

## 5. Running memory (§2.1; Figs. 10–11)

Structure of working memory M:
- `section_queue` — hierarchical list from top-level section to deepest subsection; elements are
  `{text, object_id}` dicts or lists of sibling dicts. Updated by a dedicated prompt (Fig. 10):
  append as subsection / truncate to a broader level and insert / leave unchanged. Rule: deeper items
  must never come from earlier pages than their parents.
- `active_entities` — important entities persisting across pages, with object_id(s).
- `semantic_topics` — core topics continuing across pages.
- `unresolved_objects` — objects referred to but not yet explained (placeholders).

## 6. Neural index E (§2.1)

Vector index over the **self-contained summaries** of all nodes; semantic similarity search.
The agent's `do_semantic_search` matches "wrt their summary and content" (Fig. 12).
**Embedding model and top-k for this index are not specified.**

## 7. Symbolic graph G (§2.1)

Graph with node/edge properties (type, location, visual attributes) and local + global relations.
Global structure: **Louvain community detection** (Blondel et al., 2008) groups nodes into communities.

## 8. Retrieval agent (§2.2; Fig. 12)

- LLM agent = **GPT-4o**, temperature 0.
- Given q: produce a numbered **plan** (semantic / symbolic / hybrid), then iterate steps; each step
  emits a Python code snippet which the harness executes and returns results for.
- Step keywords: `semantic_search`, `graph_filter`, `graph_contextualize`, `DONE`.
- Termination: (i) nearing context window, (ii) max steps (**20 rounds**), (iii) agent says DONE.
- Final output: list of selected node IDs.
- Prompt explicitly says **prioritize recall over precision** (e.g. return all figures rather than
  over-filtering).
- Output format: `<plan>...</plan>` then `<step><description/><step_keyword/><code/></step>`.

### 8.1 NeuroSemanticSearch(query)
`do_semantic_search(query, pdf_name)` — embedding similarity over the neural index using an
agent-composed query (may be called multiple times for sub-queries).

### 8.2 SymbolicGraphQuery(query_statement)
Agent writes a Python **expression** over `doc_graph`, e.g.
`[(node_id, node) for node_id, node in doc_graph.nodes(data=True) if ...]`
(filter by type, section, page, ...). Missing keys must be handled gracefully.
**Security note for our reimplementation:** this is LLM-generated code execution → must be sandboxed.

### 8.3 Contextualize(node)
`get_community_for_node(node_id, doc_graph)` — returns all nodes in the node's **Louvain community**.
§2.2 also mentions "local neighborhoods"; the prompt only exposes community membership.

## 9. Datasets (§3.1; App. B)

| Dataset | Docs | Questions | Avg pages | Notes |
|---|---|---|---|---|
| **MMLongBench-Doc** | 135 PDFs | 1,082 | 47.5 (~21k tokens) | 33% cross-page; text/image/chart/table/layout evidence; Apache-2.0 |
| LongDocURL | 396 | 2,325 | 86 (~43k tokens) | 52.9% multi-page, 37.1% cross-element; Apache-2.0 |
| DUDE | ~5k | — | 5.7 | only extractive subset has evidence pages; ~1% multi-page; CC BY 4.0 |
| MP-DocVQA | 5,928 | 46k | ~8 | evidence always single page; scanned; MIT |

## 10. Baselines (§3.2)

- Text retrievers: **E5-large-v2**, **BGE-large-en**, **BM25** (bm25s, Lù 2024).
- Image retriever: **ColPali** (≈ M3DocRAG backbone).
- Hierarchical: **RAPTOR**.
- Text baselines operate over **summaries of all extracted page elements** (i.e., LAD-RAG's
  ingestion output), top-k elements; k swept up to perfect recall (avg. k=94 MMLongBench,
  65 LongDocURL, 17 DUDE, 10 MP-DocVQA; App. H.1).
- Ablations: w/o Contextualize (C), w/o GraphQuery (G), w/o both (= agent over neural index only,
  akin to SimpleDoc).

## 11. Metrics (§3.3)

Gold evidence pages P = {p1..pn}; retrieved pages P̂.
- **Perfect Recall:** PR = 1 if P ⊆ P̂ else 0.
- **Irrelevant Pages Ratio:** IPR = |P̂ \ P| / |P̂| (lower is better).
- Table 1 uses "ratio of perfect recall to irrelevant page retrievals" as a single score —
  **exact formula not given**.
- **QA accuracy:** following MMLongBench / LongDocURL — GPT-4o extracts a concise answer
  **from the QA models' outputs** (ACL wording; arXiv v2 said "from retrieved content"), then a
  rule-based comparison gives binary correctness. Human eval (App. G, 100 samples): judge vs.
  annotators accuracy 0.93 / 0.95, κ 0.86 / 0.90.
- QA models: Phi-3.5-Vision-4B, Pixtral-12B-2409, InternVL2-8B, GPT-4o; greedy decoding.
  Settings: LAD-RAG evidence, best baseline @5, @10, top-k-adjusted (same #pages as LAD-RAG),
  ground-truth pages (oracle). Full-document baselines: mPLUG-DocOwl1.5-8B, Idefics2-8B,
  MiniCPM-Llama3-V2.5-8B.

## 12. Key reported results — [PAPER]

- LAD-RAG: **>90% perfect recall on average** across the 4 datasets without top-k tuning.
- At equal IPR, PR gain over baselines ≈ 20% (MMLongBench), 15% (LongDocURL), 10% (DUDE, MP-DocVQA).
- Baselines need on average k=22 (MMLongBench), 27 (LongDocURL), 10 (DUDE), 5 (MP-DocVQA) to match LAD-RAG recall.
- Table 1 (PR/IPR ratio score, higher better), MMLongBench / LongDocURL:
  LAD-RAG 0.979 / 0.895; w/o C 0.957 / 0.819; w/o G 0.856 / 0.809; w/o C&G 0.840 / 0.774;
  RAPTOR 0.877 / 0.853; ColPali 0.831 / 0.791; BM25 0.728 / 0.762; E5-Large 0.791 / 0.769;
  BGE-Large 0.743 / 0.704.
- Table 2, MMLongBench-Doc QA accuracy (all / single / multi):
  - GPT-4o: GT 0.696/0.693/0.565; @5 0.575/0.607/0.303; @10 0.610/0.637/0.372;
    topk-adj 0.593/0.629/0.409; **LAD-RAG 0.625/0.676/0.450**.
  - InternVL2-8B: GT 0.399/0.506/0.250; @5 0.287/0.372/0.164; @10 0.319/0.395/0.208;
    topk-adj 0.304/0.365/0.212; LAD-RAG 0.448/0.495/0.242.
  - (Pixtral-12B and Phi-3.5-Vision rows in Table 2, p.8.)
- Figure 3 (PR vs. IPR curves) is an image; values not extractable as text.
- Latency: agent typically 2–5 LLM calls per query (Fig. 4); >97% of calls generate <100 tokens (App. F).

## 13. Implementation details (App. H)

- Graph: Python **networkx**. Community detection: Louvain.
- Serving: **vLLM 0.9.2**; 4× NVIDIA **A100**; Python **3.10.12**; PyTorch **2.7.0+cu126**.
- Temperature 0 everywhere (graph construction, agent, QA).
- Max tokens: **8192** for graph construction steps (extraction, memory updates, relation extraction);
  **2048** for QA.
- Agent max rounds: **20**.
- Pages rendered with PyMuPDF at 300 DPI.
- Prompts: Fig. 9 (node extraction), Fig. 10 (section_queue update), Fig. 11 (graph construction /
  cross-page relations), Fig. 12 (retriever agent).
- **Code not released** (App. A: "undergoing institutional review and legal clearance prior to public
  release"; the ACL version drops the arXiv v2 promise to add a repository link / share on request).
  Reproduction must rely on the paper's descriptions and prompts (App. H).
- InternVL2-8B gave comparable extraction quality to GPT-4o on manual inspection of dozens of docs;
  GPT-4o chosen for instruction following / structured output (§7).

## 14. Limitations (§7)

- Focus is retrieval; LVLMs still under-use near-perfect evidence (GT QA is far from 100%).
- Depends on a strong LVLM for ingestion; may struggle with noisy inputs, complex layouts,
  low-quality scans (DUDE, MP-DocVQA contain scans).
- Ingestion cost: per-page GPT-4o calls; authors suggest smaller models / OCR for extraction in
  cost-sensitive settings, with LVLMs reserved for cross-page linking.
- Trade-off unified model vs. specialized modular pipelines.

## 15. Open questions / unspecified details (to resolve in CP-4.1)

1. Embedding model for the LAD-RAG neural index; top-k returned by `do_semantic_search`.
2. Intra-page relation extraction: Fig. 11 consumes "CURRENT PAGE RELATIONSHIPS" but no prompt
   for producing them is shown.
3. How `aggregated_section` nodes are created.
4. Louvain parameters (resolution, random seed, weights); whether communities are computed once
   at ingestion (App. C suggests yes) or on demand.
5. Whether edges are typed attributes on an undirected graph and whether edge types affect communities.
6. Node → page mapping for PR/IPR (presumably from object_id `page_N`).
7. Handling of **unanswerable** questions (empty P ⇒ PR trivially 1) in retrieval metrics.
8. Exact formula for the Table 1 "PR to IPR ratio" score.
9. Baseline retrieval unit: text baselines use element summaries; ColPali presumably page images —
   how element-level top-k maps to page-level top-k on the Figure 3 x-axis.
10. Context-window handling when agent observations (node lists) are large.
11. How the QA stage consumes retrieved evidence (page images of retrieved pages vs. node text).
12. ~~Whether the ACL camera-ready differs from arXiv v2.~~ Resolved 2026-09-27: numbers identical;
    see header of this file.
