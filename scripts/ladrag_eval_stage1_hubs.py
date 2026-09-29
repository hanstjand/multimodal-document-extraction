"""Post-hoc descriptive failure analysis for EVAL-0001 (CP-4.5A): which cross-page neighbours do the
semantic seeds reach? Gold-free (uses only the saved rankings and the graphs); nothing is tuned.

Usage:
  python scripts/ladrag_eval_stage1_hubs.py
Writes experiments/ladrag/results/eval/EVAL-0001-stage1/hub_analysis.json.
"""

import json
from collections import Counter
from pathlib import Path

from multimodal_document_extraction.studies.ladrag.graph_retrieval import (
    SCOPE_CROSS_PAGE,
    GraphIndex,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph

ROOT = Path("data/processed/ladrag/graphs/ING-0001-stage1-qwen3.5-2b-1280")
OUT = Path("experiments/ladrag/results/eval/EVAL-0001-stage1")


def main() -> None:
    rows = [json.loads(line) for line in (OUT / "rankings.jsonl").read_text("utf-8").splitlines()]
    indices: dict[str, GraphIndex] = {}
    edge_types, node_types, targets = Counter(), Counter(), Counter()
    earlier = later = 0
    for row in rows:
        doc = row["doc_id"]
        if doc not in indices:
            indices[doc] = GraphIndex(DocumentGraph.load(ROOT / doc / "graph.json"))
        ix = indices[doc]
        for seed in row["seed_nodes"]:
            for n in ix.neighbors(seed, SCOPE_CROSS_PAGE):
                edge_types.update(n.types)
                node_types[ix.node(n.node_id).get("type")] += 1
                targets[f"{doc}:{n.node_id}"] += 1
                if n.page < ix.node_page(seed):
                    earlier += 1
                else:
                    later += 1
    top_degree = {}
    for doc, ix in sorted(indices.items()):
        ranked = sorted(
            ((len(ix.neighbors(n, SCOPE_CROSS_PAGE)), n) for n in ix.nodes_in_order()),
            key=lambda x: -x[0],
        )[:3]
        top_degree[doc] = [
            {"node_id": n, "cross_page_degree": k, "type": ix.node(n).get("type")}
            for k, n in ranked
        ]
    result = {
        "questions": len(rows),
        "seed_cross_page_links": earlier + later,
        "links_to_earlier_pages": earlier,
        "links_to_later_pages": later,
        "edge_types": dict(edge_types.most_common()),
        "neighbour_node_types": dict(node_types.most_common()),
        "most_frequent_neighbour_nodes": dict(targets.most_common(10)),
        "top_cross_page_degree_per_document": top_degree,
    }
    (OUT / "hub_analysis.json").write_text(json.dumps(result, indent=1) + "\n", "utf-8")
    print(json.dumps(result, indent=1))


if __name__ == "__main__":
    main()
