import hashlib
import math
import re

import numpy as np
import pytest

from multimodal_document_extraction.retrieval.dense import DenseModelSpec
from multimodal_document_extraction.studies.ladrag.graph_retrieval import GraphIndex
from multimodal_document_extraction.studies.ladrag.node_retrieval import (
    BM25NodeRetriever,
    DenseNodeConfig,
    DenseNodeRetriever,
    node_text,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph, GraphMetadata

SPEC = DenseModelSpec("fake", "fake/model", "rev", "query: ", "passage: ", max_seq_length=12)
CONFIG = DenseNodeConfig(text_field="r10", window_tokens=12, overlap_tokens=3)


class FakeEncoder:
    """Whitespace tokens; bag-of-words hashed into 256 dims, L2-normalized (as in test_dense)."""

    num_special_tokens = 2

    def __init__(self):
        self.calls = 0

    def token_offsets(self, text):
        return [m.span() for m in re.finditer(r"\S+", text)]

    def num_tokens(self, text):
        return len(self.token_offsets(text))

    def encode(self, texts):
        self.calls += 1
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\S+", text.lower()):
                if word in {"query:", "passage:"}:
                    continue
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


def _add(g, node_id, page, order, kind, summary, content):
    g.add_node(
        node_id,
        page,
        order,
        {"type": kind, "summary": summary, "content": content, "title_or_heading": None},
    )


@pytest.fixture
def index() -> GraphIndex:
    g = DocumentGraph(GraphMetadata(doc_id="d.pdf", num_pages=10))
    long_content = " ".join(f"w{i}" for i in range(30)) + " zebra"  # "zebra" only at the end
    _add(g, "page_10-obj_000", 10, 0, "paragraph", "appendix notes", "extra material")
    _add(g, "page_1-obj_000", 1, 0, "section_header", "Introduction", "Introduction")
    _add(g, "page_1-obj_001", 1, 1, "paragraph", "long text", long_content)
    _add(g, "page_2-obj_000", 2, 0, "table", "phone buttons", [{"cells": ["Power", "on/off"]}])
    _add(g, "page_2-obj_001", 2, 1, "footer", None, None)  # no text at all
    _add(g, "page_3-obj_000", 3, 0, "paragraph", "same text", "identical")
    _add(g, "page_3-obj_001", 3, 1, "paragraph", "same text", "identical")
    return GraphIndex(g)


@pytest.fixture
def dense(index) -> DenseNodeRetriever:
    retriever = DenseNodeRetriever(SPEC, FakeEncoder(), CONFIG)
    retriever.index_graph(index)
    return retriever


def test_node_text_r10_and_summary():
    attrs = {"summary": "S", "content": "C"}
    assert node_text(attrs, "r10") == ("S\nC", False)
    assert node_text(attrs, "summary") == ("S", False)
    assert node_text({"summary": None, "content": None}, "r10") == ("\n", False)
    text, converted = node_text({"summary": "t", "content": [{"cells": ["a"]}]}, "r10")
    assert converted and text == 't\n[{"cells": ["a"]}]'
    with pytest.raises(ValueError):
        node_text(attrs, "content")


def test_all_nodes_indexed_in_node_order_with_pages(dense):
    doc = dense.indices["d.pdf"]
    ids = [r.node_id for r in doc.records]
    assert ids == [
        "page_1-obj_000",
        "page_1-obj_001",
        "page_2-obj_000",
        "page_2-obj_001",
        "page_3-obj_000",
        "page_3-obj_001",
        "page_10-obj_000",
    ]
    assert len(set(ids)) == len(ids)
    assert [r.page for r in doc.records] == [1, 1, 2, 2, 3, 3, 10]
    assert doc.records[2].node_type == "table" and doc.records[2].converted_non_string
    stats = doc.stats()
    assert stats["nodes"] == 7 and stats["unscored_nodes"] == 1
    assert stats["multi_window_nodes"] == 1 and stats["converted_non_string"] == 1


def test_long_node_windowing_and_maxp(dense):
    doc = dense.indices["d.pdf"]
    long_record = doc.records[1]
    assert long_record.num_windows > 1
    # every token is covered (no truncation): the last word is found through a later window
    hits = dense.rank_nodes("zebra", "d.pdf")
    assert hits[0].node_id == "page_1-obj_001" and hits[0].score > 0


def test_empty_node_is_unscored_and_ranked_last(dense):
    hits = dense.rank_nodes("introduction", "d.pdf")
    assert hits[-1].node_id == "page_2-obj_001" and hits[-1].score is None
    assert all(h.score is not None and math.isfinite(h.score) for h in hits[:-1])
    assert [h.rank for h in hits] == list(range(1, 8))


def test_ties_are_broken_by_node_id_order(dense):
    hits = dense.rank_nodes("identical same text", "d.pdf")
    assert [h.node_id for h in hits[:2]] == ["page_3-obj_000", "page_3-obj_001"]
    assert hits[0].score == hits[1].score


def test_semantic_search_top_k(dense):
    assert len(dense.semantic_search("phone", "d.pdf")) == 7  # top_k 10 > 7 nodes
    top = dense.semantic_search("phone buttons power", "d.pdf", top_k_nodes=2)
    assert [h.rank for h in top] == [1, 2] and top[0].node_id == "page_2-obj_000"
    assert len(dense.semantic_search("x", "d.pdf", top_k_nodes=None)) == 7
    for bad in (0, -1, 2.5, True):
        with pytest.raises(ValueError):
            dense.semantic_search("x", "d.pdf", top_k_nodes=bad)
    with pytest.raises(KeyError):
        dense.semantic_search("x", "other.pdf")


def test_search_is_deterministic(index):
    runs = []
    for _ in range(2):
        retriever = DenseNodeRetriever(SPEC, FakeEncoder(), CONFIG)
        retriever.index_graph(index)
        runs.append(retriever.rank_nodes("appendix material notes", "d.pdf"))
    assert runs[0] == runs[1]
    assert runs[0][0].node_id == "page_10-obj_000"


def test_save_and_load_roundtrip(dense, index, tmp_path):
    dense.save("d.pdf", tmp_path, {"graph": "synthetic"})
    loaded = DenseNodeRetriever(SPEC, FakeEncoder(), CONFIG)
    loaded.load("d.pdf", tmp_path, index)
    assert loaded.rank_nodes("zebra", "d.pdf") == dense.rank_nodes("zebra", "d.pdf")
    other = DenseNodeRetriever(SPEC, FakeEncoder(), DenseNodeConfig("summary", 12, 3))
    with pytest.raises(ValueError, match="different config"):
        other.load("d.pdf", tmp_path, index)
    index.graph.nodes["page_1-obj_000"]["summary"] = "changed"
    with pytest.raises(ValueError, match="does not match"):
        loaded.load("d.pdf", tmp_path, index)


def test_config_is_validated():
    with pytest.raises(ValueError):
        DenseNodeConfig(text_field="content")
    with pytest.raises(ValueError, match="exceeds"):
        DenseNodeRetriever(SPEC, FakeEncoder(), DenseNodeConfig("r10", 13, 3))


def test_bm25_element_baseline(index):
    bm25 = BM25NodeRetriever(text_field="summary")
    bm25.index_graph(index)
    hits = bm25.rank_nodes("phone buttons", "d.pdf")
    assert hits[0].node_id == "page_2-obj_000" and hits[0].score > 0
    assert hits[-1].node_id == "page_2-obj_001" and hits[-1].score is None  # no summary
    assert len(bm25.semantic_search("phone", "d.pdf", top_k_nodes=100)) == 7
    assert bm25.rank_nodes("phone buttons", "d.pdf") == hits  # deterministic
    # summary-only text: the long content word is not indexed for the element-summary baseline
    zebra = bm25.rank_nodes("zebra", "d.pdf")
    assert all(h.score in (0.0, None) for h in zebra)
    assert [h.node_id for h in zebra[:2]] == ["page_1-obj_000", "page_1-obj_001"]  # ties by ID
