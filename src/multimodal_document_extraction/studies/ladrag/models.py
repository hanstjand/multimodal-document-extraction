"""Vendor-neutral model interface for LAD-RAG† ingestion (IMPLEMENTATION_SPEC §3; CP-4.3A).

Real models (a local VLM in CP-4.3B, optional API adapters later) implement :class:`VisionModel`.
For framework development and tests there are two deterministic implementations:

- :class:`ScriptedVisionModel` — replies come from a user-supplied function (full control in tests).
- :class:`MockVisionModel` — schema-valid replies derived from the rendered LAD-RAG prompts
  (Figs. 9-11), so the whole pipeline runs end-to-end without any model.

Neither makes network calls or loads model weights.
"""

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Protocol

TASK_NODE_EXTRACTION = "node_extraction"  # Fig. 9, with page image
TASK_RUNNING_MEMORY = "running_memory"  # Fig. 10, text only
TASK_GRAPH_CONSTRUCTION = "graph_construction"  # Fig. 11, with page image


@dataclass(frozen=True)
class ImageInput:
    """A rendered page image (PNG bytes) with its content hash."""

    png: bytes
    sha256: str
    width: int
    height: int


@dataclass(frozen=True)
class GenerationParams:
    temperature: float = 0.0
    max_output_tokens: int = 8192

    def to_dict(self) -> dict[str, Any]:
        return {"temperature": self.temperature, "max_output_tokens": self.max_output_tokens}


@dataclass(frozen=True)
class GenerationRequest:
    task: str
    prompt: str
    images: tuple[ImageInput, ...]
    params: GenerationParams


@dataclass(frozen=True)
class ModelReply:
    text: str
    model_id: str
    usage: dict[str, int] = field(
        default_factory=dict
    )  # prompt_tokens / completion_tokens if known
    latency_s: float = 0.0


class ResourceExhaustedError(RuntimeError):
    """A request failed because a hardware resource ran out (e.g. CUDA out of memory).

    Raised by :class:`VisionModel` implementations after releasing what they can, so the caller may
    retry. ``details`` is JSON-serializable (e.g. memory statistics) and is persisted by ingestion.
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.details = dict(details or {})


class VisionModel(Protocol):
    """Anything that turns a prompt (+ optional page images) into text."""

    model_id: str

    def generate(self, request: GenerationRequest) -> ModelReply: ...


class ScriptedVisionModel:
    """Replies produced by ``script(request)``; every request is recorded in ``calls``."""

    def __init__(
        self, script: Callable[[GenerationRequest], str], model_id: str = "scripted"
    ) -> None:
        self.script = script
        self.model_id = model_id
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> ModelReply:
        self.calls.append(request)
        return ModelReply(text=self.script(request), model_id=self.model_id)


# --- MockVisionModel ------------------------------------------------------------------------------

_PREFIX = re.compile(r"start with the prefix '([^']+)'")


def _between(text: str, start: str, end: str) -> str:
    i = text.index(start) + len(start)
    return text[i : text.index(end, i)].strip()


def _leaf_sections(section_queue: list) -> list[dict]:
    if not section_queue:
        return []
    last = section_queue[-1]
    return list(last) if isinstance(last, list) else [last]


class MockVisionModel:
    """Deterministic, schema-valid stand-in for the ingestion VLM (no model involved).

    - node extraction: one section header and two paragraphs per page, with IDs using the prompt's
      prefix and text derived from the page number and image hash;
    - running memory: appends the candidate sections to the current ``section_queue``;
    - graph construction: links every non-section object to the leaf section(s)
      (``is_part_of_section``) and the page's first paragraph to the previous page's first paragraph
      (``continues``, via ``active_entities``).
    """

    def __init__(self, model_id: str = "mock") -> None:
        self.model_id = model_id
        self.calls: list[GenerationRequest] = []

    def generate(self, request: GenerationRequest) -> ModelReply:
        self.calls.append(request)
        handler = {
            TASK_NODE_EXTRACTION: self._nodes,
            TASK_RUNNING_MEMORY: self._memory,
            TASK_GRAPH_CONSTRUCTION: self._graph,
        }[request.task]
        return ModelReply(text=json.dumps(handler(request), indent=2), model_id=self.model_id)

    @staticmethod
    def _nodes(request: GenerationRequest) -> list[dict]:
        prefix = _PREFIX.search(request.prompt).group(1)
        page = prefix.removeprefix("page_")
        tag = request.images[0].sha256[:8] if request.images else "noimage"
        return [
            {
                "type": "section_header",
                "content": f"Section {page}",
                "title_or_heading": f"Section {page}",
                "position_on_page": "top-left",
                "layout_relation": "at the top of the page",
                "summary": f"Header of section {page}.",
                "visual_attributes": {"bold": True},
                "page_metadata": {"page_number": int(page)},
                "object_id": f"{prefix}-obj_001",
            },
            {
                "type": "paragraph",
                "content": f"Body text of page {page} ({tag}).",
                "title_or_heading": f"Paragraph {page}.1",
                "position_on_page": "center",
                "layout_relation": "below the section header",
                "summary": f"First paragraph of page {page}.",
                "visual_attributes": None,
                "page_metadata": None,
                "object_id": f"{prefix}-obj_002",
            },
            {
                "type": "paragraph",
                "content": f"Second paragraph of page {page}.",
                "title_or_heading": f"Paragraph {page}.2",
                "position_on_page": "bottom",
                "layout_relation": "below the first paragraph",
                "summary": f"Second paragraph of page {page}.",
                "visual_attributes": None,
                "page_metadata": None,
                "object_id": f"{prefix}-obj_003",
            },
        ]

    @staticmethod
    def _memory(request: GenerationRequest) -> dict:
        queue = json.loads(
            _between(
                request.prompt, "**CURRENT SECTION_QUEUE:**", "**CANDIDATE SECTIONS FROM PAGE:**"
            )
        )
        candidates = json.loads(
            _between(
                request.prompt, "**CANDIDATE SECTIONS FROM PAGE:**", "Return only a JSON object"
            )
        )
        if not isinstance(queue, list):
            queue = []
        return {"section_queue": queue + candidates}

    @staticmethod
    def _graph(request: GenerationRequest) -> dict:
        objects = json.loads(
            _between(request.prompt, "CURRENT PAGE OBJECTS:", "CURRENT PAGE RELATIONSHIPS:")
        )
        memory = json.loads(
            _between(request.prompt, "CURRENT WORKING MEMORY:", "Return a JSON object")
        )
        leaves = _leaf_sections(memory.get("section_queue", []))
        relations = [
            {
                "from_object": obj["object_id"],
                "to_object": leaf["object_id"],
                "type": "is_part_of_section",
            }
            for obj in objects
            if obj.get("type") not in {"title", "section_header"}
            for leaf in leaves
        ]
        paragraphs = [o for o in objects if o.get("type") == "paragraph"]
        entities = list(memory.get("active_entities", []))
        if paragraphs and entities:
            relations.append(
                {
                    "from_object": paragraphs[0]["object_id"],
                    "to_object": entities[-1]["object_id"],
                    "type": "continues",
                }
            )
        if paragraphs:
            entities.append(
                {
                    "text": paragraphs[0].get("title_or_heading"),
                    "object_id": paragraphs[0]["object_id"],
                }
            )
        updated = {**memory, "active_entities": entities}
        return {"updated_memory": updated, "cross_page_relationships": relations}
