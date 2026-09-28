import json
import re
from pathlib import Path

import pymupdf
import pytest

from multimodal_document_extraction.studies.ladrag.ingestion import (
    DocumentIngestor,
    IngestionConfig,
    JsonReplyError,
    normalize_objects_container,
    parse_json_reply,
    parse_objects_reply,
    render_page,
)
from multimodal_document_extraction.studies.ladrag.models import (
    TASK_GRAPH_CONSTRUCTION,
    TASK_NODE_EXTRACTION,
    TASK_RUNNING_MEMORY,
    GenerationRequest,
    MockVisionModel,
    ModelReply,
    ScriptedVisionModel,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph
from multimodal_document_extraction.utils.model_cache import ModelCache

# --- fixtures ------------------------------------------------------------------------------------


@pytest.fixture
def pdf(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.pdf"
    doc = pymupdf.open()
    for n in range(1, 4):
        page = doc.new_page(width=612, height=792)
        page.insert_text((72, 72), f"Section {n}", fontsize=18)
        page.insert_text((72, 120), f"Paragraph text on page {n}.")
    doc.save(path)
    doc.close()
    return path


def _page_of(request: GenerationRequest) -> int:
    """Page of a node-extraction request (from the Fig. 9 ID prefix)."""
    assert request.task == TASK_NODE_EXTRACTION
    return int(re.search(r"prefix 'page_(\d+)'", request.prompt).group(1))


def _graph_core(graph: DocumentGraph) -> dict:
    data = graph.to_dict()
    return {"nodes": data["nodes"], "edges": data["edges"]}


class CrashingModel:
    """Delegates to MockVisionModel but raises once on a given page's node extraction."""

    def __init__(self, crash_page: int) -> None:
        self.inner = MockVisionModel()
        self.model_id = self.inner.model_id
        self.crash_page = crash_page
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> ModelReply:
        self.calls.append(request)
        if (
            request.task == TASK_NODE_EXTRACTION
            and f"prefix 'page_{self.crash_page}'" in request.prompt
        ):
            raise RuntimeError("simulated crash (e.g. GPU out of memory)")
        return self.inner.generate(request)


# --- rendering and JSON parsing ------------------------------------------------------------------


def test_render_page_is_one_based_and_scales(pdf):
    image = render_page(pdf, 1, dpi=72)
    assert (image.width, image.height) == (612, 792)
    assert image.png.startswith(b"\x89PNG")
    small = render_page(pdf, 3, dpi=300, max_side_px=200)
    assert max(small.width, small.height) <= 200
    assert render_page(pdf, 1, dpi=72).sha256 == image.sha256  # deterministic
    for bad in (0, 4):
        with pytest.raises(ValueError):
            render_page(pdf, bad)


@pytest.mark.parametrize(
    ("text", "expected", "value"),
    [
        ('[{"a": 1}]', list, [{"a": 1}]),
        ('```json\n[{"a": 1}]\n```', list, [{"a": 1}]),
        ('Here you go:\n{"section_queue": []} thanks', dict, {"section_queue": []}),
        ('noise [unclosed\n{"x": 1}', dict, {"x": 1}),
        ('[1, 2]\n{"k": "v"}', dict, {"k": "v"}),
    ],
)
def test_parse_json_reply(text, expected, value):
    assert parse_json_reply(text, expected) == value


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("I cannot help with that.", list),
        ('[{"a": 1}]', dict),  # the object is inside the list: never taken as the answer
        ("{broken", dict),
        ("", list),
        ('Inline only: {"x": 1}', dict),  # not at the start of a line
    ],
)
def test_parse_json_reply_errors(text, expected):
    with pytest.raises(JsonReplyError):
        parse_json_reply(text, expected)


def test_lenient_escapes_for_latex():
    raw = r'{"content": "loss $\mathcal{L}$, \( A_{h,l} \), \frac{1}{2}, \beta, line\nbreak, \"q\", é"}'
    notes = []
    value = parse_json_reply(raw, dict, notes)
    assert (
        value["content"]
        == 'loss $\\mathcal{L}$, \\( A_{h,l} \\), \\frac{1}{2}, \\beta, line\nbreak, "q", é'
    )
    assert notes == ["lenient_escapes"]
    strict_notes = []
    assert (
        parse_json_reply('{"a": "b\\nc"}', dict, strict_notes) == {"a": "b\nc"}
        and strict_notes == []
    )


def test_truncated_structure_is_not_salvaged():
    truncated = '```json\n[\n  {\n    "type": "paragraph",\n    "content": "a"\n  },\n  {\n    "type": "table",\n    "content": "Method | Label'
    with pytest.raises(JsonReplyError):
        parse_objects_reply(truncated)


# --- end to end with MockVisionModel -------------------------------------------------------------


def test_mock_end_to_end(pdf, tmp_path):
    model = MockVisionModel()
    result = DocumentIngestor(model).ingest("synthetic.pdf", pdf, tmp_path / "out")
    graph = result.graph
    assert graph.validate() == []
    stats = graph.stats()
    assert stats["nodes"] == 9 and stats["pages_with_nodes"] == 3
    # per page: next_on_page 1-2, 2-3; is_part_of_section 2-1, 3-1; continues page n -> page n-1
    assert stats["edge_types"] == {"continues": 2, "is_part_of_section": 6, "next_on_page": 6}
    assert stats["edges"] == 11  # (1,2) carries next_on_page + is_part_of_section
    assert stats["communities"] >= 1
    assert graph.node("page_2-obj_002")["type"] == "paragraph"
    assert graph.graph.has_edge("page_3-obj_002", "page_2-obj_002")
    assert [r.task for r in model.calls] == [
        TASK_NODE_EXTRACTION,
        TASK_RUNNING_MEMORY,
        TASK_GRAPH_CONSTRUCTION,
    ] * 3
    assert model.calls[0].images and not model.calls[1].images  # Fig. 10 is text-only
    summary = result.summary
    assert (
        summary["pages_processed"] == 3 and summary["calls"] == 9 and summary["cached_calls"] == 0
    )
    assert summary["flags"] == {} and summary["json_repairs"] == 0
    loaded = DocumentGraph.load(tmp_path / "out" / "graph.json")
    assert loaded.to_json() == graph.to_json()
    assert loaded.metadata.ingestion_model == "mock"
    assert loaded.metadata.config["community_seed"] == 0
    assert loaded.metadata.provenance["pages_ingested"] == [1, 2, 3]
    record = json.loads((tmp_path / "out" / "pages" / "page_0002.json").read_text(encoding="utf-8"))
    assert record["memory"]["section_queue"][-1]["object_id"] == "page_2-obj_001"
    assert (
        json.loads((tmp_path / "out" / "summary.json").read_text(encoding="utf-8"))[
            "pages_processed"
        ]
        == 3
    )


def test_subset_of_pages(pdf, tmp_path):
    result = DocumentIngestor(MockVisionModel()).ingest("d", pdf, tmp_path / "out", pages=[2, 3])
    assert result.graph.pages() == [2, 3]
    assert result.graph.metadata.num_pages == 3
    with pytest.raises(ValueError):
        DocumentIngestor(MockVisionModel()).ingest("d", pdf, tmp_path / "x", pages=[3, 2])


# --- JSON failures and repair --------------------------------------------------------------------


def _mock_with_overrides(overrides):
    mock = MockVisionModel()

    def script(request):
        reply = overrides(request)
        return mock.generate(request).text if reply is None else reply

    return ScriptedVisionModel(script)


def test_invalid_json_is_repaired(pdf, tmp_path):
    def overrides(request):
        if (
            request.task == TASK_NODE_EXTRACTION
            and _page_of(request) == 2
            and "previous output" not in request.prompt
        ):
            return "Sorry, here is a description instead of JSON."
        return None

    model = _mock_with_overrides(overrides)
    result = DocumentIngestor(model).ingest("d", pdf, tmp_path / "out")
    assert result.summary["json_repairs"] == 1 and result.summary["flags"] == {}
    assert result.graph.stats()["nodes"] == 9
    repair = [r for r in model.calls if "previous output was not valid JSON" in r.prompt]
    assert len(repair) == 1 and repair[0].prompt.endswith("Return only the JSON list.")


def test_unrepairable_json_flags_page_and_continues(pdf, tmp_path):
    def overrides(request):
        if request.task == TASK_NODE_EXTRACTION and _page_of(request) == 2:
            return "not json at all"
        return None

    model = _mock_with_overrides(overrides)
    result = DocumentIngestor(model).ingest("d", pdf, tmp_path / "out")
    assert result.summary["flags"] == {
        "json_invalid:node_extraction": 1,
        "graph_construction_skipped:no_nodes": 1,  # R21
    }
    assert result.graph.pages() == [1, 3]
    assert result.graph.validate() == []
    assert len(model.calls) == 3 + 2 + 3  # page 2: A + repair only (no B, no D)


@pytest.mark.parametrize(
    ("value", "shape", "ids"),
    [
        ([{"type": "a", "object_id": "x"}], "list", ["x"]),
        ({"type": "figure", "content": "c", "object_id": "x"}, "single_object", ["x"]),
        (
            {
                "page_9-obj_001": {"type": "paragraph"},
                "page_9-obj_002": {"type": "title", "object_id": "own"},
            },
            "id_map",
            ["page_9-obj_001", "own"],
        ),
        ({"objects": [{"type": "table", "object_id": "t"}]}, "wrapped_list", ["t"]),
    ],
)
def test_normalize_objects_container(value, shape, ids):
    objects, got_shape = normalize_objects_container(value)
    assert got_shape == shape
    assert [o.get("object_id") for o in objects] == ids


def test_normalize_objects_container_rejects_other_dicts():
    for bad in ({"a": 1, "b": 2}, {"x": {"no_known_field": 1}}, "text", 5):
        with pytest.raises(JsonReplyError):
            normalize_objects_container(bad)


def test_parse_objects_reply_skips_unusable_values():
    text = (
        'Note {"a": 1} then ```json\n{"page_1-obj_001": {"type": "paragraph", "content": "x"}}\n```'
    )
    objects, shape = parse_objects_reply(text)
    assert shape == "id_map" and objects[0]["object_id"] == "page_1-obj_001"


def test_single_object_reply_becomes_one_node(pdf, tmp_path):
    def overrides(request):
        if request.task == TASK_NODE_EXTRACTION:
            page = _page_of(request)
            return json.dumps(
                {"type": "figure", "content": f"chart {page}", "object_id": f"page_{page}-obj_001"}
            )
        return None

    result = DocumentIngestor(_mock_with_overrides(overrides)).ingest(
        "d", pdf, tmp_path / "out", pages=[1]
    )
    assert result.summary["flags"] == {"container_normalized:single_object": 1}
    assert list(result.graph.graph.nodes) == ["page_1-obj_001"]
    assert result.summary["json_repairs"] == 0


# --- IDs, relations, memory ----------------------------------------------------------------------


def test_bad_ids_are_normalized_and_bad_relations_rejected(pdf, tmp_path):
    def overrides(request):
        if request.task == TASK_NODE_EXTRACTION:
            page = _page_of(request)
            return json.dumps(
                [
                    {"type": "Title", "content": f"T{page}", "object_id": f"page_{page}-obj_1"},
                    {
                        "type": "paragraph",
                        "content": "a",
                        "object_id": f"page_{page}-obj_1",
                    },  # duplicate
                    {"type": "table", "content": [["x", 1]], "object_id": "wrong"},
                    "not an object",
                    {
                        "type": "figure",
                        "content": "fig",
                        "bbox": [1, 2, 3, 4],
                    },  # no id, extra field
                ]
            )
        if request.task == TASK_GRAPH_CONSTRUCTION:
            return json.dumps(
                {
                    "updated_memory": {"section_queue": [], "active_entities": "oops"},
                    "cross_page_relationships": [
                        {
                            "from_object": "page_1-obj_002",
                            "to_object": "page_9-obj_001",
                            "type": "references",
                        },
                        {
                            "from_object": "page_1-obj_002",
                            "to_object": "page_1-obj_001",
                            "type": "explains",
                        },
                        42,
                    ],
                }
            )
        return None

    result = DocumentIngestor(_mock_with_overrides(overrides)).ingest(
        "d", pdf, tmp_path / "out", pages=[1]
    )
    graph = result.graph
    assert sorted(graph.graph.nodes) == [
        "page_1-obj_001",
        "page_1-obj_002",
        "page_1-obj_003",
        "page_1-obj_004",
    ]
    assert graph.node("page_1-obj_001")["type"] == "title"
    assert graph.node("page_1-obj_003")["content"] == '[["x", 1]]'
    assert graph.node("page_1-obj_004")["extra_fields"] == {"bbox": [1, 2, 3, 4]}
    summary = result.summary
    assert summary["ids_reassigned"] == 3
    assert summary["rejected_relations"] == {"not an object": 1, "unknown endpoint": 1}
    assert "explains" in graph.graph.edges["page_1-obj_001", "page_1-obj_002"]["types"]
    flags = summary["flags"]
    assert flags["non_object_items_dropped"] == 1
    assert flags["memory_key_kept:active_entities"] == 1
    assert flags["memory_key_kept:semantic_topics"] == 1
    record = json.loads((tmp_path / "out" / "pages" / "page_0001.json").read_text(encoding="utf-8"))
    assert record["memory"]["section_queue"] == [
        {"text": "T1", "object_id": "page_1-obj_001"}
    ]  # from [B]


def test_invalid_section_queue_is_rejected(pdf, tmp_path):
    def overrides(request):
        if request.task == TASK_RUNNING_MEMORY:
            return json.dumps({"section_queue": [{"title": "missing text/object_id"}]})
        return None

    result = DocumentIngestor(_mock_with_overrides(overrides)).ingest(
        "d", pdf, tmp_path / "out", pages=[1]
    )
    assert result.summary["flags"] == {"section_queue_rejected": 1}


# --- cache ---------------------------------------------------------------------------------------


def test_cache_makes_reruns_free_and_identical(pdf, tmp_path):
    cache = ModelCache(tmp_path / "cache")
    first = DocumentIngestor(MockVisionModel(), cache=cache).ingest("d", pdf, tmp_path / "run1")
    second_model = MockVisionModel()
    second = DocumentIngestor(second_model, cache=cache).ingest("d", pdf, tmp_path / "run2")
    assert second_model.calls == []
    assert second.summary["cached_calls"] == second.summary["calls"] == 9
    assert _graph_core(first.graph) == _graph_core(second.graph)


# --- resume after interruption -------------------------------------------------------------------


def test_resume_after_crash_continues_at_failed_page(pdf, tmp_path):
    out = tmp_path / "out"
    crashing = CrashingModel(crash_page=3)
    with pytest.raises(RuntimeError, match="simulated crash"):
        DocumentIngestor(crashing).ingest("d", pdf, out)
    assert sorted(p.name for p in (out / "pages").iterdir()) == ["page_0001.json", "page_0002.json"]
    assert not (out / "graph.json").exists()

    resumed_model = MockVisionModel()
    resumed = DocumentIngestor(resumed_model).ingest("d", pdf, out)
    extraction = [r for r in resumed_model.calls if r.task == TASK_NODE_EXTRACTION]
    assert [_page_of(r) for r in extraction] == [3]  # pages 1-2 not re-run
    assert len(resumed_model.calls) == 3  # A, B, D for page 3 only
    assert resumed.summary["pages_resumed"] == 2 and resumed.summary["pages_processed"] == 3

    reference = DocumentIngestor(MockVisionModel()).ingest("d", pdf, tmp_path / "reference")
    assert _graph_core(resumed.graph) == _graph_core(reference.graph)


def test_resume_refuses_mismatched_runs_unless_restart(pdf, tmp_path):
    out = tmp_path / "out"
    DocumentIngestor(MockVisionModel()).ingest("d", pdf, out)
    other = IngestionConfig(community_seed=1)
    with pytest.raises(ValueError, match="fingerprint"):
        DocumentIngestor(MockVisionModel(), other).ingest("d", pdf, out)
    model = MockVisionModel()
    result = DocumentIngestor(model, other).ingest("d", pdf, out, restart=True)
    assert len(model.calls) == 9 and result.summary["pages_resumed"] == 0
    assert result.graph.metadata.config["community_seed"] == 1


def test_config_validation():
    with pytest.raises(ValueError):
        IngestionConfig(community_algorithm="leiden")
    assert IngestionConfig().to_dict()["section_types"] == ["title", "section_header"]


def test_extract_nodes_only_step_a(pdf, tmp_path):
    model = MockVisionModel()
    record = DocumentIngestor(model).extract_nodes(pdf, 2)
    assert [r.task for r in model.calls] == [TASK_NODE_EXTRACTION]  # no B, no D
    assert [o["object_id"] for o in record["objects"]] == [
        "page_2-obj_001",
        "page_2-obj_002",
        "page_2-obj_003",
    ]
    assert record["flags"] == [] and record["repairs"] == 0 and record["image"]["width"] > 0
