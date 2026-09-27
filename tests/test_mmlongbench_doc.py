import hashlib
import json
from pathlib import Path

import pymupdf
import pytest

from multimodal_document_extraction.datasets.mmlongbench_doc import (
    DEFAULT_RAW_DIR,
    FLAG_INVALID_EVIDENCE_PAGES,
    FLAG_WRONG_DOCUMENT,
    load_mmlongbench_doc,
    load_pages,
    make_question_id,
)
from multimodal_document_extraction.evaluation.retrieval_metrics import evaluate_retrieval

# --- Synthetic fixture -----------------------------------------------------------------------


def _write_pdf(path: Path, num_pages: int, texts: dict[int, str] | None = None) -> None:
    doc = pymupdf.open()
    for i in range(num_pages):
        page = doc.new_page()
        text = (texts or {}).get(i + 1)
        if text:
            page.insert_text((72, 72), text)
    doc.save(path)
    doc.close()


def _sample(
    doc_id, question, pages, answer="x", sources="['Table']", fmt="Str", doc_type="Brochure"
):
    return {
        "doc_id": doc_id,
        "doc_type": doc_type,
        "question": question,
        "answer": answer,
        "evidence_pages": pages,
        "evidence_sources": sources,
        "answer_format": fmt,
    }


@pytest.fixture
def raw_dir(tmp_path: Path) -> Path:
    (tmp_path / "github").mkdir()
    (tmp_path / "documents").mkdir()
    _write_pdf(tmp_path / "documents" / "a.pdf", 3, {2: "hello page two"})
    _write_pdf(tmp_path / "documents" / "b.pdf", 5)
    samples = [
        _sample("a.pdf", "Q single?", "[2]"),
        _sample("a.pdf", "Q multi?", "[1, 3]"),
        _sample("a.pdf", "Q none?", "[]", answer="Not answerable", sources="[]", fmt="None"),
        _sample("b.pdf", "Q zero page?", "[0]", doc_type="Guidebook"),
        _sample("b.pdf", "Q partly out of range?", "[2, 99]", doc_type="Guidebook"),
    ]
    samples_path = tmp_path / "github" / "samples.json"
    samples_path.write_text(json.dumps(samples), encoding="utf-8")
    manifest = {
        "files": {
            "github/samples.json": {
                "sha256": hashlib.sha256(samples_path.read_bytes()).hexdigest()
            },
            **{
                f"documents/{p.name}": {"sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                for p in (tmp_path / "documents").iterdir()
            },
        }
    }
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    return tmp_path


def test_loads_documents_and_questions(raw_dir):
    ds = load_mmlongbench_doc(raw_dir, verify_pdfs=True, wrong_documents=())
    assert set(ds.documents) == {"a.pdf", "b.pdf"}
    assert ds.documents["a.pdf"].num_pages == 3
    assert ds.documents["b.pdf"].doc_type == "Guidebook"
    assert ds.documents["a.pdf"].dataset == "MMLongBench-Doc"
    assert len(ds.questions) == 5
    q_single, q_multi, q_none = ds.questions[:3]
    assert q_single.evidence_pages == frozenset({2})
    assert q_multi.evidence_pages == frozenset({1, 3}) and q_multi.is_multi_page
    assert not q_none.has_evidence and q_none.answer_format == "None"
    assert q_single.evidence_sources == ("Table",)
    assert q_single.metadata["index"] == 0 and q_single.metadata["doc_type"] == "Brochure"


def test_question_ids_are_index_plus_hash_and_stable(raw_dir):
    ds1 = load_mmlongbench_doc(raw_dir, wrong_documents=())
    ds2 = load_mmlongbench_doc(raw_dir, wrong_documents=())
    ids = [q.question_id for q in ds1.questions]
    assert ids == [q.question_id for q in ds2.questions]
    assert len(set(ids)) == len(ids)
    assert ids[0] == make_question_id(0, "a.pdf", "Q single?")
    assert ids[0].startswith("mmlb-0000-") and len(ids[0]) == len("mmlb-0000-") + 8


def test_invalid_evidence_pages_are_dropped_and_flagged(raw_dir):
    ds = load_mmlongbench_doc(raw_dir, wrong_documents=())
    zero, partial = ds.questions[3], ds.questions[4]
    assert zero.evidence_pages == frozenset()
    assert zero.metadata["raw_evidence_pages"] == [0]
    assert zero.metadata["quality_flags"] == [FLAG_INVALID_EVIDENCE_PAGES]
    assert partial.evidence_pages == frozenset({2})
    assert partial.metadata["raw_evidence_pages"] == [2, 99]
    assert partial.metadata["quality_flags"] == [FLAG_INVALID_EVIDENCE_PAGES]
    assert [q.metadata["index"] for q in ds.clean_questions()] == [0, 1, 2]
    assert [q.metadata["index"] for q in ds.flagged_questions()] == [3, 4]


def test_wrong_document_flag(raw_dir):
    ds = load_mmlongbench_doc(raw_dir, wrong_documents={"a.pdf"})
    assert all(
        FLAG_WRONG_DOCUMENT in q.metadata["quality_flags"] for q in ds.questions_for("a.pdf")
    )
    assert ds.clean_questions() == ()
    assert "wrong_document_note" in ds.documents["a.pdf"].metadata


def test_samples_checksum_is_verified(raw_dir):
    path = raw_dir / "github" / "samples.json"
    path.write_text(
        path.read_text(encoding="utf-8").replace("Q single?", "Q changed?"), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="MANIFEST"):
        load_mmlongbench_doc(raw_dir, wrong_documents=())


def test_pdf_checksum_is_verified_when_requested(raw_dir):
    _write_pdf(raw_dir / "documents" / "b.pdf", 5, {1: "tampered"})
    load_mmlongbench_doc(raw_dir, wrong_documents=())  # not verified by default
    with pytest.raises(ValueError, match="MANIFEST"):
        load_mmlongbench_doc(raw_dir, verify_pdfs=True, wrong_documents=())


def test_missing_pdf_raises(raw_dir):
    (raw_dir / "documents" / "b.pdf").unlink()
    with pytest.raises(FileNotFoundError):
        load_mmlongbench_doc(raw_dir, wrong_documents=())


def test_inconsistent_doc_type_raises(raw_dir):
    path = raw_dir / "github" / "samples.json"
    samples = json.loads(path.read_text(encoding="utf-8"))
    samples[1]["doc_type"] = "Academic paper"
    path.write_text(json.dumps(samples), encoding="utf-8")
    manifest = json.loads((raw_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    manifest["files"]["github/samples.json"]["sha256"] = hashlib.sha256(
        path.read_bytes()
    ).hexdigest()
    (raw_dir / "MANIFEST.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="doc_type"):
        load_mmlongbench_doc(raw_dir, wrong_documents=())


def test_load_pages_is_one_based_with_text(raw_dir):
    ds = load_mmlongbench_doc(raw_dir, wrong_documents=())
    pages = load_pages(ds.documents["a.pdf"])
    assert [p.page_number for p in pages] == [1, 2, 3]
    assert "hello page two" in pages[1].text
    assert pages[0].text.strip() == ""
    assert all(p.text is None for p in load_pages(ds.documents["a.pdf"], with_text=False))


# --- Integration with the real download (skipped if absent) -----------------------------------

real_data = pytest.mark.skipif(
    not (DEFAULT_RAW_DIR / "MANIFEST.json").exists(), reason="MMLongBench-Doc not downloaded"
)


@pytest.fixture(scope="module")
def real_ds():
    return load_mmlongbench_doc()


@real_data
def test_real_counts_match_inspection(real_ds):
    assert len(real_ds.questions) == 1082
    assert len(real_ds.documents) == 135
    assert sum(d.num_pages for d in real_ds.documents.values()) == 6529
    assert len({q.question_id for q in real_ds.questions}) == 1082


@real_data
def test_real_quality_flags(real_ds):
    flagged = real_ds.flagged_questions()
    flags = [f for q in flagged for f in q.metadata["quality_flags"]]
    assert flags.count(FLAG_INVALID_EVIDENCE_PAGES) == 9
    assert flags.count(FLAG_WRONG_DOCUMENT) == 10
    assert len(flagged) == 19
    assert len(real_ds.clean_questions()) == 1063


@real_data
def test_real_subset_sizes(real_ds):
    def sizes(questions):
        with_evidence = sum(q.has_evidence for q in questions)
        return with_evidence, len(questions) - with_evidence

    # 8 of the 9 invalid-page questions lose all their pages -> counted as no-evidence in the full set
    assert sizes(real_ds.questions) == (846, 236)
    assert sizes(real_ds.clean_questions()) == (837, 226)


@real_data
def test_real_questions_work_with_metrics(real_ds):
    from multimodal_document_extraction.data_models import RetrievalResult, RetrievedItem

    def oracle(q):
        items = tuple(
            RetrievedItem(doc_id=q.doc_id, page_number=p, rank=r)
            for r, p in enumerate(sorted(q.evidence_pages), start=1)
        )
        return RetrievalResult(
            question_id=q.question_id, doc_id=q.doc_id, method="oracle", items=items
        )

    evaluation = evaluate_retrieval((q, oracle(q)) for q in real_ds.clean_questions())
    assert evaluation.perfect_recall.mean == 1.0
    assert evaluation.irrelevant_pages_ratio.mean == 0.0
    assert evaluation.no_evidence_correct.mean == 1.0
