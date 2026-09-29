import time

import pytest

from multimodal_document_extraction.studies.ladrag.graph_query import (
    GraphQueryEngine,
    QueryError,
    QueryTimeoutError,
    validate_expression,
)
from multimodal_document_extraction.studies.ladrag.graph_retrieval import (
    SCOPE_CROSS_PAGE,
    SCOPE_INTRA_PAGE,
    GraphConsistencyError,
    GraphIndex,
    UnknownNodeError,
    get_community_for_node,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph, GraphMetadata


def _attrs(kind: str, text: str = "") -> dict:
    return {"type": kind, "content": text, "summary": text, "title_or_heading": None}


@pytest.fixture
def graph() -> DocumentGraph:
    """Pages 1, 2, 10 (page 10 checks numeric ordering), plus an isolated singleton node.

    p1: A=page_1-obj_000 (section_header), B=page_1-obj_001 (paragraph)
    p2: C=page_2-obj_000 (figure), D=page_2-obj_001 (paragraph)
    p10: E=page_10-obj_000 (paragraph)   p3: F=page_3-obj_000 (footer, isolated)
    """
    g = DocumentGraph(GraphMetadata(doc_id="d.pdf", num_pages=10))
    g.add_node("page_1-obj_000", 1, 0, _attrs("section_header", "Intro"))
    g.add_node("page_1-obj_001", 1, 1, _attrs("paragraph", "Label words anchor"))
    g.add_node("page_2-obj_000", 2, 0, _attrs("figure", "Figure 2 chart"))
    g.add_node("page_2-obj_001", 2, 1, _attrs("paragraph", "continued text"))
    g.add_node("page_10-obj_000", 10, 0, _attrs("paragraph", "appendix"))
    g.add_node("page_3-obj_000", 3, 0, _attrs("footer", "3"))
    assert g.add_relation("page_1-obj_000", "page_1-obj_001", "next_on_page", "intra_page") is None
    assert g.add_relation("page_2-obj_000", "page_2-obj_001", "next_on_page", "intra_page") is None
    # same-page edge produced by Fig. 11 (origin fig11 must NOT make it cross-page)
    assert g.add_relation("page_1-obj_001", "page_1-obj_000", "is_part_of_section", "fig11") is None
    # cross-page edges, one declared in the "reverse" direction (undirected graph)
    assert g.add_relation("page_2-obj_001", "page_1-obj_001", "continues", "fig11") is None
    assert g.add_relation("page_1-obj_001", "page_10-obj_000", "references", "fig11") is None
    assert g.add_relation("page_2-obj_000", "page_1-obj_000", "is_part_of_section", "fig11") is None
    g.set_communities(
        [
            {"page_1-obj_000", "page_1-obj_001", "page_2-obj_000"},
            {"page_2-obj_001", "page_10-obj_000"},
            {"page_3-obj_000"},
        ]
    )
    return g


@pytest.fixture
def index(graph) -> GraphIndex:
    return GraphIndex(graph)


# --- pages ---------------------------------------------------------------------------------------


def test_node_to_page_and_ordered_unique_pages(index):
    assert index.node_page("page_10-obj_000") == 10
    ids = ["page_2-obj_001", "page_1-obj_000", "page_2-obj_000", "page_10-obj_000"]
    assert index.pages_of(ids) == (2, 1, 10)
    assert index.nodes_in_order()[-1] == "page_10-obj_000"  # numeric, not string order


def test_unknown_node_raises(index):
    with pytest.raises(UnknownNodeError):
        index.node_page("page_9-obj_000")
    with pytest.raises(UnknownNodeError):
        index.neighbors("nonsense")
    with pytest.raises(UnknownNodeError):
        index.get_community_for_node(None)


def test_page_attribute_must_match_node_id(graph):
    graph.graph.nodes["page_2-obj_000"]["page"] = 3  # corrupted metadata
    with pytest.raises(GraphConsistencyError, match="does not match"):
        GraphIndex(graph)


# --- neighbours ----------------------------------------------------------------------------------


def test_one_hop_all_neighbours_are_undirected_and_ordered(index):
    got = index.neighbors("page_1-obj_001")
    assert [n.node_id for n in got] == ["page_1-obj_000", "page_2-obj_001", "page_10-obj_000"]
    first = got[0]
    assert first.types == ("is_part_of_section", "next_on_page")  # merged edge metadata kept
    assert first.sources == ("fig11", "intra_page") and first.cross_page is False
    # reverse direction of the "continues" edge declared from page 2
    assert [n.node_id for n in index.neighbors("page_2-obj_001")] == [
        "page_1-obj_001",
        "page_2-obj_000",
    ]


def test_cross_page_is_decided_by_endpoint_pages_not_type_or_origin(index):
    cross = index.neighbors("page_1-obj_001", scope=SCOPE_CROSS_PAGE)
    assert [n.node_id for n in cross] == ["page_2-obj_001", "page_10-obj_000"]
    intra = index.neighbors("page_1-obj_001", scope=SCOPE_INTRA_PAGE)
    assert [n.node_id for n in intra] == ["page_1-obj_000"]  # fig11 origin, same page → intra
    assert index.is_cross_page("page_2-obj_000", "page_1-obj_000")
    assert not index.is_cross_page("page_1-obj_000", "page_1-obj_001")
    assert len(index.edges(SCOPE_CROSS_PAGE)) == 3 and len(index.edges(SCOPE_INTRA_PAGE)) == 2
    with pytest.raises(ValueError):
        index.neighbors("page_1-obj_001", scope="everything")


def test_relation_type_and_origin_filters(index):
    got = index.neighbors("page_1-obj_000", relation_types=["is_part_of_section"])
    assert [n.node_id for n in got] == ["page_1-obj_001", "page_2-obj_000"]
    got = index.neighbors(
        "page_1-obj_000", relation_types=["is_part_of_section"], scope="cross_page"
    )
    assert [n.node_id for n in got] == ["page_2-obj_000"]
    got = index.neighbors("page_1-obj_000", origins=["intra_page"])
    assert [n.node_id for n in got] == ["page_1-obj_001"]
    assert index.neighbors("page_3-obj_000") == []  # isolated node


# --- ordered expansion (D-021) --------------------------------------------------------------------


def test_ordered_expansion_order_and_duplicate_suppression(index):
    seeds = ["page_2-obj_001", "page_1-obj_001", "page_10-obj_000"]
    items = index.ordered_one_hop_expansion(seeds, scope=SCOPE_CROSS_PAGE)
    assert [(i.node_id, i.role, i.seed_rank) for i in items] == [
        ("page_2-obj_001", "seed", 1),
        ("page_1-obj_001", "neighbor", 1),  # cross-page neighbour of seed 1
        # seed 2 (page_1-obj_001) already emitted, but still expanded:
        ("page_10-obj_000", "neighbor", 2),
        # seed 3 already emitted as a neighbour; its only neighbour too → nothing new
    ]
    assert len({i.node_id for i in items}) == len(items)
    assert items[1].types == ("continues",) and items[1].cross_page is True
    assert index.pages_of(i.node_id for i in items) == (2, 1, 10)


def test_expansion_with_all_edges_orders_by_page_then_node_id(index):
    items = index.ordered_one_hop_expansion(["page_1-obj_000"])
    assert [i.node_id for i in items] == ["page_1-obj_000", "page_1-obj_001", "page_2-obj_000"]
    intra = index.ordered_one_hop_expansion(["page_2-obj_001"], scope=SCOPE_INTRA_PAGE)
    assert index.pages_of(i.node_id for i in intra) == (2,)  # intra-page expansion adds no page


def test_expansion_is_deterministic(graph):
    seeds = ["page_1-obj_001", "page_2-obj_000"]
    runs = [GraphIndex(graph).ordered_one_hop_expansion(seeds) for _ in range(3)]
    assert runs[0] == runs[1] == runs[2]


# --- communities -----------------------------------------------------------------------------------


def test_community_lookup(index):
    members = get_community_for_node("page_2-obj_000", index)
    assert [n for n, _ in members] == ["page_1-obj_000", "page_1-obj_001", "page_2-obj_000"]
    assert members[2][1]["type"] == "figure"
    assert [n for n, _ in index.get_community_for_node("page_3-obj_000")] == ["page_3-obj_000"]


def test_node_without_community_is_its_own_singleton():
    g = DocumentGraph(GraphMetadata(doc_id="d.pdf", num_pages=1))
    g.add_node("page_1-obj_000", 1, 0, _attrs("paragraph"))
    g.add_node("page_1-obj_001", 1, 1, _attrs("paragraph"))
    assert [n for n, _ in GraphIndex(g).get_community_for_node("page_1-obj_001")] == [
        "page_1-obj_001"
    ]


def test_returned_attributes_are_copies(index):
    index.node("page_1-obj_000")["type"] = "changed"
    index.get_community_for_node("page_1-obj_000")[0][1]["type"] = "changed"
    assert index.node("page_1-obj_000")["type"] == "section_header"


# --- safe symbolic query (R13) ---------------------------------------------------------------------


@pytest.fixture
def engine(index) -> GraphQueryEngine:
    return GraphQueryEngine.for_graph(index, timeout_s=2.0)


PAPER_FILTER = (
    "[(node_id, node) for node_id, node in doc_graph.nodes(data=True) "
    "if node.get('type') == 'figure']"
)


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        (PAPER_FILTER, ["page_2-obj_000"]),  # Fig. 5 form
        (
            "[n for n, d in doc_graph.nodes(data=True) if d.get('page') in (1, 10)]",
            ["page_1-obj_000", "page_1-obj_001", "page_10-obj_000"],
        ),
        (
            "[n for n, d in doc_graph.nodes(data=True) if 'label' in (d.get('content') or '').lower()]",
            ["page_1-obj_001"],
        ),
        ("doc_graph.neighbors('page_2-obj_001')", ["page_1-obj_001", "page_2-obj_000"]),
        (
            "[b for a, b, d in doc_graph.edges(data=True) if 'continues' in d.get('types')]",
            ["page_2-obj_001"],
        ),
        ("doc_graph.nodes['page_10-obj_000'].get('type')", "paragraph"),
        ("len(doc_graph.nodes()) + doc_graph.number_of_edges()", 11),
        ("(x for x in range(3))", [0, 1, 2]),  # generators are materialized
        ("sum(d.get('page') for n, d in doc_graph.nodes(data=True))", 19),
    ],
)
def test_allowed_expressions(engine, expression, expected):
    result = engine.evaluate(expression)
    if isinstance(result, list) and result and isinstance(result[0], tuple):
        result = [r[0] for r in result]
    assert result == expected


def test_community_tool_in_sandbox_uses_paper_signature(engine):
    result = engine.evaluate("get_community_for_node('page_10-obj_000', doc_graph)")
    assert [n for n, _ in result] == ["page_2-obj_001", "page_10-obj_000"]
    with pytest.raises(QueryError, match="unknown node"):
        engine.evaluate("get_community_for_node('page_99-obj_000', doc_graph)")


@pytest.mark.parametrize(
    "expression",
    [
        "import os",  # statement
        "x = 1",  # statement
        "__import__('os')",  # dunder name
        "open('secret.txt').read()",  # attribute not allowed / open unavailable
        "open('secret.txt')",  # builtin not available → NameError at runtime
        "doc_graph.__class__",  # dunder attribute
        "doc_graph._nodes",  # private attribute
        "doc_graph.nodes._view",  # private attribute of the accessor
        "get_community_for_node.__globals__",  # function internals
        "().__class__.__bases__[0].__subclasses__()",  # classic escape
        "getattr(doc_graph, 'graph')",  # getattr not available
        "eval('1+1')",  # eval not available
        "type(doc_graph)",  # type not available
        "doc_graph.graph",  # attribute outside the facade
        "'a'.format(x=1)",  # str.format not allowed
        "2 ** 100",  # power
        "[0] * 10",  # multiplication
        "1 << 40",  # shift
        "10000000",  # constant too large
        "(y := 3)",  # walrus
        "f'{doc_graph}'",  # f-string
        "lambda: (yield)",  # yield
        "sum([[1], [2]], [])",  # list concatenation through sum
        "doc_graph.nodes().append('x')",  # mutating method
        "dict(**{'a': 1})",  # ** unpacking keyword
        "",  # empty
    ],
)
def test_rejected_expressions(engine, expression):
    with pytest.raises(QueryError):
        engine.evaluate(expression)


def test_static_validation_rejects_before_execution():
    with pytest.raises(QueryError, match="disallowed"):
        validate_expression("[1 for _x in range(3)]")
    with pytest.raises(QueryError, match="not a single Python expression"):
        validate_expression("a = 1; b = 2")


def test_timeout_guard(index):
    engine = GraphQueryEngine.for_graph(index, timeout_s=0.5)
    started = time.monotonic()
    with pytest.raises(QueryTimeoutError):
        engine.evaluate("[a for a in range(1000000) for b in range(1000000)]")
    assert time.monotonic() - started < 5


def test_result_size_guard(index):
    engine = GraphQueryEngine.for_graph(index, max_result_items=10)
    with pytest.raises(QueryError, match="more than 10 items"):
        engine.evaluate("list(range(11))")


def test_sandbox_cannot_mutate_the_graph(engine, index):
    engine.evaluate("[d.get('type') for n, d in doc_graph.nodes(data=True)]")
    engine.evaluate("doc_graph.nodes['page_1-obj_000'].keys()")
    assert index.node("page_1-obj_000")["type"] == "section_header"
    assert engine.evaluate(PAPER_FILTER) == engine.evaluate(PAPER_FILTER)  # deterministic
