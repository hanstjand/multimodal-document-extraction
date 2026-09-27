import hashlib
import json

import pytest

from multimodal_document_extraction.studies.ladrag import prompts
from multimodal_document_extraction.studies.ladrag.prompts import (
    FIG09,
    FIG10,
    FIG11,
    FIG12,
    load_template,
    render_fstring,
    render_graph_construction,
    render_node_extraction,
    render_retriever_agent,
    render_running_memory,
)

# sha256 recorded in prompts/README.md when transcribed (CP-4.1)
EXPECTED_SHA256 = {
    FIG09: "dd7484aa3779964d464dc6999636638664b5290672baf0235926a2e03492877f",
    FIG10: "2b799af74146ec8ef8ccdcbd7e20717f08abcfd9f75986246431bb8350f12a1b",
    FIG11: "895f5fed42857f3de872f6fbaedcadb81d760e297ea82719471ef9cadb4cd5cf",
    FIG12: "4af9a876d8c406b91fa2055eed856b1bfd08fa4348a536f35e2ccd4aa42c9259",
}


@pytest.mark.parametrize("name", sorted(EXPECTED_SHA256))
def test_templates_unchanged_since_transcription(name):
    data = (prompts.PROMPT_DIR / name).read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED_SHA256[name]


def test_node_extraction_prefix():
    text = render_node_extraction("page_7")
    assert "'page_7-obj_003'" in text and "prefix 'page_7'" in text
    assert "{}" not in text and "{{" not in text


def test_running_memory_renders_json_and_unescapes_template():
    memory = {
        "section_queue": [{"text": "Intro", "object_id": "page_1-obj_001"}],
        "active_entities": [],
    }
    candidates = [{"text": "Methods", "object_id": "page_2-obj_001"}]
    text = render_running_memory(memory, candidates)
    assert json.dumps(memory["section_queue"], indent=2) in text
    assert json.dumps(candidates, indent=2) in text
    assert '{ "text": ..., "object_id": ... }' in text  # {{ }} escapes resolved
    assert "{{" not in text and "json.dumps" not in text
    assert "...page_{ page number}..." in text


def test_running_memory_falls_back_to_whole_memory_like_the_paper():
    text = render_running_memory({"active_entities": []}, [])
    assert json.dumps({"active_entities": []}, indent=2) in text


def test_graph_construction_keeps_inserted_braces_intact():
    objects = json.dumps([{"object_id": "page_2-obj_001", "content": "literal {{braces}} in text"}])
    text = render_graph_construction(objects, "[]", {"section_queue": []})
    assert "literal {{braces}} in text" in text  # values are never unescaped
    assert '"type": "is_part_of_section"' in text
    assert "{extracted_objects_text}" not in text and "{{" not in text.replace("{{braces}}", "")


def test_retriever_agent():
    text = render_retriever_agent("doc.pdf", 'How many "charts"?')
    assert "do_semantic_search(query, doc.pdf)" in text
    assert 'question: "How many "charts"?"' in text
    assert "{semantic_search,graph_filter,graph_contextualize,DONE}" in text


def test_render_fstring_requires_each_placeholder_once():
    with pytest.raises(ValueError):
        render_fstring("{a} {a}", {"{a}": "x"})
    with pytest.raises(ValueError):
        render_fstring("{a}", {"{b}": "x"})
    assert render_fstring("{{x}} {a} }}", {"{a}": "{{v}}"}) == "{x} {{v}} }"


def test_templates_are_cached():
    assert load_template(FIG09) is load_template(FIG09)
