import csv

import pytest

from multimodal_document_extraction.data_models import Question, RetrievalResult, RetrievedItem
from multimodal_document_extraction.evaluation.retrieval_metrics import (
    evaluate_retrieval_at_k,
    first_perfect_recall_k,
)
from multimodal_document_extraction.utils.run_recording import (
    RESULTS_FIELDS,
    append_results,
    create_run_dir,
    git_state,
)


def _pair(qid, gold, ranking):
    q = Question(question_id=qid, doc_id="d", question="?", evidence_pages=gold)
    items = tuple(
        RetrievedItem(doc_id="d", page_number=p, rank=r) for r, p in enumerate(ranking, 1)
    )
    return q, RetrievalResult(question_id=qid, doc_id="d", method="m", items=items)


def test_first_perfect_recall_k():
    assert first_perfect_recall_k(*_pair("q", [3, 1], [2, 3, 4, 1])) == 4
    assert first_perfect_recall_k(*_pair("q", [2], [2, 3])) == 1
    assert first_perfect_recall_k(*_pair("q", [], [2, 3])) is None
    assert first_perfect_recall_k(*_pair("q", [9], [2, 3])) is None


def test_evaluate_retrieval_at_k_curve():
    pairs = [_pair("q1", [2], [1, 2, 3]), _pair("q2", [1, 3], [1, 2, 3])]
    curve = evaluate_retrieval_at_k(pairs, [3, 1, 2, 5])
    assert list(curve) == [1, 2, 3, 5]
    assert curve[1].perfect_recall.mean == 0.0
    assert curve[2].perfect_recall.mean == 0.5
    assert curve[3].perfect_recall.mean == 1.0
    assert curve[5].perfect_recall.mean == 1.0  # k beyond ranking length keeps all items
    assert curve[1].irrelevant_pages_ratio.mean == pytest.approx(
        0.5
    )  # q1: 1 of 1 irrelevant; q2: 0


def _row(eid, k):
    return {"experiment_id": eid, "top_k": k}


def test_append_results_header_and_unique_ids(tmp_path):
    path = tmp_path / "results.csv"
    append_results(path, [_row("E1", 1), _row("E1", 2)])
    append_results(path, [_row("E2", 1)])
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == RESULTS_FIELDS
        assert [r["experiment_id"] for r in reader] == ["E1", "E1", "E2"]
    with pytest.raises(ValueError, match="already"):
        append_results(path, [_row("E1", 3)])
    with pytest.raises(ValueError, match="unknown"):
        append_results(path, [{"experiment_id": "E3", "bogus": 1}])


def test_append_results_rejects_different_header(tmp_path):
    path = tmp_path / "results.csv"
    path.write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        append_results(path, [_row("E1", 1)])


def test_create_run_dir_refuses_reuse(tmp_path):
    run_dir = create_run_dir(tmp_path, "E1")
    assert run_dir == tmp_path / "runs" / "E1" and run_dir.is_dir()
    with pytest.raises(FileExistsError):
        create_run_dir(tmp_path, "E1")


def test_git_state_in_repo():
    state = git_state()
    assert len(state["commit"]) == 40
    assert isinstance(state["dirty"], bool) and isinstance(state["untracked"], list)
