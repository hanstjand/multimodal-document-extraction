"""Draw a reproducible stratified sample of accepted cross-page relations for a manual audit (CP-4.3C).

Reads existing page records only (no model inference, no API). Every accepted relation with origin
``fig11`` whose endpoints lie on different pages is a candidate. Sampling (seed 0): all relations of
rare types (< 3 candidates) are kept; for the remaining types, up to ``per_type`` relations are drawn,
spread round-robin over documents so every document with candidates is represented.

Usage:
  python scripts/ladrag_relation_audit_sample.py CAL-0001-qwen3.5-2b-1280 [--per-type 12] [--seed 0]
Writes experiments/ladrag/results/calibration/<calibration_id>-relation-audit-sample.json (committed);
judgements are added manually to the audit file, not by this script.
"""

import argparse
import json
import random
from collections import defaultdict
from pathlib import Path

from multimodal_document_extraction.studies.ladrag.schema import parse_node_id

ROOT = Path("data/processed/ladrag/calibration")


def _node_summary(attrs: dict) -> dict:
    return {
        "type": attrs.get("type"),
        "title": attrs.get("title_or_heading"),
        "content": (attrs.get("content") or "")[:400],
        "summary": (attrs.get("summary") or "")[:300],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("calibration_id")
    parser.add_argument("--per-type", type=int, default=12)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    candidates, nodes = [], {}
    for doc_dir in sorted(p for p in (ROOT / args.calibration_id).iterdir() if p.is_dir()):
        for record_path in sorted((doc_dir / "pages").glob("page_*.json")):
            record = json.loads(record_path.read_text(encoding="utf-8"))
            for obj in record["objects"]:
                nodes[(doc_dir.name, obj["object_id"])] = obj["attrs"]
            for rel in record["relations"]:
                if rel["origin"] != "fig11":
                    continue
                source_page = parse_node_id(rel["from_object"])[0]
                target_page = parse_node_id(rel["to_object"])[0]
                if source_page != target_page:
                    candidates.append(
                        {"doc_id": doc_dir.name, "record_page": record["page"], **rel}
                    )

    by_type: dict[str, list] = defaultdict(list)
    for c in candidates:
        by_type[c["type"]].append(c)
    rng = random.Random(args.seed)
    sample = []
    for rel_type in sorted(by_type):
        items = sorted(
            by_type[rel_type], key=lambda c: (c["doc_id"], c["from_object"], c["to_object"])
        )
        if len(items) < 3 or len(items) <= args.per_type:
            sample += items
            continue
        by_doc: dict[str, list] = defaultdict(list)
        for c in items:
            by_doc[c["doc_id"]].append(c)
        for doc_items in by_doc.values():
            rng.shuffle(doc_items)
        docs = sorted(by_doc)
        picked = []
        while len(picked) < args.per_type:
            for doc in docs:
                if by_doc[doc] and len(picked) < args.per_type:
                    picked.append(by_doc[doc].pop())
        sample += picked

    rows = []
    for i, c in enumerate(sample, start=1):
        rows.append(
            {
                "id": f"R{i:02d}",
                "doc_id": c["doc_id"],
                "type": c["type"],
                "source": {
                    "object_id": c["from_object"],
                    **_node_summary(nodes[(c["doc_id"], c["from_object"])]),
                },
                "target": {
                    "object_id": c["to_object"],
                    **_node_summary(nodes[(c["doc_id"], c["to_object"])]),
                },
                "judgement": None,
                "reason": None,
            }
        )
    out = (
        Path("experiments/ladrag/results/calibration")
        / f"{args.calibration_id}-relation-audit-sample.json"
    )
    out.write_text(
        json.dumps(
            {
                "calibration_id": args.calibration_id,
                "seed": args.seed,
                "per_type": args.per_type,
                "candidates_by_type": {t: len(v) for t, v in sorted(by_type.items())},
                "sample_size": len(rows),
                "sample": rows,
            },
            indent=2,
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        f"candidates: { {t: len(v) for t, v in sorted(by_type.items())} }; sampled {len(rows)} -> {out}"
    )


if __name__ == "__main__":
    main()
