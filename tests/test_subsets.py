import dataclasses
from pathlib import Path

import pytest

from multimodal_document_extraction.data_models import Question
from multimodal_document_extraction.datasets.mmlongbench_doc import (
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

SPLITS = Path("data/splits/mmlongbench-doc")


def _q(qid, doc_id):
    return Question(question_id=qid, doc_id=doc_id, question="?", evidence_pages=[1])


# --- Subset ----------------------------------------------------------------------------------


def test_subset_roundtrip(tmp_path):
    subset = Subset("s1", "D", ["a", "b"], ["q1", "q2"], metadata={"seed": 0})
    path = tmp_path / "s1.json"
    subset.save(path)
    loaded = Subset.load(path)
    assert loaded == subset and loaded.metadata == {"seed": 0}


def test_subset_select_keeps_input_order_and_checks_ids():
    questions = [_q("q1", "a"), _q("q2", "b"), _q("q3", "c")]
    subset = Subset("s", "D", ["a", "b"], ["q2", "q1"])
    assert [q.question_id for q in subset.select(questions)] == ["q1", "q2"]
    with pytest.raises(KeyError):
        Subset("s", "D", ["a"], ["q1", "q9"]).select(questions)
    with pytest.raises(ValueError, match="not in the subset"):
        Subset("s", "D", ["a"], ["q1", "q2"]).select(questions)


def test_subset_rejects_duplicates():
    with pytest.raises(ValueError):
        Subset("s", "D", ["a", "a"], [])
    with pytest.raises(ValueError):
        Subset("s", "D", ["a"], ["q1", "q1"])


# --- select_documents / select_calibration ---------------------------------------------------


def _stats(n=30):
    types = ["T1", "T2", "T3"]
    return [
        DocumentStats(
            doc_id=f"d{i:02d}",
            doc_type=types[i % 3],
            num_pages=10 + i % 7,
            num_questions=5 + i % 3,
            num_multi_page=1 + i % 3,
            num_no_evidence=i % 2,
            image_only=i % 5 == 0,
        )
        for i in range(n)
    ]


def _constraints(**overrides):
    base = SelectionConstraints(
        num_documents=5,
        max_pages_per_document=40,
        total_pages=(50, 80),
        total_questions=(20, 40),
        min_multi_page_share=0.2,
        min_no_evidence=1,
        min_image_only=1,
    )
    return dataclasses.replace(base, **overrides)


def test_select_documents_satisfies_constraints_and_is_deterministic():
    constraints = _constraints()
    docs, attempt = select_documents(_stats(), constraints, seed=7)
    assert constraints.check(docs) and attempt >= 1
    assert {d.doc_type for d in docs} == {"T1", "T2", "T3"}
    assert [d.doc_id for d in docs] == sorted(d.doc_id for d in docs)
    again, _ = select_documents(list(reversed(_stats())), constraints, seed=7)
    assert again == docs  # independent of input order
    other, _ = select_documents(_stats(), constraints, seed=8)
    assert constraints.check(other)


def test_select_documents_respects_page_limit_and_fails_when_infeasible():
    docs, _ = select_documents(_stats(), _constraints(max_pages_per_document=13), seed=1)
    assert all(d.num_pages <= 13 for d in docs)
    with pytest.raises(RuntimeError):
        select_documents(_stats(), _constraints(total_pages=(1000, 2000)), seed=1, max_attempts=50)


def test_select_calibration():
    docs, _ = select_documents(_stats(), _constraints(), seed=3)
    calib = select_calibration(docs, seed=3, max_total_pages=40)
    assert len(calib) == 2 and sum(d.num_pages for d in calib) <= 40
    assert all(d.num_multi_page > 0 for d in calib)
    assert calib == select_calibration(docs, seed=3, max_total_pages=40)
    with pytest.raises(RuntimeError):
        select_calibration(docs, seed=3, max_total_pages=5)


# --- Real pilot files (skipped if data or splits are absent) ---------------------------------

real = pytest.mark.skipif(
    not (DEFAULT_RAW_DIR / "MANIFEST.json").exists() or not (SPLITS / "pilot-v1.json").exists(),
    reason="MMLongBench-Doc or pilot splits not available",
)


@pytest.fixture(scope="module")
def real_ds():
    return load_mmlongbench_doc()


@real
def test_pilot_and_calibration_files_are_consistent(real_ds):
    pilot = Subset.load(SPLITS / "pilot-v1.json")
    calib = Subset.load(SPLITS / "calib-v1.json")
    questions = pilot.select(real_ds.questions)
    assert len(pilot.doc_ids) == 10 and len(questions) == 80
    assert all(not q.metadata["quality_flags"] for q in questions)
    assert {real_ds.documents[d].doc_type for d in pilot.doc_ids} == {
        d.doc_type for d in real_ds.documents.values()
    }
    assert set(calib.doc_ids) <= set(pilot.doc_ids) and set(calib.question_ids) <= set(
        pilot.question_ids
    )
    assert (
        sum(real_ds.documents[d].num_pages for d in pilot.doc_ids)
        == pilot.metadata["totals"]["pages"]
    )


@real
def test_pilot_selection_is_reproducible(real_ds):
    pilot = Subset.load(SPLITS / "pilot-v1.json")
    stats = []
    for doc_id, doc in sorted(real_ds.documents.items()):
        qs = real_ds.questions_for(doc_id)
        if any(q.metadata["quality_flags"] for q in qs):
            continue
        stats.append(
            DocumentStats(
                doc_id=doc_id,
                doc_type=doc.doc_type or "",
                num_pages=doc.num_pages,
                num_questions=len(qs),
                num_multi_page=sum(q.is_multi_page for q in qs),
                num_no_evidence=sum(not q.has_evidence for q in qs),
                image_only=not any((p.text or "").strip() for p in load_pages(doc)),
            )
        )
    docs, attempt = select_documents(stats, SelectionConstraints(), seed=pilot.metadata["seed"])
    assert [d.doc_id for d in docs] == list(pilot.doc_ids)
    assert attempt == pilot.metadata["attempt"]
