"""Render the verbatim LAD-RAG prompts (Figs. 9-12) exactly as the paper's Python sources would.

Figs. 9 and 12 are ``str.format`` sources (positional ``{}``, escapes ``{{ }}``). Figs. 10 and 11 are
f-string sources whose placeholders are Python expressions; they are filled by exact placeholder
match, and only the literal template text is unescaped, so inserted values (JSON, page text) are
never altered. See README.md in this directory.
"""

import json
import re
from functools import cache
from pathlib import Path
from typing import Any

PROMPT_DIR = Path(__file__).parent

FIG09 = "fig09_node_extraction.txt"
FIG10 = "fig10_running_memory.txt"
FIG11 = "fig11_graph_construction.txt"
FIG12 = "fig12_retriever_agent.txt"

FIG10_SECTION_QUEUE = "{json.dumps(working_memory.get('section_queue', working_memory), indent=2)}"
FIG10_CANDIDATES = "{json.dumps(candidate_section_objects, indent=2)}"
FIG11_OBJECTS = "{extracted_objects_text}"
FIG11_RELATIONS = "{extracted_relations_text}"
FIG11_MEMORY = "{json.dumps(working_memory, indent=2)}"


@cache
def load_template(name: str) -> str:
    return (PROMPT_DIR / name).read_text(encoding="utf-8")


def _unescape(literal: str) -> str:
    return literal.replace("{{", "{").replace("}}", "}")


def render_fstring(template: str, values: dict[str, str]) -> str:
    """Fill f-string placeholders given verbatim (e.g. ``"{extracted_objects_text}"``).

    Every placeholder must occur exactly once; literal text between placeholders is unescaped.
    """
    for placeholder in values:
        count = template.count(placeholder)
        if count != 1:
            raise ValueError(f"placeholder {placeholder!r} occurs {count} times")
    pattern = re.compile("|".join(re.escape(p) for p in values))
    parts, last = [], 0
    for match in pattern.finditer(template):
        parts.append(_unescape(template[last : match.start()]))
        parts.append(values[match.group(0)])
        last = match.end()
    parts.append(_unescape(template[last:]))
    rendered = "".join(parts)
    return rendered


def render_node_extraction(prefix: str) -> str:
    """Fig. 9 with the object-ID prefix (e.g. ``page_3``)."""
    return load_template(FIG09).format(prefix, prefix)


def render_running_memory(
    working_memory: dict[str, Any], candidate_section_objects: list[dict]
) -> str:
    """Fig. 10 as the paper's f-string would render it."""
    return render_fstring(
        load_template(FIG10),
        {
            FIG10_SECTION_QUEUE: json.dumps(
                working_memory.get("section_queue", working_memory), indent=2
            ),
            FIG10_CANDIDATES: json.dumps(candidate_section_objects, indent=2),
        },
    )


def render_graph_construction(
    extracted_objects_text: str, extracted_relations_text: str, working_memory: dict[str, Any]
) -> str:
    """Fig. 11 as the paper's f-string would render it."""
    return render_fstring(
        load_template(FIG11),
        {
            FIG11_OBJECTS: extracted_objects_text,
            FIG11_RELATIONS: extracted_relations_text,
            FIG11_MEMORY: json.dumps(working_memory, indent=2),
        },
    )


def render_retriever_agent(pdf_name: str, question: str) -> str:
    """Fig. 12 with the document name and question."""
    return load_template(FIG12).format(pdf_name, question)
