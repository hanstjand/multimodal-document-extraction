"""Post-ingestion check of Stage-1 graphs for retrieval-eval-v1 (CP-4.3D; read-only, no model, no API).

For every retrieval-eval-v1 evidence question, checks whether each gold page is represented by at
least one graph node, and classifies uncovered gold pages by page status (resource_failure /
ok without nodes, incl. JSON failure). Also summarizes graph size, cross-page edges (origin fig11,
endpoints on different pages), rejected relations, and working-memory growth per page.

Usage:
  python scripts/ladrag_stage1_graph_check.py [RUN_ID]
Writes experiments/ladrag/results/ingestion/<RUN_ID>-graph-check.json (committed).
"""

import json
import sys
from collections import Counter
from pathlib import Path

from multimodal_document_extraction.studies.ladrag.schema import parse_node_id

RUN_ID = sys.argv[1] if len(sys.argv) > 1 else "ING-0001-stage1-qwen3.5-2b-1280"
ROOT = Path("data/processed/ladrag/graphs") / RUN_ID
STATS = Path("experiments/ladrag/results/design/retrieval-eval-v1-stage1-stats.json")
OUT = Path("experiments/ladrag/results/ingestion") / f"{RUN_ID}-graph-check.json"


def _page(node_id: str) -> int:
    return parse_node_id(node_id)[0]


def main() -> None:
    design = json.loads(STATS.read_text(encoding="utf-8"))
    documents, node_pages = {}, {}
    for doc_id in sorted(design["documents"]):
        doc_dir = ROOT / doc_id
        graph = json.loads((doc_dir / "graph.json").read_text(encoding="utf-8"))
        records = [
            json.loads(p.read_text(encoding="utf-8"))
            for p in sorted((doc_dir / "pages").glob("page_*.json"))
        ]
        pages_with_nodes = {n["page"] for n in graph["nodes"]}
        node_pages[doc_id] = pages_with_nodes
        cross = [
            e
            for e in graph["edges"]
            if "fig11" in e["sources"] and _page(e["source"]) != _page(e["target"])
        ]
        cross_relations = [
            r
            for rec in records
            for r in rec["relations"]
            if r["origin"] == "fig11" and _page(r["from_object"]) != _page(r["to_object"])
        ]
        documents[doc_id] = {
            "num_pages": graph["metadata"]["num_pages"],
            "page_records": len(records),
            "status": dict(Counter(r["status"] for r in records)),
            "resource_failed_pages": graph["metadata"]["provenance"].get("resource_failed_pages"),
            "pages_without_nodes": graph["metadata"]["provenance"].get("pages_without_nodes"),
            "pages_json_invalid": [
                r["page"] for r in records if any(f.startswith("json_invalid") for f in r["flags"])
            ],
            "nodes": len(graph["nodes"]),
            "edges": len(graph["edges"]),
            "cross_page_edges": len(cross),
            "cross_page_relations_accepted": dict(Counter(r["type"] for r in cross_relations)),
            "backward_cross_page_relations": sum(
                _page(r["to_object"]) < _page(r["from_object"]) for r in cross_relations
            ),
            "rejected_relations": dict(
                Counter(x["reason"] for r in records for x in r["rejected_relations"])
            ),
            "communities": len({n["community"] for n in graph["nodes"]}),
            "memory_chars_by_page": [r["memory_chars"] for r in records],
        }

    coverage = []
    for q in design["questions"]:
        if not q["has_evidence"]:
            continue
        missing = [p for p in q["evidence_pages"] if p not in node_pages[q["doc_id"]]]
        d = documents[q["doc_id"]]
        coverage.append(
            {
                "question_id": q["question_id"],
                "doc_id": q["doc_id"],
                "multi_page": q["multi_page"],
                "evidence_pages": q["evidence_pages"],
                "gold_pages_without_nodes": missing,
                "missing_due_to_resource_failure": [
                    p for p in missing if p in (d["resource_failed_pages"] or [])
                ],
            }
        )
    result = {
        "run_id": RUN_ID,
        "documents": documents,
        "totals": {
            "pages": sum(d["page_records"] for d in documents.values()),
            "nodes": sum(d["nodes"] for d in documents.values()),
            "edges": sum(d["edges"] for d in documents.values()),
            "cross_page_edges": sum(d["cross_page_edges"] for d in documents.values()),
            "resource_failed_pages": sum(
                len(d["resource_failed_pages"] or []) for d in documents.values()
            ),
            "evidence_questions": len(coverage),
            "evidence_questions_all_gold_pages_with_nodes": sum(
                not c["gold_pages_without_nodes"] for c in coverage
            ),
        },
        "gold_page_coverage": coverage,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps(result["totals"], indent=1))
    for c in coverage:
        if c["gold_pages_without_nodes"]:
            print("UNCOVERED", c)
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
