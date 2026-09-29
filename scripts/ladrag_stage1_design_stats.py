"""Stage-1 design statistics for the proposed subset retrieval-eval-v1 (CP-4.3D planning; read-only).

retrieval-eval-v1 (proposed) = all pilot-v1 questions of the five documents already used in the
CP-4.3C calibration (CAL-0001). Documents are fixed by that earlier choice, not by any retrieval
result. pilot-v1 itself is not modified. No model inference, no API.

Usage:
  python scripts/ladrag_stage1_design_stats.py
Writes experiments/ladrag/results/design/retrieval-eval-v1-stage1-stats.json (committed).
"""

import itertools
import json
from collections import Counter
from pathlib import Path

from multimodal_document_extraction.datasets.mmlongbench_doc import load_mmlongbench_doc
from multimodal_document_extraction.datasets.subsets import Subset

PILOT = Path("data/splits/mmlongbench-doc/pilot-v1.json")
CALIBRATION_PLAN = Path("experiments/ladrag/configs/CAL-0001-qwen3.5-2b-1280.json")
OUT = Path("experiments/ladrag/results/design/retrieval-eval-v1-stage1-stats.json")
SOURCE_GROUPS = {
    "Pure-text (Plain-text)": "text",
    "Generalized-text (Layout)": "layout",
    "Figure": "figure",
    "Chart": "chart",
    "Table": "table",
}


def _adjacent_only(pages: list[int]) -> bool:
    return all(b - a == 1 for a, b in itertools.pairwise(pages))


def main() -> None:
    plan = json.loads(CALIBRATION_PLAN.read_text(encoding="utf-8"))
    cached = {doc_id: spec["pages"] for doc_id, spec in plan["documents"].items()}
    ds = load_mmlongbench_doc()
    pilot = Subset.load(PILOT)
    questions = [q for q in pilot.select(ds.questions) if q.doc_id in cached]

    documents, rows = {}, []
    for doc_id in sorted(cached):
        doc = ds.documents[doc_id]
        pages = cached[doc_id]
        documents[doc_id] = {
            "doc_type": doc.doc_type,
            "num_pages": doc.num_pages,
            "cal0001_pages": [pages[0], pages[-1]],
            "cal0001_starts_at_page_1": pages[0] == 1,
            "pages_not_yet_ingested": doc.num_pages - len(pages),
        }
    for q in questions:
        gold = sorted(q.evidence_pages)
        raw = list(q.metadata["raw_evidence_pages"])
        rows.append(
            {
                "question_id": q.question_id,
                "doc_id": q.doc_id,
                "evidence_pages": gold,
                "evidence_sources": list(q.evidence_sources),
                "source_groups": sorted({SOURCE_GROUPS[s] for s in q.evidence_sources})
                if q.has_evidence
                else [],
                "has_evidence": q.has_evidence,
                "multi_page": q.is_multi_page,
                "adjacent_only": _adjacent_only(gold) if q.is_multi_page else None,
                "all_gold_pages_valid": bool(raw) and len(raw) == len(gold),
                "gold_pages_in_cal0001_range": sum(p in cached[q.doc_id] for p in gold),
            }
        )

    evidence = [r for r in rows if r["has_evidence"]]
    multi = [r for r in evidence if r["multi_page"]]

    def per_group(subset: list[dict]) -> dict:
        return dict(Counter(g for r in subset for g in r["source_groups"]).most_common())

    for doc_id, d in documents.items():
        mine = [r for r in rows if r["doc_id"] == doc_id]
        d.update(
            questions=len(mine),
            evidence=sum(r["has_evidence"] for r in mine),
            no_evidence=sum(not r["has_evidence"] for r in mine),
            multi_page=sum(bool(r["multi_page"]) for r in mine),
        )
    stats = {
        "subset": "retrieval-eval-v1 (proposed, Stage 1)",
        "source_subset": pilot.name,
        "documents": documents,
        "totals": {
            "documents": len(documents),
            "pages": sum(d["num_pages"] for d in documents.values()),
            "pages_ingested_in_cal0001": sum(len(p) for p in cached.values()),
            "pages_not_yet_ingested": sum(d["pages_not_yet_ingested"] for d in documents.values()),
            "questions": len(rows),
            "evidence_questions": len(evidence),
            "no_evidence_questions": len(rows) - len(evidence),
            "single_page": len(evidence) - len(multi),
            "multi_page": len(multi),
            "multi_page_adjacent_only": sum(r["adjacent_only"] for r in multi),
            "evidence_questions_all_gold_valid": sum(r["all_gold_pages_valid"] for r in evidence),
        },
        "gold_page_count_distribution": dict(
            sorted(Counter(len(r["evidence_pages"]) for r in evidence).items())
        ),
        "source_groups_multilabel": {
            "all_evidence": per_group(evidence),
            "single_page": per_group([r for r in evidence if not r["multi_page"]]),
            "multi_page": per_group(multi),
        },
        "source_combinations": dict(
            Counter("+".join(r["source_groups"]) for r in evidence).most_common()
        ),
        "questions": rows,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(
        json.dumps(stats, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({k: stats[k] for k in stats if k != "questions"}, indent=1))
    print(f"written {OUT}")


if __name__ == "__main__":
    main()
