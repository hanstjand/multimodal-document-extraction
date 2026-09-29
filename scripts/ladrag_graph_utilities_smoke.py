"""Read-only structural smoke test of the CP-4.4 graph utilities on the Stage-1 graphs.

Loads every graph of a run, exercises neighbour queries (all / cross-page / intra-page), the ordered
one-hop expansion, community lookup and the AST sandbox, and checks internal consistency and the
cross-page edge counts against the persisted graph-check report. Uses NO gold evidence, computes no
retrieval metric; seeds for the expansion check are simply the first nodes in node ID order.

Usage:
  python scripts/ladrag_graph_utilities_smoke.py [RUN_ID]
Writes experiments/ladrag/results/ingestion/<RUN_ID>-graph-utilities-smoke.json (committed).
"""

import json
import sys
import time
from pathlib import Path

from multimodal_document_extraction.studies.ladrag.graph_query import GraphQueryEngine
from multimodal_document_extraction.studies.ladrag.graph_retrieval import (
    SCOPE_ALL,
    SCOPE_CROSS_PAGE,
    SCOPE_INTRA_PAGE,
    GraphIndex,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "ING-0001-stage1-qwen3.5-2b-1280"
ROOT = Path("data/processed/ladrag/graphs") / RUN_ID
RESULTS = Path("experiments/ladrag/results/ingestion")
PAPER_FILTER = (
    "[(node_id, node) for node_id, node in doc_graph.nodes(data=True) "
    "if node.get('type') == 'figure']"
)


def main() -> None:
    check = json.loads((RESULTS / f"{RUN_ID}-graph-check.json").read_text(encoding="utf-8"))
    rows, ok = {}, True
    for doc_dir in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        started = time.perf_counter()
        graph = DocumentGraph.load(doc_dir / "graph.json")  # validates the whole graph
        index = GraphIndex(graph)  # validates page attribute vs node ID
        nodes = index.nodes_in_order()
        degree = {
            s: sum(len(index.neighbors(n, s)) for n in nodes)
            for s in (SCOPE_ALL, SCOPE_CROSS_PAGE, SCOPE_INTRA_PAGE)
        }
        edges = {s: len(index.edges(s)) for s in (SCOPE_ALL, SCOPE_CROSS_PAGE, SCOPE_INTRA_PAGE)}
        persisted = check["documents"][doc_dir.name]["cross_page_edges"]
        seeds = nodes[:10]
        expansion = index.ordered_one_hop_expansion(seeds, scope=SCOPE_CROSS_PAGE)
        repeat = index.ordered_one_hop_expansion(seeds, scope=SCOPE_CROSS_PAGE)
        community_sizes = sorted(
            {index.community_of(n): len(index.get_community_for_node(n)) for n in nodes}.values()
        )
        engine = GraphQueryEngine.for_graph(index)
        figures = engine.evaluate(PAPER_FILTER)
        checks = {
            "degree_sums_equal_2x_edges": all(degree[s] == 2 * edges[s] for s in degree),
            "cross_plus_intra_equals_all": edges[SCOPE_CROSS_PAGE] + edges[SCOPE_INTRA_PAGE]
            == edges[SCOPE_ALL],
            "all_edges_equal_graph_edges": edges[SCOPE_ALL] == graph.graph.number_of_edges(),
            "cross_page_edges_equal_graph_check": edges[SCOPE_CROSS_PAGE] == persisted,
            "expansion_deterministic": expansion == repeat,
            "expansion_unique_nodes": len({i.node_id for i in expansion}) == len(expansion),
            "communities_cover_all_nodes": sum(community_sizes) == len(nodes),
            "figure_filter_matches_types": len(figures)
            == sum(index.node(n).get("type") == "figure" for n in nodes),
        }
        ok &= all(checks.values())
        rows[doc_dir.name] = {
            "nodes": len(nodes),
            "edges": edges,
            "cross_page_edges_graph_check": persisted,
            "expansion_from_first_10_nodes": {
                "items": len(expansion),
                "pages": len(index.pages_of(i.node_id for i in expansion)),
            },
            "communities": len(community_sizes),
            "largest_community": community_sizes[-1],
            "singleton_communities": sum(s == 1 for s in community_sizes),
            "figure_nodes_via_sandbox": len(figures),
            "checks": checks,
            "seconds": round(time.perf_counter() - started, 2),
        }
    result = {"run_id": RUN_ID, "all_checks_passed": ok, "documents": rows}
    out = RESULTS / f"{RUN_ID}-graph-utilities-smoke.json"
    out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, indent=1))
    print(f"written {out}")
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
