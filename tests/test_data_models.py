import dataclasses
import json

import pytest

from multimodal_document_extraction.data_models import (
    Document,
    Page,
    Question,
    RetrievalResult,
    RetrievedItem,
)


def _items(*pages, unit_type="page"):
    return tuple(
        RetrievedItem(
            doc_id="d1",
            page_number=p,
            rank=r,
            unit_type=unit_type,
            unit_id=None if unit_type == "page" else f"d1/page_{p}-obj_{r}",
        )
        for r, p in enumerate(pages, start=1)
    )


def _json_roundtrip(obj):
    return type(obj).from_dict(json.loads(json.dumps(obj.to_dict())))


# --- Document / Page -------------------------------------------------------------------------


def test_document_pages_are_one_based():
    doc = Document(doc_id="d1", num_pages=3)
    assert list(doc.page_numbers()) == [1, 2, 3]
    assert doc.has_page(1) and doc.has_page(3)
    assert not doc.has_page(0) and not doc.has_page(4)


@pytest.mark.parametrize("num_pages", [0, -1, 1.0, True, "3"])
def test_document_rejects_invalid_num_pages(num_pages):
    with pytest.raises(ValueError):
        Document(doc_id="d1", num_pages=num_pages)


def test_document_rejects_empty_id():
    with pytest.raises(ValueError):
        Document(doc_id="", num_pages=1)


@pytest.mark.parametrize("page_number", [0, -2, 1.5, False])
def test_page_rejects_invalid_page_number(page_number):
    with pytest.raises(ValueError):
        Page(doc_id="d1", page_number=page_number)


def test_models_are_frozen():
    doc = Document(doc_id="d1", num_pages=2)
    with pytest.raises(dataclasses.FrozenInstanceError):
        doc.num_pages = 5  # type: ignore[misc]


def test_metadata_ignored_for_equality_and_hash():
    a = Document(doc_id="d1", num_pages=2, metadata={"x": 1})
    b = Document(doc_id="d1", num_pages=2, metadata={"x": 2})
    assert a == b
    assert hash(a) == hash(b)


# --- Question --------------------------------------------------------------------------------


def test_question_coerces_evidence_pages_to_frozenset():
    q = Question(question_id="q1", doc_id="d1", question="?", evidence_pages=[3, 1, 3])
    assert q.evidence_pages == frozenset({1, 3})
    assert q.has_evidence and q.is_multi_page


def test_question_without_evidence():
    q = Question(question_id="q1", doc_id="d1", question="?")
    assert q.evidence_pages == frozenset()
    assert not q.has_evidence and not q.is_multi_page


@pytest.mark.parametrize("pages", [[0], [1, -1], [1.0]])
def test_question_rejects_invalid_evidence_pages(pages):
    with pytest.raises(ValueError):
        Question(question_id="q1", doc_id="d1", question="?", evidence_pages=pages)


@pytest.mark.parametrize("pages", ["12", 5])
def test_question_rejects_non_iterable_evidence_pages(pages):
    with pytest.raises(TypeError):
        Question(question_id="q1", doc_id="d1", question="?", evidence_pages=pages)


def test_result_rejects_non_item_entries():
    with pytest.raises(TypeError):
        RetrievalResult(question_id="q1", doc_id="d1", method="m", items=({"page_number": 1},))


def test_question_validate_against_document():
    doc = Document(doc_id="d1", num_pages=5)
    Question(question_id="q1", doc_id="d1", question="?", evidence_pages=[1, 5]).validate_against(
        doc
    )
    with pytest.raises(ValueError, match="exceed"):
        Question(question_id="q2", doc_id="d1", question="?", evidence_pages=[6]).validate_against(
            doc
        )
    with pytest.raises(ValueError, match="not d1"):
        Question(question_id="q3", doc_id="d2", question="?").validate_against(doc)


# --- RetrievedItem ---------------------------------------------------------------------------


def test_retrieved_item_defaults_to_page_unit():
    item = RetrievedItem(doc_id="d1", page_number=2, rank=1, score=0.5)
    assert item.unit_type == "page"
    assert item.key == ("page", 2)


def test_non_page_item_requires_unit_id():
    with pytest.raises(ValueError, match="unit_id"):
        RetrievedItem(doc_id="d1", page_number=2, rank=1, unit_type="node")


@pytest.mark.parametrize(
    "kwargs",
    [
        {"unit_type": "chunk", "unit_id": "x"},
        {"score": float("nan")},
        {"score": float("inf")},
        {"rank": 0},
    ],
)
def test_retrieved_item_rejects_invalid_fields(kwargs):
    base = {"doc_id": "d1", "page_number": 1, "rank": 1}
    with pytest.raises(ValueError):
        RetrievedItem(**{**base, **kwargs})


# --- RetrievalResult -------------------------------------------------------------------------


def test_result_retrieved_pages_from_elements():
    result = RetrievalResult(
        question_id="q1", doc_id="d1", method="m", items=_items(4, 2, 4, 7, unit_type="element")
    )
    assert len(result) == 4
    assert result.retrieved_pages == frozenset({2, 4, 7})
    assert result.pages_in_rank_order() == (4, 2, 7)


def test_empty_result_is_allowed():
    result = RetrievalResult(question_id="q1", doc_id="d1", method="m")
    assert len(result) == 0
    assert result.retrieved_pages == frozenset()


def test_result_top_k():
    result = RetrievalResult(question_id="q1", doc_id="d1", method="m", items=_items(3, 1, 2))
    assert result.top_k(2).retrieved_pages == frozenset({3, 1})
    assert result.top_k(2).metadata["top_k"] == 2
    assert len(result.top_k(0)) == 0
    assert result.top_k(10).items == result.items
    with pytest.raises(ValueError):
        result.top_k(-1)


def test_result_rejects_non_consecutive_ranks():
    items = (
        RetrievedItem(doc_id="d1", page_number=1, rank=1),
        RetrievedItem(doc_id="d1", page_number=2, rank=3),
    )
    with pytest.raises(ValueError, match="ranks"):
        RetrievalResult(question_id="q1", doc_id="d1", method="m", items=items)


def test_result_rejects_duplicate_units():
    with pytest.raises(ValueError, match="duplicate"):
        RetrievalResult(question_id="q1", doc_id="d1", method="m", items=_items(1, 1))


def test_result_rejects_item_from_other_document():
    item = RetrievedItem(doc_id="d2", page_number=1, rank=1)
    with pytest.raises(ValueError, match="d2"):
        RetrievalResult(question_id="q1", doc_id="d1", method="m", items=(item,))


def test_result_rejects_negative_latency():
    with pytest.raises(ValueError):
        RetrievalResult(question_id="q1", doc_id="d1", method="m", latency_s=-0.1)


# --- Serialization ---------------------------------------------------------------------------


def test_json_roundtrip_all_models():
    objects = [
        Document(doc_id="d1", num_pages=3, dataset="MMLongBench-Doc", metadata={"k": "v"}),
        Page(doc_id="d1", page_number=2, text="hello", image_path="p2.png"),
        Question(
            question_id="q1",
            doc_id="d1",
            question="How many?",
            evidence_pages=[2, 1],
            answer="3",
            answer_format="Int",
            evidence_sources=["Chart", "Table"],
            metadata={"doc_type": "Report"},
        ),
        RetrievalResult(
            question_id="q1",
            doc_id="d1",
            method="bm25-page",
            items=_items(2, 1),
            latency_s=0.25,
            metadata={"tokens": 0},
        ),
    ]
    for obj in objects:
        restored = _json_roundtrip(obj)
        assert restored == obj
        assert restored.metadata == obj.metadata


def test_question_to_dict_is_deterministic():
    q = Question(question_id="q1", doc_id="d1", question="?", evidence_pages=[9, 2, 5])
    assert q.to_dict()["evidence_pages"] == [2, 5, 9]
