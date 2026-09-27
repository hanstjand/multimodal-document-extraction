import pytest

from multimodal_document_extraction.data_models import Question, RetrievalResult, RetrievedItem
from multimodal_document_extraction.evaluation.retrieval_metrics import (
    evaluate_retrieval,
    irrelevant_pages_ratio,
    irrelevant_pages_ratio_for,
    mean_irrelevant_pages_ratio,
    no_evidence_correct,
    no_evidence_correct_for,
    perfect_recall,
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


# --- irrelevant_pages_ratio (sets) -----------------------------------------------------------


@pytest.mark.parametrize(
    ("gold", "retrieved", "expected"),
    [
        ({2, 5}, {2, 5}, 0.0),  # all relevant
        ({2, 5}, {2, 5, 7, 9}, 0.5),  # 2 of 4 irrelevant
        ({2}, {1, 3, 4}, 1.0),  # all irrelevant
        ({2, 5}, {2}, 0.0),  # incomplete but no noise
        ({2}, {2, 7, 8}, 2 / 3),
    ],
)
def test_ipr_cases(gold, retrieved, expected):
    assert irrelevant_pages_ratio(gold, retrieved) == pytest.approx(expected)


def test_ipr_counts_pages_not_items():
    # elements on pages 2, 2, 7 -> P-hat = {2, 7} -> IPR = 1/2 (not 1/3)
    result = _result(pages=(2, 2, 7), unit_type="element")
    assert irrelevant_pages_ratio_for(_question(pages=(2,)), result) == pytest.approx(0.5)


def test_ipr_rejects_invalid_input():
    with pytest.raises(ValueError):
        irrelevant_pages_ratio({0}, {1})
    with pytest.raises(TypeError):
        irrelevant_pages_ratio({1}, "12")


def test_ipr_for_rejects_mismatched_pairs():
    with pytest.raises(ValueError, match="question"):
        irrelevant_pages_ratio_for(_question(qid="q1"), _result(qid="q2", pages=(2,)))


# --- The three D-009 edge cases --------------------------------------------------------------


def test_case1_evidence_but_nothing_retrieved():
    gold, retrieved = {2, 5}, set()
    assert perfect_recall(gold, retrieved) == 0.0
    assert irrelevant_pages_ratio(gold, retrieved) == 0.0
    assert no_evidence_correct(gold, retrieved) is None


def test_case2_no_evidence_and_nothing_retrieved():
    gold, retrieved = set(), set()
    assert irrelevant_pages_ratio(gold, retrieved) == 0.0
    assert no_evidence_correct(gold, retrieved) == 1.0
    assert perfect_recall(gold, retrieved) is None  # PR not used for no-evidence questions


def test_case3_no_evidence_but_something_retrieved():
    gold, retrieved = set(), {3, 4}
    assert irrelevant_pages_ratio(gold, retrieved) == 1.0
    assert no_evidence_correct(gold, retrieved) == 0.0
    assert perfect_recall(gold, retrieved) is None


def test_no_evidence_correct_for_models():
    assert no_evidence_correct_for(_question(pages=()), _result(pages=())) == 1.0
    assert no_evidence_correct_for(_question(pages=()), _result(pages=(1,))) == 0.0
    assert no_evidence_correct_for(_question(pages=(1,)), _result(pages=())) is None


# --- Aggregation by subset -------------------------------------------------------------------


def _mixed_pairs():
    return [
        # evidence subset
        (_question("e1", pages=(2,)), _result("e1", pages=(2, 3))),  # PR 1, IPR 0.5
        (_question("e2", pages=(2, 5)), _result("e2", pages=(2,))),  # PR 0, IPR 0
        (_question("e3", pages=(4,)), _result("e3", pages=())),  # PR 0, IPR 0 (case 1)
        # no-evidence subset
        (_question("n1", pages=()), _result("n1", pages=())),  # IPR 0, NEC 1 (case 2)
        (_question("n2", pages=()), _result("n2", pages=(1, 2))),  # IPR 1, NEC 0 (case 3)
    ]


def test_mean_ipr_uses_evidence_subset_only():
    summary = mean_irrelevant_pages_ratio(_mixed_pairs())
    assert summary.metric == "irrelevant_pages_ratio"
    assert summary.mean == pytest.approx(0.5 / 3)
    assert summary.num_scored == 3
    assert summary.num_excluded == 2


def test_evaluate_retrieval_reports_subsets_separately():
    evaluation = evaluate_retrieval(_mixed_pairs())
    assert evaluation.num_questions == 5
    assert evaluation.num_evidence_questions == 3
    assert evaluation.num_no_evidence_questions == 2

    assert evaluation.perfect_recall.mean == pytest.approx(1 / 3)
    assert evaluation.irrelevant_pages_ratio.mean == pytest.approx(0.5 / 3)
    assert evaluation.no_evidence_irrelevant_pages_ratio.mean == pytest.approx(0.5)
    assert evaluation.no_evidence_correct.mean == pytest.approx(0.5)

    assert evaluation.to_dict() == {
        "num_questions": 5,
        "evidence_subset": {
            "num_questions": 3,
            "perfect_recall": pytest.approx(1 / 3),
            "irrelevant_pages_ratio": pytest.approx(0.5 / 3),
        },
        "no_evidence_subset": {
            "num_questions": 2,
            "irrelevant_pages_ratio": pytest.approx(0.5),
            "no_evidence_correct": pytest.approx(0.5),
        },
    }


def test_evaluate_retrieval_subsets_are_consistent():
    evaluation = evaluate_retrieval(_mixed_pairs())
    # PR and IPR are averaged over exactly the same (evidence) questions.
    assert evaluation.perfect_recall.num_scored == evaluation.irrelevant_pages_ratio.num_scored
    # The no-evidence metrics cover exactly the complementary questions.
    assert (
        evaluation.no_evidence_correct.num_scored
        == evaluation.no_evidence_irrelevant_pages_ratio.num_scored
        == evaluation.perfect_recall.num_excluded
    )


def test_evaluate_retrieval_without_no_evidence_questions():
    pairs = [(_question("e1", pages=(1,)), _result("e1", pages=(1,)))]
    evaluation = evaluate_retrieval(pairs)
    assert evaluation.perfect_recall.mean == 1.0
    assert evaluation.irrelevant_pages_ratio.mean == 0.0
    assert evaluation.no_evidence_correct.mean is None
    assert evaluation.no_evidence_irrelevant_pages_ratio.mean is None


def test_evaluate_retrieval_accepts_generators_and_rejects_duplicates():
    generator = ((_question(f"e{i}", pages=(1,)), _result(f"e{i}", pages=(1,))) for i in range(3))
    assert evaluate_retrieval(generator).num_questions == 3
    pair = (_question("e1", pages=(1,)), _result("e1", pages=(1,)))
    with pytest.raises(ValueError, match="more than once"):
        evaluate_retrieval([pair, pair])
