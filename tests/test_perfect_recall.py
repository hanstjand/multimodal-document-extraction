import pytest

from multimodal_document_extraction.data_models import Question, RetrievalResult, RetrievedItem
from multimodal_document_extraction.evaluation.retrieval_metrics import (
    mean_perfect_recall,
    perfect_recall,
    perfect_recall_for,
)


def _question(qid="q1", pages=(2, 5), doc_id="d1"):
    return Question(question_id=qid, doc_id=doc_id, question="?", evidence_pages=pages)


def _result(qid="q1", pages=(), doc_id="d1", unit_type="page"):
    items = tuple(
        RetrievedItem(
            doc_id=doc_id,
            page_number=p,
            rank=r,
            unit_type=unit_type,
            unit_id=None if unit_type == "page" else f"{doc_id}/page_{p}-obj_{r}",
        )
        for r, p in enumerate(pages, start=1)
    )
    return RetrievalResult(question_id=qid, doc_id=doc_id, method="m", items=items)


# --- perfect_recall (sets) -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("gold", "retrieved", "expected"),
    [
        ({2}, {2}, 1.0),  # exact
        ({2, 5}, {1, 2, 5, 9}, 1.0),  # superset still counts
        ({2, 5}, {2}, 0.0),  # one page missing
        ({2, 5}, {1, 3}, 0.0),  # none found
        ({2}, set(), 0.0),  # empty retrieval
        ([5, 2, 2], (2, 5), 1.0),  # any iterable, duplicates ignored
    ],
)
def test_perfect_recall_cases(gold, retrieved, expected):
    assert perfect_recall(gold, retrieved) == expected


@pytest.mark.parametrize("retrieved", [set(), {1, 2, 3}])
def test_perfect_recall_undefined_without_gold(retrieved):
    assert perfect_recall(set(), retrieved) is None


@pytest.mark.parametrize("pages", [{0}, {-1}, {1.0}, {True}])
def test_perfect_recall_rejects_invalid_page_numbers(pages):
    with pytest.raises(ValueError):
        perfect_recall(pages, {1})
    with pytest.raises(ValueError):
        perfect_recall({1}, pages)


@pytest.mark.parametrize("pages", ["12", 3])
def test_perfect_recall_rejects_non_iterables(pages):
    with pytest.raises(TypeError):
        perfect_recall(pages, {1})


# --- perfect_recall_for (models) -------------------------------------------------------------


def test_perfect_recall_for_uses_retrieved_pages_of_elements():
    # elements on pages 5, 2, 5 -> P-hat = {2, 5}
    result = _result(pages=(5, 2, 5), unit_type="element")
    assert perfect_recall_for(_question(pages=(2, 5)), result) == 1.0


def test_perfect_recall_for_depends_on_top_k():
    result = _result(pages=(7, 2, 9, 5))
    question = _question(pages=(2, 5))
    assert perfect_recall_for(question, result.top_k(2)) == 0.0
    assert perfect_recall_for(question, result.top_k(4)) == 1.0


def test_perfect_recall_for_rejects_mismatched_pairs():
    with pytest.raises(ValueError, match="question"):
        perfect_recall_for(_question(qid="q1"), _result(qid="q2", pages=(2,)))
    with pytest.raises(ValueError, match="document"):
        perfect_recall_for(_question(doc_id="d1"), _result(doc_id="d2", pages=(2,)))


# --- mean_perfect_recall ---------------------------------------------------------------------


def test_mean_perfect_recall_excludes_questions_without_gold():
    pairs = [
        (_question("q1", pages=(2,)), _result("q1", pages=(2, 3))),  # 1
        (_question("q2", pages=(2, 5)), _result("q2", pages=(2,))),  # 0
        (_question("q3", pages=(4,)), _result("q3", pages=(4,))),  # 1
        (_question("q4", pages=()), _result("q4", pages=(1,))),  # excluded
    ]
    summary = mean_perfect_recall(pairs)
    assert summary.metric == "perfect_recall"
    assert summary.mean == pytest.approx(2 / 3)
    assert summary.num_scored == 3
    assert summary.num_excluded == 1
    assert summary.num_questions == 4
    assert summary.to_dict() == {
        "metric": "perfect_recall",
        "mean": pytest.approx(2 / 3),
        "num_scored": 3,
        "num_excluded": 1,
    }


def test_mean_perfect_recall_all_excluded_or_empty():
    only_unanswerable = [(_question("q1", pages=()), _result("q1"))]
    summary = mean_perfect_recall(only_unanswerable)
    assert summary.mean is None and summary.num_scored == 0 and summary.num_excluded == 1
    empty = mean_perfect_recall([])
    assert empty.mean is None and empty.num_questions == 0


def test_mean_perfect_recall_accepts_generators():
    pairs = ((_question(f"q{i}", pages=(1,)), _result(f"q{i}", pages=(1,))) for i in range(3))
    assert mean_perfect_recall(pairs).mean == 1.0


def test_mean_perfect_recall_rejects_duplicate_questions():
    pair = (_question("q1", pages=(1,)), _result("q1", pages=(1,)))
    with pytest.raises(ValueError, match="more than once"):
        mean_perfect_recall([pair, pair])
