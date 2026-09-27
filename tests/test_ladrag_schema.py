import json

import networkx as nx
import pytest

from multimodal_document_extraction.studies.ladrag.schema import (
    DEFAULT_SECTION_TYPES,
    EXTRACTED_FIELDS,
    MEMORY_KEYS,
    RECONSTRUCTED_NODE_FIELDS,
    RELATION_NEXT_ON_PAGE,
    SCHEMA_VERSION,
    SOURCE_FIG11,
    SOURCE_INTRA_PAGE,
    DocumentGraph,
    GraphMetadata,
    assign_ids,
    initial_memory,
    make_node_id,
    normalize_object,
    page_prefix,
    parse_node_id,
    validate_memory,
)


def _meta(**kw):
    base = {
        "doc_id": "doc.pdf",
        "num_pages": 3,
        "created_at": "2026-09-27T00:00:00+00:00",
        "created_by": "tests",
        "ingestion_model": "scripted",
        "config": {"community": {"algorithm": "louvain", "resolution": 1.0, "seed": 0}},
        "provenance": {"dataset": "synthetic"},
    }
    return GraphMetadata(**{**base, **kw})


def _obj(**kw):
    return normalize_object({"type": "paragraph", "content": "text", "summary": "sum", **kw})


def _graph():
    g = DocumentGraph(_meta())
    g.add_node("page_1-obj_001", 1, 0, _obj(type="Section_Header", content="Intro"))
    g.add_node("page_1-obj_002", 1, 1, _obj(object_id="page_1-obj_2", bbox=[1, 2, 3, 4]))
    g.add_node("page_2-obj_001", 2, 0, _obj(type="figure"))
    return g


# --- IDs (1-based pages, page_{n}-obj_{k:03d}) --------------------------------------------------


def test_node_id_roundtrip_and_prefix():
    assert make_node_id(22, 2) == "page_22-obj_002"  # format seen in the paper's Fig. 6
    assert parse_node_id("page_22-obj_002") == (22, 2)
    assert parse_node_id("page_3-obj_7") == (3, 7)
    assert parse_node_id("page_0-obj_001") is None  # pages are 1-based
    assert parse_node_id("doc/page_3-obj_7") is None
    assert parse_node_id(None) is None
    assert page_prefix(4) == "page_4"
    for bad in [(0, 1), (1, -1), (True, 1), (1.0, 1)]:
        with pytest.raises(ValueError):
            make_node_id(*bad)
    with pytest.raises(ValueError):
        page_prefix(0)


def test_assign_ids_keeps_valid_and_reassigns_invalid():
    claimed = ["page_3-obj_1", "page_3-obj_001", "page_4-obj_002", None, "obj_9", "page_3-obj_5"]
    result = assign_ids(claimed, page=3)
    assert result.ids == (
        "page_3-obj_001",  # kept
        "page_3-obj_006",  # duplicate index 1 -> next free after max used (5)
        "page_3-obj_007",  # wrong page
        "page_3-obj_008",  # missing
        "page_3-obj_009",  # malformed
        "page_3-obj_005",  # kept
    )
    assert result.reassigned == 4
    assert result.mapping["page_3-obj_1"] == "page_3-obj_001"
    assert result.mapping["obj_9"] == "page_3-obj_009"
    assert assign_ids(claimed, page=3) == result  # deterministic


def test_assign_ids_all_missing_is_sequential():
    assert assign_ids([None, None], page=2).ids == ("page_2-obj_001", "page_2-obj_002")


# --- extracted objects: paper fields vs. reconstructed fields; extras preserved ----------------


def test_field_groups_are_distinguishable():
    assert "type" in EXTRACTED_FIELDS and "summary" in EXTRACTED_FIELDS
    assert not set(EXTRACTED_FIELDS) & set(RECONSTRUCTED_NODE_FIELDS)
    assert {"page", "doc_id", "extra_fields", "community"} <= set(RECONSTRUCTED_NODE_FIELDS)


def test_normalize_object_preserves_unknown_keys_and_claimed_id():
    raw = {
        "type": " Table ",
        "content": [["a", 1]],
        "object_id": "p1-obj_3",
        "bbox": [0, 0, 5, 5],
        "lang": "en",
    }
    obj = normalize_object(raw)
    assert obj["type"] == "table"
    assert obj["content"] == '[["a", 1]]'
    assert obj["summary"] is None
    assert obj["claimed_object_id"] == "p1-obj_3"
    assert obj["extra_fields"] == {"bbox": [0, 0, 5, 5], "lang": "en"}
    assert normalize_object({})["type"] == "unknown"


def test_default_section_types_are_only_a_default():
    assert DEFAULT_SECTION_TYPES == ("title", "section_header")


# --- working memory ------------------------------------------------------------------------------


def test_initial_memory_and_validation():
    memory = initial_memory()
    assert tuple(memory) == MEMORY_KEYS
    assert validate_memory(memory) == []
    memory["section_queue"] = [
        {"text": "1 Intro", "object_id": "page_1-obj_001"},
        [
            {"text": "1.1 A", "object_id": "page_2-obj_001"},
            {"text": "1.2 B", "object_id": "page_2-obj_004"},
        ],
    ]
    memory["active_entities"] = [{"text": "Pew", "object_id": ["page_1-obj_002"]}]
    memory["model_added_key"] = "allowed"
    assert validate_memory(memory) == []


def test_validate_memory_reports_problems():
    assert validate_memory([]) == ["memory is not an object: list"]
    problems = validate_memory({"section_queue": [{"text": "x"}, []], "active_entities": {}})
    assert "missing key 'semantic_topics'" in problems
    assert "'active_entities' is not a list" in problems
    assert "section_queue[0] is not a section or list of sections" in problems
    assert "section_queue[1] is not a section or list of sections" in problems


# --- graph metadata ------------------------------------------------------------------------------


def test_graph_metadata_roundtrip_and_validation():
    meta = _meta()
    assert meta.schema_version == SCHEMA_VERSION
    assert GraphMetadata.from_dict(json.loads(json.dumps(meta.to_dict()))) == meta
    for bad in [{"doc_id": ""}, {"num_pages": 0}, {"num_pages": 2.0}, {"schema_version": "x"}]:
        with pytest.raises(ValueError):
            _meta(**bad)
    with pytest.raises(ValueError, match="unknown"):
        GraphMetadata.from_dict({**meta.to_dict(), "run_id": "E1"})


# --- nodes -------------------------------------------------------------------------------------


def test_nodes_have_plain_dict_attributes_for_agent_filters():
    g = _graph()
    figures = [(n, d) for n, d in g.graph.nodes(data=True) if d.get("type") == "figure"]  # Fig. 5
    assert [n for n, _ in figures] == ["page_2-obj_001"]
    node = g.node("page_1-obj_002")
    assert node["page"] == 1 and node["doc_id"] == "doc.pdf"
    assert node["claimed_object_id"] == "page_1-obj_2"
    assert node["extra_fields"] == {"bbox": [1, 2, 3, 4]}
    assert g.nodes_on_page(1) == ["page_1-obj_001", "page_1-obj_002"]
    assert g.pages() == [1, 2]
    assert g.validate() == []


def test_add_node_validation():
    g = _graph()
    with pytest.raises(ValueError, match="duplicate"):
        g.add_node("page_1-obj_001", 1, 5, _obj())
    with pytest.raises(ValueError, match="does not match"):
        g.add_node("page_2-obj_009", 1, 0, _obj())
    with pytest.raises(ValueError, match="exceeds"):
        g.add_node("page_4-obj_001", 4, 0, _obj())  # num_pages = 3
    with pytest.raises(ValueError, match="order_on_page"):
        g.add_node("page_3-obj_001", 3, -1, _obj())


# --- edges -------------------------------------------------------------------------------------


def test_relations_merge_and_rejections():
    g = _graph()
    assert (
        g.add_relation("page_1-obj_002", "page_1-obj_001", "is_part_of_section", SOURCE_FIG11)
        is None
    )
    assert (
        g.add_relation("page_1-obj_001", "page_1-obj_002", RELATION_NEXT_ON_PAGE, SOURCE_INTRA_PAGE)
        is None
    )
    edge = g.graph.edges["page_1-obj_001", "page_1-obj_002"]
    assert edge["types"] == ["is_part_of_section", "next_on_page"]
    assert edge["sources"] == ["fig11", "intra_page"]
    rejected = g.add_relations(
        [
            {"from_object": "page_2-obj_001", "to_object": "page_1-obj_001", "type": "continues"},
            {"from_object": "page_2-obj_001", "to_object": "page_9-obj_001", "type": "references"},
            {"from_object": "page_2-obj_001", "to_object": "page_2-obj_001", "type": "explains"},
            {"from_object": "page_2-obj_001", "to_object": "page_1-obj_002"},
            "not a dict",
        ],
        SOURCE_FIG11,
    )
    assert [r.reason for r in rejected] == [
        "unknown endpoint",
        "self-loop",
        "missing relation type",
        "not an object",
    ]
    assert g.graph.has_edge("page_1-obj_001", "page_2-obj_001")
    assert not g.graph.is_directed()
    assert g.validate() == []


# --- communities ---------------------------------------------------------------------------------


def test_communities():
    g = _graph()
    g.add_relation("page_1-obj_001", "page_1-obj_002", "next_on_page", SOURCE_INTRA_PAGE)
    g.set_communities([{"page_2-obj_001"}, {"page_1-obj_002", "page_1-obj_001"}])
    assert g.node("page_1-obj_001")["community"] == 0  # ordered by smallest member ID
    assert g.community_members("page_1-obj_002") == ["page_1-obj_001", "page_1-obj_002"]
    assert g.community_members("page_2-obj_001") == ["page_2-obj_001"]
    with pytest.raises(ValueError):
        g.set_communities([{"page_1-obj_001"}])  # missing nodes
    with pytest.raises(ValueError):
        g.set_communities(
            [{"page_1-obj_001", "page_1-obj_002"}, {"page_1-obj_001", "page_2-obj_001"}]
        )
    assert g.node("page_1-obj_001")["community"] == 0  # failed calls leave communities unchanged


def test_louvain_output_is_accepted():
    g = _graph()
    g.add_relation("page_1-obj_001", "page_1-obj_002", "next_on_page", SOURCE_INTRA_PAGE)
    communities = nx.community.louvain_communities(g.graph, weight=None, resolution=1.0, seed=0)
    g.set_communities(communities)
    assert g.stats()["communities"] == len(communities)
    assert g.validate() == []


# --- serialization: deterministic, lossless, validated -------------------------------------------


def _full_graph():
    g = _graph()
    g.add_relation("page_2-obj_001", "page_1-obj_001", "continues", SOURCE_FIG11)
    g.add_relation("page_1-obj_002", "page_1-obj_001", "next_on_page", SOURCE_INTRA_PAGE)
    g.set_communities([{"page_1-obj_001", "page_2-obj_001"}, {"page_1-obj_002"}])
    return g


def test_json_roundtrip_is_lossless_and_deterministic(tmp_path):
    g = _full_graph()
    text = g.to_json()
    restored = DocumentGraph.from_json(text)
    assert restored.to_json() == text  # byte-identical
    assert restored.metadata == g.metadata
    assert restored.node("page_1-obj_002")["extra_fields"] == {"bbox": [1, 2, 3, 4]}
    assert restored.stats() == g.stats()
    data = json.loads(text)
    assert data["edges"][0]["source"] == "page_1-obj_001"  # endpoints ordered
    path = tmp_path / "g" / "graph.json"
    g.save(path)
    assert DocumentGraph.load(path).to_json() == text
    assert b"\r\n" not in path.read_bytes()


def test_insertion_order_does_not_change_json():
    a = _full_graph()
    b = DocumentGraph(_meta())
    b.add_node("page_2-obj_001", 2, 0, _obj(type="figure"))
    b.add_node("page_1-obj_002", 1, 1, _obj(object_id="page_1-obj_2", bbox=[1, 2, 3, 4]))
    b.add_node("page_1-obj_001", 1, 0, _obj(type="Section_Header", content="Intro"))
    b.add_relation("page_1-obj_001", "page_1-obj_002", "next_on_page", SOURCE_INTRA_PAGE)
    b.add_relation("page_1-obj_001", "page_2-obj_001", "continues", SOURCE_FIG11)
    b.set_communities([{"page_1-obj_002"}, {"page_2-obj_001", "page_1-obj_001"}])
    assert a.to_json() == b.to_json()


@pytest.mark.parametrize(
    ("mutate", "match"),
    [
        (lambda d: d.update(schema="other"), "schema"),
        (
            lambda d: d["edges"].append(
                {
                    "source": "page_1-obj_001",
                    "target": "page_3-obj_009",
                    "types": ["x"],
                    "sources": ["fig11"],
                }
            ),
            "unknown node",
        ),
        (lambda d: d["edges"].append(dict(d["edges"][0])), "duplicate edge"),
        (lambda d: d["nodes"].append(dict(d["nodes"][0])), "duplicate node"),
        (lambda d: d["nodes"][0].update(surprise=1), "unknown attributes"),
        (lambda d: d["nodes"][0].update(doc_id="other.pdf"), "doc_id"),
        (lambda d: d["nodes"][0].update(page=2), "does not match"),
        (lambda d: d["edges"][0].update(types=[]), "invalid types"),
        (lambda d: d["nodes"][0].pop("community"), "only some nodes"),
        (lambda d: d["metadata"].update(num_pages=1), "exceeds"),
    ],
)
def test_from_dict_detects_invalid_graphs(mutate, match):
    data = json.loads(_full_graph().to_json())
    mutate(data)
    with pytest.raises(ValueError, match=match):
        DocumentGraph.from_dict(data)


def test_save_refuses_invalid_graph(tmp_path):
    g = _graph()
    g.graph.nodes["page_1-obj_001"]["surprise"] = 1  # bypassing the API
    assert any("unknown attributes" in p for p in g.validate())
    with pytest.raises(ValueError, match="invalid"):
        g.save(tmp_path / "graph.json")


def test_stats():
    g = _graph()
    g.add_relation("page_1-obj_001", "page_1-obj_002", "next_on_page", SOURCE_INTRA_PAGE)
    assert g.stats() == {
        "nodes": 3,
        "edges": 1,
        "pages_with_nodes": 2,
        "edge_types": {"next_on_page": 1},
        "communities": 0,
        "isolated_nodes": 1,
    }
