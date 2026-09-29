import pytest

from multimodal_document_extraction.studies.ladrag.expansion_eval import (
    adjacent_pages,
    condition_pages,
    irrelevant_pages_ratio,
    paired_comparison,
    perfect_recall,
    reachability,
    truncate,
    unbudgeted_sets,
)
from multimodal_document_extraction.studies.ladrag.graph_retrieval import GraphIndex
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph, GraphMetadata


@pytest.fixture
def index() -> GraphIndex:
    """Pages 1–8. Edges: p2-obj0 — p7-obj0 (cross), p2-obj0 — p2-obj1 (intra),
    p7-obj0 — p8-obj0 (cross, two hops from p2)."""
    g = DocumentGraph(GraphMetadata(doc_id="d.pdf", num_pages=8))
    for page in range(1, 9):
        g.add_node(f"page_{page}-obj_000", page, 0, {"type": "paragraph"})
    g.add_node("page_2-obj_001", 2, 1, {"type": "paragraph"})
    g.add_relation("page_2-obj_000", "page_7-obj_000", "continues", "fig11")
    g.add_relation("page_2-obj_000", "page_2-obj_001", "next_on_page", "intra_page")
    g.add_relation("page_7-obj_000", "page_8-obj_000", "references", "fig11")
    return GraphIndex(g)


RANKING = [  # full node ranking (semantic), gold-free
    "page_2-obj_000",
    "page_5-obj_000",
    "page_2-obj_001",
    "page_1-obj_000",
    "page_3-obj_000",
    "page_4-obj_000",
    "page_6-obj_000",
    "page_7-obj_000",
    "page_8-obj_000",
]


def test_conditions_and_truncation(index):
    a = condition_pages("A", index, RANKING, 8, m=2)
    assert a == [2, 5, 1, 3, 4, 6, 7, 8]
    b = condition_pages("B", index, RANKING, 8, m=2)
    assert b[:3] == [2, 7, 5]  # neighbour page 7 displaces lower-ranked semantic pages
    assert condition_pages("C", index, RANKING, 8, m=2) == a  # intra-page expansion = A
    d = condition_pages("D", index, RANKING, 8, m=2)
    assert d[:6] == [2, 1, 3, 5, 4, 6]  # p-1 then p+1 per seed page
    for pages in (a, b, d):
        assert len(pages) == len(set(pages))
        for k in (1, 3, 5, 10):
            assert len(truncate(pages, k)) == min(k, len(pages))


def test_adjacent_pages_stay_in_range():
    assert adjacent_pages(1, 8) == [2] and adjacent_pages(8, 8) == [7]
    assert adjacent_pages(4, 8) == [3, 5]


def test_unbudgeted_sets(index):
    sets = unbudgeted_sets(index, RANKING, 8, m=2)
    assert sets["A"] == [2, 5]
    assert sets["B"] == [2, 5, 7]
    assert sets["C"] == [2, 5]
    assert sets["D"] == [2, 5, 1, 3, 4, 6]


def test_metrics():
    assert perfect_recall([2, 7], [2, 7, 5]) == 1.0 and perfect_recall([2, 7], [2]) == 0.0
    assert perfect_recall([], [1]) is None
    assert irrelevant_pages_ratio([2], [2, 5]) == 0.5 and irrelevant_pages_ratio([2], []) == 0.0


def test_reachability_classes(index):
    r = reachability(index, RANKING, [2, 7], 8, m=2)
    assert r["primary_class"] == "expansion_completes" and r["graph_completes"]
    assert not r["adjacent_completes"] and r["gold_added_by_graph"] == [7]
    assert r["missing_gold_detail"][0]["graph_distance"] == "1"
    r = reachability(index, RANKING, [2, 8], 8, m=2)
    assert r["primary_class"] == "expansion_adds_only_irrelevant" and r["gold_unreachable"]
    assert r["missing_gold_detail"][0]["graph_distance"] == "2"
    assert r["irrelevant_added_by_graph"] == [7]
    r = reachability(index, RANKING, [5, 6], 8, m=2)
    assert r["adjacent_completes"] and r["missing_gold_detail"][0]["is_seed_page_pm1"]
    assert reachability(index, RANKING, [2], 8, m=2)["primary_class"] == (
        "semantic_already_complete"
    )
    r = reachability(index, ["page_5-obj_000", *RANKING], [3], 8, m=1)
    assert r["primary_class"] == "no_expansion_possible"
    assert r["missing_gold_detail"][0]["graph_distance"] == "unreachable"


def test_paired_comparison_counts():
    rows = [
        {"question_id": f"q{i}", "doc_id": f"d{i % 2}", "metrics": {
            "B": {"1": {"pr": b}}, "A": {"1": {"pr": a}}}}
        for i, (b, a) in enumerate([(1.0, 0.0), (0.0, 0.0), (0.0, 1.0), (1.0, 1.0)])
    ]  # fmt: skip
    out = paired_comparison(rows, "pr", "B", "A", 1, lambda x, y: x > y, n=200)
    assert (out["wins"], out["ties"], out["losses"]) == (1, 2, 1)
    assert out["mean_difference"] == 0.0 and out["win_question_ids"] == ["q0"]
    lo, hi = out["question_bootstrap_95"]
    assert lo <= 0.0 <= hi
