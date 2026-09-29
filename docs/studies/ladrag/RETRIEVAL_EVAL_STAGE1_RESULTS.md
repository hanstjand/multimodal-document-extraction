# retrieval-eval-v1 Stage 1 — results (CP-4.5A, EVAL-0001) [REPRO]

Date: 2026-09-29. Protocol: `RETRIEVAL_EVAL_V1.md` (frozen, D-021) — unchanged. Plan:
`experiments/ladrag/configs/EVAL-0001-stage1.json`. Outputs (committed):
`experiments/ladrag/results/eval/EVAL-0001-stage1/` — `rankings.jsonl` (gold-free, hashed before gold
was loaded), `per_question.jsonl`, `aggregates.json`, `comparisons.json`, `diagnostics.json`,
`baselines.json`, `hub_analysis.json`, `run_meta.json`. Code: `scripts/ladrag_eval_stage1.py`,
`src/.../studies/ladrag/expansion_eval.py` (6 tests), `scripts/ladrag_eval_stage1_hubs.py`.

**Stage 1 is exploratory / diagnostic: 5 documents, 35 evidence questions (18 multi-page). All
intervals below are descriptive; no significance or confirmatory claim is made.** All numbers are
[REPRO] (our LAD-RAG† reproduction on MMLongBench-Doc); none is comparable to [PAPER] values.

## 0. Setup and validation

- Graphs: ING-0001 (hashes checked against NIDX-0001). Seeds: saved NIDX-0001 `e5-large-v2-r10`
  index (R10 text, 512/64 windows, MaxP, frozen tie-breaking), top m = 10 nodes.
- Provenance: EVAL-0001 ran from an uncommitted working tree based on `5eaff0e` (code hashes in
  `run_meta.json`); NIDX-0001 was run from a tree based on `d583c03` and committed as `5eaff0e`.
- Phase 1 computed every ranking from question text only and persisted it (SHA-256
  `aa2ac657…`) before gold was loaded; the file was unchanged afterwards.
- Assertions passed before any aggregate was written: A == C at page level for every question and k;
  all pages within document bounds; no duplicate pages; exactly min(k, pages) pages (always k);
  A/B/C/D share the same seed ranking (A's prefix = seed pages); graph/index hashes match; all 35
  evidence questions have valid gold pages; no gold page without nodes (pipeline consistent).
- Runtime 35.5 s, peak VRAM 2.5 GiB, $0 API.
- Diagnostic class precedence (defined in code before running; the frozen outcomes overlap):
  semantic_already_complete → expansion_completes → expansion_adds_some_missing_gold →
  no_expansion_possible → expansion_adds_only_irrelevant; `gold_unreachable` is a separate flag.

## 1. Matched page budget (primary) — PR / IPR

**Multi-page evidence questions (n = 18) — primary subgroup**

| Condition | k = 1 | k = 3 | k = 5 | k = 10 |
|---|---|---|---|---|
| A semantic-only | 0.000 / 0.389 | 0.333 / 0.574 | 0.444 / 0.700 | 0.667 / 0.811 |
| B + graph | 0.000 / 0.389 | 0.167 / 0.667 | 0.333 / 0.733 | 0.611 / 0.828 |
| C intra-page only (= A) | 0.000 / 0.389 | 0.333 / 0.574 | 0.444 / 0.700 | 0.667 / 0.811 |
| D p ± 1 control | 0.000 / 0.389 | 0.333 / 0.630 | 0.500 / 0.711 | 0.778 / 0.800 |

**All evidence questions (n = 35)**

| Condition | k = 1 | k = 3 | k = 5 | k = 10 |
|---|---|---|---|---|
| A | 0.286 / 0.400 | 0.571 / 0.648 | 0.657 / 0.760 | 0.800 / 0.857 |
| B | 0.286 / 0.400 | 0.429 / 0.714 | 0.600 / 0.777 | 0.743 / 0.869 |
| C (= A) | 0.286 / 0.400 | 0.571 / 0.648 | 0.657 / 0.760 | 0.800 / 0.857 |
| D | 0.286 / 0.400 | 0.571 / 0.676 | 0.686 / 0.766 | 0.857 / 0.851 |

Single-page (n = 17): A 0.588 / 0.824 / 0.882 / 0.941 PR at k = 1/3/5/10; B 0.588 / 0.706 / 0.882 /
0.882; D equals A. Source groups (overlapping; Table n = 3 and Layout n = 8 descriptive only): B is
at or below A in every group and k; D ≥ A except Pure-text k = 5, Figure k = 10, Layout k = 3/10.
Full tables: `aggregates.json`.

No-evidence questions (n = 8): every condition returns ≥ 1 page, so NoEvidenceCorrect = 0 and IPR = 1
by construction (not a comparison).

## 2. Unbudgeted view (secondary) — PR / IPR / mean pages returned

| Group | A (seed pages) | B (+ cross-page neighbours) | D (+ p ± 1) |
|---|---|---|---|
| Multi-page (18) | 0.667 / 0.749 / 7.3 | 0.667 / 0.822 / 12.7 | 0.833 / 0.824 / 14.9 |
| All evidence (35) | 0.771 / 0.801 / 7.1 | 0.771 / 0.862 / 12.2 | 0.886 / 0.874 / 14.8 |

Graph expansion adds ≈ 5 pages per question and **no** Perfect Recall in any group; the p ± 1 control
adds ≈ 7.7 pages and raises PR (at a higher IPR). Neither is "better" merely by returning more pages.

## 3. Paired comparisons (exploratory; question bootstrap 95 % interval, 10,000 resamples, seed 0;
document bootstrap = sensitivity only)

Mean PR difference (B − other), win/tie/loss for B:

| Group | Comparison | k = 3 | k = 5 | k = 10 |
|---|---|---|---|---|
| Multi (18) | B − A (= B − C) | −0.167 [−0.333, 0.000], 0/15/3 | −0.111 [−0.278, 0.000], 0/16/2 | −0.056 [−0.167, 0.000], 0/17/1 |
| Multi (18) | B − D | −0.167 [−0.389, 0.056], 1/13/4 | −0.167 [−0.389, 0.056], 1/13/4 | −0.167 [−0.333, 0.000], 0/15/3 |
| All (35) | B − A | −0.143 [−0.257, −0.029], 0/30/5 | −0.057 [−0.143, 0.000], 0/33/2 | −0.057 [−0.143, 0.000], 0/33/2 |
| All (35) | B − D | −0.143 [−0.314, 0.029], 2/26/7 | −0.086 [−0.229, 0.057], 2/28/5 | −0.114 [−0.229, −0.029], 0/31/4 |

k = 1 is identical for all conditions (the first page is always the top seed's page). IPR moves in the
same direction (B higher IPR than A at k = 3/5/10). B never has a PR win over A or C at any k.
Question IDs of every win/loss: `comparisons.json`.

## 4. Graph-reachability diagnostic (frozen §6)

**Multi-page questions (n = 18)**

| # | Count | m = 10 | m = 5 |
|---|---|---|---|
| 1 | semantic-only already complete | 12 | 7 |
| 2 | graph expansion completes an incomplete gold set | **0** | **0** |
| 3 | p ± 1 control completes an incomplete gold set | 3 | 6 |
| 4 | graph succeeds where p ± 1 does not | **0** | **0** |
| 5 | p ± 1 succeeds where graph does not | 3 | 6 |
| 6 | graph adds some missing gold, not all | 3 | 3 |
| 7 | graph adds only irrelevant pages (gold missing) | 3 | 8 |
| 8 | gold unreachable after one-hop graph expansion | 6 | 11 |

m = 10 question IDs: (3)/(5) mmlb-0061-96ccfadc, mmlb-0831-02a2dc3d, mmlb-0832-c9ced344;
(6) mmlb-0061-96ccfadc, mmlb-0673-336693c6, mmlb-0829-b07c235b; (7) mmlb-0831-02a2dc3d,
mmlb-0832-c9ced344, mmlb-0887-6b7da098; (8) all six incomplete questions. m = 5 IDs in
`diagnostics.json`.

Missing gold pages before expansion (multi, m = 10; 14 pages): shortest graph distance from the
seeds 1 → 5, 2 → 4, 3+ → 1, unreachable → 4. The graph recovers 5 of them, 3 of which are also p ± 1 of
a seed page. Per question the graph adds on average 5.4 neighbour pages, 5.1 of them irrelevant.
All 35 evidence questions: 27 semantic-complete at m = 10; graph completes 0; p ± 1 completes 4
(adds mmlb-0830-bb4aa60d).

## 5. Per-document differences (PR, all evidence of the document; n = 5–9, descriptive)

| Document (n) | k = 3 A / B / D | k = 10 A / B / D |
|---|---|---|
| 2305.14160v4 (5) | 0.80 / 0.60 / **1.00** | 1.00 / 1.00 / 1.00 |
| Campaign_038 (6) | 0.67 / 0.50 / 0.50 | 0.83 / 0.67 / 0.67 |
| f8d3a162 (9) | 0.22 / 0.11 / 0.33 | 0.56 / 0.56 / **0.89** |
| mi_phone (7) | 0.57 / 0.57 / 0.71 | 0.86 / 0.86 / 0.86 |
| reportq32015 (8) | 0.75 / 0.50 / 0.50 | 0.88 / 0.75 / 0.88 |

The largest adjacency gain is f8d3 (text-dense administration file with continued lists); graph
expansion never raises a document's PR above A.

## 6. Failure examples

- **mmlb-0829-b07c235b** (f8d3, gold 1–2): seeds on pages 3, 4, 5, 9, 15; the graph adds pages 1 and 13
  (page 1 is gold, one hop away) but page 2 is two hops away; p ± 1 adds 2 but not 1.
- **mmlb-0831 / mmlb-0832** (f8d3, missing page 7): page 7 has a single node with no edge to any seed
  (unreachable); p ± 1 of the seed pages 6/8 recovers it. The graph again only adds pages 1 and 13.
- **mmlb-0887-6b7da098** (mi_phone, gold 6–9): seeds reach page 6; missing pages 7/8/9 are at distance
  2 / 3+ / unreachable; the graph adds pages 1, 5, 13, 14, 25 (all irrelevant).
- **mmlb-0673-336693c6** (Campaign, gold 9, 19, 25–28): the graph adds 17 pages including 9, 19, 26, but
  not 25 (degraded gold page without Fig. 11 output, distance 2) or 27; under a budget its pages
  3, 4, 5 displace the seeds' semantic pages.
- **mmlb-0055-3565de0a** (reportq3, gold 29–30, semantic-complete): at k = 3/5, B inserts pages 1, 3, 4
  (neighbours of the top seed) ahead of the semantically found gold pages → PR loss.

## 7. Post-hoc descriptive analysis (gold-free; `hub_analysis.json`; nothing was tuned)

Across the 43 questions the seeds have 1,046 cross-page neighbour links: 63 % `is_part_of_section`,
22 % `continues`; 59 % of the reached nodes are section headers or titles. A few hub nodes dominate:
f8d3 page 13 (image) and page 1 (title) with 49 cross-page edges each, Campaign p26/p24/p18 (43–46),
mi_phone p1 title (37), 2305 p1 title (23). One-hop expansion therefore mostly returns the same few
front/section pages for every question; combined with the frozen (page, node ID) neighbour order,
low page numbers fill the budget first. Consistent with the CP-4.3C qualitative audit, the generated
`continues` links rarely connect the actual continuation page.

## 8. Reference baselines (secondary; not used to choose anything)

Multi-page PR at k = 1/3/5/10 (page-level k = first appearance of node pages, R19):

| Retriever | Unit / text | PR |
|---|---|---|
| A: E5-large-v2 (primary) | nodes, R10 summary + content | 0.000 / 0.333 / 0.444 / 0.667 |
| BM25 | nodes, element summary | 0.000 / 0.222 / 0.444 / 0.611 |
| E5-large-v2 | nodes, element summary | 0.000 / 0.278 / 0.444 / 0.500 |
| BGE-large-en | nodes, element summary | 0.000 / 0.278 / 0.500 / 0.556 |
| BM25 (Phase 3) | pages, PyMuPDF page text — different unit | 0.000 / 0.167 / 0.333 / 0.389 |
| E5 (Phase 3) | pages, page text — different unit | 0.000 / 0.167 / 0.222 / 0.333 |
| BGE (Phase 3) | pages, page text — different unit | 0.000 / 0.167 / 0.222 / 0.500 |

All-evidence values and IPR: `baselines.json`.

## 9. Interpretation (exploratory)

- On Stage 1 the generated cross-page graph does **not** help retrieve official evidence pages:
  B ≤ A at every k in every subgroup, zero graph-completed gold sets, zero graph-unique successes.
- The simple p ± 1 layout control does at least as well as B everywhere and completes 3 (m = 10) to
  6 (m = 5) multi-page gold sets that the graph does not; there is no evidence that the graph adds
  anything beyond adjacency.
- Likely mechanisms (diagnostic, not proven): hub structure of `is_part_of_section` edges to titles /
  headers, weak `continues` edges, pages with very few nodes, and a neighbour order that favours low
  page numbers.
- With 18 multi-page questions in 5 documents this is a go/no-go signal, not a confirmed effect.
