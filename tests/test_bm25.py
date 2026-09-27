from pathlib import Path

import pytest

from multimodal_document_extraction.data_models import Page, Question
from multimodal_document_extraction.datasets.mmlongbench_doc import (
    DEFAULT_RAW_DIR,
    load_mmlongbench_doc,
    load_pages,
)
from multimodal_document_extraction.datasets.subsets import Subset
from multimodal_document_extraction.retrieval.bm25 import METHOD_NAME, BM25Config, BM25PageRetriever


def _pages(*texts, doc_id="d1"):
    return [Page(doc_id=doc_id, page_number=i, text=t) for i, t in enumerate(texts, start=1)]


def _question(text, doc_id="d1", qid="q1"):
    return Question(question_id=qid, doc_id=doc_id, question=text, evidence_pages=[1])


def test_ranks_all_pages_by_score():
    retriever = BM25PageRetriever()
    retriever.index_document(
        "d1",
        _pages(
            "Quarterly revenue grew strongly in 2023.",
            "The cat sat on the mat.",
            "",
            "Revenue table: revenue by segment, revenue growth.",
        ),
    )
    result = retriever.retrieve(_question("What was the revenue growth?"))
    assert result.method == METHOD_NAME
    assert [i.rank for i in result.items] == [1, 2, 3, 4]
    assert result.pages_in_rank_order()[0] == 4  # most revenue mentions
    assert set(result.pages_in_rank_order()[:2]) == {1, 4}
    assert result.retrieved_pages == frozenset({1, 2, 3, 4})
    scores = [i.score for i in result.items]
    assert scores == sorted(scores, reverse=True)
    assert result.metadata["num_positive_scores"] == 2
    assert result.latency_s is not None and result.latency_s >= 0


def test_ties_and_zero_scores_are_ordered_by_page_number():
    retriever = BM25PageRetriever()
    retriever.index_document("d1", _pages("apple", "banana", "cherry", "banana"))
    result = retriever.retrieve(_question("zebra"))  # out of vocabulary -> all zero
    assert result.pages_in_rank_order() == (1, 2, 3, 4)
    assert all(i.score == 0.0 for i in result.items)
    tied = retriever.retrieve(_question("banana"))
    assert tied.pages_in_rank_order()[:2] == (2, 4)


def test_document_without_any_text():
    retriever = BM25PageRetriever()
    retriever.index_document("d1", _pages("", "   ", None))
    result = retriever.retrieve(_question("anything"))
    assert result.pages_in_rank_order() == (1, 2, 3)
    assert result.metadata["empty_index"] is True
    assert result.metadata["num_positive_scores"] == 0


def test_top_k_of_result():
    retriever = BM25PageRetriever()
    retriever.index_document("d1", _pages("alpha beta", "gamma", "beta beta"))
    result = retriever.retrieve(_question("beta"))
    assert result.top_k(2).retrieved_pages == frozenset({1, 3})


def test_documents_are_indexed_separately():
    retriever = BM25PageRetriever()
    retriever.index_document("d1", _pages("solar panels", "wind"))
    retriever.index_document("d2", _pages("wind turbines", "solar", doc_id="d2"))
    r1 = retriever.retrieve(_question("wind", doc_id="d1"))
    r2 = retriever.retrieve(_question("wind", doc_id="d2", qid="q2"))
    assert r1.pages_in_rank_order()[0] == 2 and r2.pages_in_rank_order()[0] == 1
    assert retriever.is_indexed("d1") and not retriever.is_indexed("d3")


def test_errors():
    retriever = BM25PageRetriever()
    with pytest.raises(KeyError):
        retriever.retrieve(_question("x"))
    with pytest.raises(ValueError):
        retriever.index_document("d1", [])
    with pytest.raises(ValueError):
        retriever.index_document("d1", _pages("a", doc_id="d2"))
    with pytest.raises(ValueError):
        retriever.index_document("d1", [Page("d1", 1, "a"), Page("d1", 1, "b")])


def test_config_is_recorded():
    retriever = BM25PageRetriever(BM25Config(k1=1.2, b=0.5))
    retriever.index_document("d1", _pages("a b"))
    config = retriever.retrieve(_question("a")).metadata["config"]
    assert config["k1"] == 1.2 and config["b"] == 0.5 and config["library"].startswith("bm25s ")


# --- Smoke test on the real pilot (no metrics; evaluation is CP-3.2) --------------------------

SPLIT = Path("data/splits/mmlongbench-doc/pilot-v1.json")


@pytest.mark.skipif(
    not (DEFAULT_RAW_DIR / "MANIFEST.json").exists() or not SPLIT.exists(),
    reason="MMLongBench-Doc or pilot split not available",
)
def test_pilot_smoke():
    ds = load_mmlongbench_doc()
    pilot = Subset.load(SPLIT)
    retriever = BM25PageRetriever()
    for doc_id in pilot.doc_ids:
        retriever.index_document(doc_id, load_pages(ds.documents[doc_id]))
    for question in pilot.select(ds.questions):
        result = retriever.retrieve(question)
        num_pages = ds.documents[question.doc_id].num_pages
        assert result.retrieved_pages == frozenset(range(1, num_pages + 1))
        image_only = question.doc_id.startswith("reportq32015")
        assert result.metadata["empty_index"] is image_only
