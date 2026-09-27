"""Create the MMLongBench-Doc pilot (pilot-v1) and calibration (calib-v1) subsets (CP-2.3).

Rules: docs/studies/ladrag/REPRODUCTION_PROTOCOL.md §5 and decision D-013. Only documents whose
questions are all clean (no quality flags, D-012) are eligible.

Usage:
  python scripts/make_mmlongbench_pilot.py [--seed 0] [--out data/splits/mmlongbench-doc] [--force]
"""

import argparse
import dataclasses
import json
from datetime import UTC, datetime
from pathlib import Path

from multimodal_document_extraction.datasets.mmlongbench_doc import (
    DATASET_NAME,
    DEFAULT_RAW_DIR,
    load_mmlongbench_doc,
    load_pages,
)
from multimodal_document_extraction.datasets.subsets import (
    DocumentStats,
    SelectionConstraints,
    Subset,
    select_calibration,
    select_documents,
)


def _totals(docs: list[DocumentStats]) -> dict:
    questions = sum(d.num_questions for d in docs)
    multi = sum(d.num_multi_page for d in docs)
    return {
        "documents": len(docs),
        "pages": sum(d.num_pages for d in docs),
        "questions": questions,
        "multi_page_questions": multi,
        "multi_page_share": round(multi / questions, 3) if questions else None,
        "no_evidence_questions": sum(d.num_no_evidence for d in docs),
        "image_only_documents": sum(d.image_only for d in docs),
        "doc_types": sorted({d.doc_type for d in docs}),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--raw", type=Path, default=DEFAULT_RAW_DIR)
    parser.add_argument("--out", type=Path, default=Path("data/splits/mmlongbench-doc"))
    parser.add_argument("--force", action="store_true", help="overwrite existing subset files")
    args = parser.parse_args()

    pilot_path, calib_path = args.out / "pilot-v1.json", args.out / "calib-v1.json"
    if not args.force and (pilot_path.exists() or calib_path.exists()):
        raise SystemExit(
            f"{pilot_path} or {calib_path} exists; versioned subsets are not overwritten"
        )

    ds = load_mmlongbench_doc(args.raw, verify_pdfs=True)
    manifest = json.loads((args.raw / "MANIFEST.json").read_text(encoding="utf-8"))

    stats: list[DocumentStats] = []
    for doc_id, document in sorted(ds.documents.items()):
        questions = ds.questions_for(doc_id)
        if any(q.metadata["quality_flags"] for q in questions):
            continue  # only fully clean documents are eligible
        image_only = not any((p.text or "").strip() for p in load_pages(document))
        stats.append(
            DocumentStats(
                doc_id=doc_id,
                doc_type=document.doc_type or "",
                num_pages=document.num_pages,
                num_questions=len(questions),
                num_multi_page=sum(q.is_multi_page for q in questions),
                num_no_evidence=sum(not q.has_evidence for q in questions),
                image_only=image_only,
            )
        )

    constraints = SelectionConstraints()
    pilot_docs, attempt = select_documents(stats, constraints, seed=args.seed)
    calib_docs = select_calibration(pilot_docs, seed=args.seed)

    source = {
        "github_commit": manifest["github"]["commit"],
        "samples_sha256": manifest["files"]["github/samples.json"]["sha256"],
    }
    created = datetime.now(UTC).isoformat(timespec="seconds")

    def build(name: str, docs: list[DocumentStats], extra: dict) -> Subset:
        doc_ids = [d.doc_id for d in docs]
        question_ids = [q.question_id for q in ds.questions if q.doc_id in set(doc_ids)]
        return Subset(
            name=name,
            dataset=DATASET_NAME,
            doc_ids=doc_ids,
            question_ids=question_ids,
            metadata={
                "created_at": created,
                "created_by": "scripts/make_mmlongbench_pilot.py",
                "decision": "D-013",
                "source": source,
                "seed": args.seed,
                **extra,
                "totals": _totals(docs),
                "documents": [dataclasses.asdict(d) for d in docs],
            },
        )

    pilot = build(
        "pilot-v1",
        pilot_docs,
        {
            "eligible_documents": len(stats),
            "eligibility": "all questions clean (D-012) and num_pages <= 40",
            "constraints": dataclasses.asdict(constraints),
            "attempt": attempt,
        },
    )
    calib = build(
        "calib-v1",
        calib_docs,
        {
            "parent": "pilot-v1",
            "rule": "2 pilot documents, each >= 1 multi-page question, total pages <= 35 "
            "(REPRODUCTION_PROTOCOL.md §5); chosen with the seeded RNG among valid pairs",
        },
    )
    pilot.save(pilot_path)
    calib.save(calib_path)
    for subset in (pilot, calib):
        print(subset.name, json.dumps(subset.metadata["totals"]))
        for d in subset.metadata["documents"]:
            print(
                f"  {d['doc_type']:<32} {d['num_pages']:>3}p {d['num_questions']:>2}q "
                f"multi={d['num_multi_page']} noev={d['num_no_evidence']} "
                f"image_only={d['image_only']}  {d['doc_id']}"
            )


if __name__ == "__main__":
    main()
