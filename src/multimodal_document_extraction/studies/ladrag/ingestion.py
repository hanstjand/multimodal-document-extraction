"""LAD-RAG† ingestion framework (CP-4.3A; IMPLEMENTATION_SPEC §4, decision D-018).

Per page (1-based):
  [A] node extraction   — Fig. 9 prompt + page image  → nodes (R1 IDs, R17 JSON repair)
  [B] section update    — Fig. 10 prompt, only if the page has section-like nodes (R3)
  [C] intra-page edges  — deterministic ``next_on_page`` + ``layout_relation`` strings (R4)
  [D] graph update      — Fig. 11 prompt + page image → memory + cross-page relations (R5, R7)
After the last page: Louvain communities (R8) and the graph file (``graph.json``).

Every model call goes through a permanent cache (R16) and is logged. After each page a page record is
written atomically; a restart rebuilds the state from the records and continues at the first
unfinished page (``pages/page_NNNN.json`` + ``progress.json``). The model is any
:class:`~multimodal_document_extraction.studies.ladrag.models.VisionModel`; nothing here depends on a
specific provider.
"""

import hashlib
import itertools
import json
import os
import re
import time
from collections import Counter
from collections.abc import Callable, Iterator, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import networkx as nx
import pymupdf

import multimodal_document_extraction
from multimodal_document_extraction.studies.ladrag.models import (
    TASK_GRAPH_CONSTRUCTION,
    TASK_NODE_EXTRACTION,
    TASK_RUNNING_MEMORY,
    GenerationParams,
    GenerationRequest,
    ImageInput,
    ModelReply,
    VisionModel,
)
from multimodal_document_extraction.studies.ladrag.prompts import (
    render_graph_construction,
    render_node_extraction,
    render_running_memory,
)
from multimodal_document_extraction.studies.ladrag.schema import (
    DEFAULT_SECTION_TYPES,
    EXTRACTED_FIELDS,
    MEMORY_KEYS,
    RELATION_NEXT_ON_PAGE,
    SOURCE_FIG11,
    SOURCE_INTRA_PAGE,
    DocumentGraph,
    GraphMetadata,
    assign_ids,
    initial_memory,
    normalize_object,
    page_prefix,
    validate_memory,
)
from multimodal_document_extraction.utils.model_cache import ModelCache, cache_key

RECORD_VERSION = (
    3  # 2: R17b container normalization, R21 skip; 3: R17c column-0 parsing + lenient escapes
)
REPAIR_SUFFIX = {
    list: "\n\nYour previous output was not valid JSON. Return only the JSON list.",
    dict: "\n\nYour previous output was not valid JSON. Return only the JSON object.",
}


@dataclass(frozen=True)
class IngestionConfig:
    """Ingestion settings (IMPLEMENTATION_SPEC §6). Paper-exact: render_dpi, temperature,
    max_output_tokens, Louvain; everything else is a reconstruction default."""

    render_dpi: int = 300
    image_max_side_px: int | None = None
    temperature: float = 0.0
    max_output_tokens: int = 8192
    section_types: tuple[str, ...] = DEFAULT_SECTION_TYPES
    json_repair_retries: int = 1
    community_algorithm: str = "louvain"
    community_resolution: float = 1.0
    community_seed: int = 0

    def __post_init__(self) -> None:
        if self.community_algorithm != "louvain":
            raise ValueError(f"unsupported community algorithm {self.community_algorithm!r}")
        if self.render_dpi < 1 or self.json_repair_retries < 0:
            raise ValueError("invalid ingestion config")

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["section_types"] = list(self.section_types)
        return data

    @property
    def params(self) -> GenerationParams:
        return GenerationParams(
            temperature=self.temperature, max_output_tokens=self.max_output_tokens
        )


# --- page rendering --------------------------------------------------------------------------------


def render_page(
    pdf_path: Path | str, page_number: int, dpi: int = 300, max_side_px: int | None = None
) -> ImageInput:
    """Render a 1-based page to PNG at ``dpi``, scaled down so its longer side is ≤ ``max_side_px``."""
    with pymupdf.open(pdf_path) as doc:
        if not 1 <= page_number <= doc.page_count:
            raise ValueError(f"page {page_number} outside 1..{doc.page_count}")
        page = doc[page_number - 1]
        zoom = dpi / 72
        if max_side_px:
            longest = max(page.rect.width, page.rect.height) * zoom
            if longest > max_side_px:
                zoom *= max_side_px / longest
        pixmap = page.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom))
        png = pixmap.tobytes("png")
        return ImageInput(
            png=png,
            sha256=hashlib.sha256(png).hexdigest(),
            width=pixmap.width,
            height=pixmap.height,
        )


# --- JSON replies (R17) ----------------------------------------------------------------------------


class JsonReplyError(ValueError):
    pass


def _looks_like_object(value: Any) -> bool:
    return isinstance(value, dict) and any(k in value for k in (*EXTRACTED_FIELDS, "object_id"))


def normalize_objects_container(value: Any) -> tuple[list, str]:
    """Normalize the container of a node-extraction reply (R17b, [RECONSTRUCTED]).

    Fig. 9 asks for a JSON list; small models sometimes return the same objects in another container.
    Returns ``(objects, shape)`` with shape ``list`` (as requested), ``single_object`` (one object →
    ``[object]``), ``id_map`` (``{object_id: object}`` → values, ID taken from the key if missing) or
    ``wrapped_list`` (a dict with exactly one key holding a list). Anything else raises
    :class:`JsonReplyError`.
    """
    if isinstance(value, list):
        return value, "list"
    if not isinstance(value, dict):
        raise JsonReplyError(f"unsupported container {type(value).__name__}")
    if _looks_like_object(value):
        return [value], "single_object"
    if value and all(_looks_like_object(v) for v in value.values()):
        return [
            {"object_id": k, **v} if "object_id" not in v else v for k, v in value.items()
        ], "id_map"
    if len(value) == 1 and isinstance(next(iter(value.values())), list):
        return next(iter(value.values())), "wrapped_list"
    raise JsonReplyError("dict is neither an object, an id map nor a wrapped list")


_TOP_LEVEL_OPENER = re.compile(r"(?m)^[\[{]")
_HEX4 = re.compile(r"[0-9a-fA-F]{4}")


def lenient_escapes(text: str) -> str:
    """Escape backslashes that do not start a valid JSON escape (R17c, [RECONSTRUCTED]).

    Small models often write LaTeX (``$\\mathcal{L}$``, ``\\(x\\)``) inside JSON strings without
    escaping. Kept as escapes: ``\\" \\\\ \\/ \\n \\r \\t \\uXXXX``; ``\\b`` and ``\\f`` are treated as
    literal backslashes (``\\beta``, ``\\frac``), everything else is doubled.
    """
    out, i = [], 0
    while i < len(text):
        char = text[i]
        if char != "\\":
            out.append(char)
            i += 1
            continue
        following = text[i + 1 : i + 2]
        if following and following in '"\\/nrt':
            out.append(text[i : i + 2])
            i += 2
        elif following == "u" and _HEX4.fullmatch(text[i + 2 : i + 6]):
            out.append(text[i : i + 6])
            i += 6
        else:
            out.append("\\\\")
            i += 1
    return "".join(out)


def _top_level_values(text: str, notes: list[str] | None) -> Iterator[Any]:
    """JSON values starting at column 0 (fence/prose tolerant, never inside a broken value).

    Only openers at the start of a line are candidates, so objects nested inside a truncated or
    otherwise broken structure (which are indented) are never salvaged as if they were the answer.
    If strict decoding fails, one lenient-escape attempt is made (recorded in ``notes``).
    """
    decoder = json.JSONDecoder()
    for match in _TOP_LEVEL_OPENER.finditer(text):
        start = match.start()
        try:
            yield decoder.raw_decode(text, start)[0]
            continue
        except json.JSONDecodeError:
            pass
        try:
            value = decoder.raw_decode(lenient_escapes(text[start:]))[0]
        except json.JSONDecodeError:
            continue
        if notes is not None:
            notes.append("lenient_escapes")
        yield value


def parse_objects_reply(text: str, notes: list[str] | None = None) -> tuple[list, str]:
    """First top-level JSON value that normalizes to a list of objects (R17 + R17b + R17c)."""
    for value in _top_level_values(text, notes):
        try:
            return normalize_objects_container(value)
        except JsonReplyError:
            continue
    raise JsonReplyError("no JSON list of objects found in reply")


def parse_json_reply(text: str, expected: type, notes: list[str] | None = None) -> Any:
    """First top-level JSON value of type ``expected`` (list or dict) in a model reply (R17, R17c).

    Values must start at the beginning of a line (after prose or a Markdown fence); a complete value
    of the wrong type is skipped as a whole.
    """
    for value in _top_level_values(text, notes):
        if isinstance(value, expected):
            return value
    raise JsonReplyError(f"no JSON {expected.__name__} found in reply")


# --- cached, logged model calls --------------------------------------------------------------------


class ModelClient:
    """Calls a :class:`VisionModel` through the permanent cache and returns a call record."""

    def __init__(self, model: VisionModel, cache: ModelCache | None = None) -> None:
        self.model = model
        self.cache = cache

    def call(
        self, task: str, prompt: str, images: Sequence[ImageInput], params: GenerationParams
    ) -> tuple[ModelReply, dict[str, Any]]:
        key = cache_key(
            self.model.model_id, task, prompt, [i.sha256 for i in images], params.to_dict()
        )
        entry = self.cache.get(key) if self.cache else None
        if entry is not None:
            reply = ModelReply(**entry["reply"])
            cached = True
        else:
            start = time.perf_counter()
            reply = self.model.generate(GenerationRequest(task, prompt, tuple(images), params))
            reply = ModelReply(
                reply.text, reply.model_id, dict(reply.usage), time.perf_counter() - start
            )
            cached = False
            if self.cache:
                self.cache.put(
                    key, {"reply": asdict(reply), "task": task, "created_at": _utc_now()}
                )
        record = {
            "task": task,
            "cache_key": key,
            "cached": cached,
            "model_id": reply.model_id,
            "usage": dict(reply.usage),
            "latency_s": reply.latency_s,
        }
        return reply, record


# --- ingestion -----------------------------------------------------------------------------------


@dataclass
class IngestionResult:
    graph: DocumentGraph
    summary: dict[str, Any]
    output_dir: Path


@dataclass
class _PageWork:
    calls: list[dict[str, Any]] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)
    repairs: int = 0


def _utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    os.replace(tmp, path)


def _page_record_path(output_dir: Path, page: int) -> Path:
    return output_dir / "pages" / f"page_{page:04d}.json"


class DocumentIngestor:
    """Runs [A]–[D] page by page with caching, logging and page-level resume."""

    def __init__(
        self,
        model: VisionModel,
        config: IngestionConfig | None = None,
        cache: ModelCache | None = None,
    ) -> None:
        self.model = model
        self.config = config or IngestionConfig()
        self.client = ModelClient(model, cache)

    # --- public API ------------------------------------------------------------------------

    def ingest(
        self,
        doc_id: str,
        pdf_path: Path | str,
        output_dir: Path | str,
        pages: Sequence[int] | None = None,
        restart: bool = False,
        provenance: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """Ingest ``pages`` (default: all, 1-based) of one PDF into ``output_dir``.

        Completed pages found in ``output_dir`` are reused if they were produced with the same
        document, pages, model and config (fingerprint); otherwise a ``ValueError`` is raised unless
        ``restart`` is set, in which case earlier page records are discarded.
        """
        pdf_path, output_dir = Path(pdf_path), Path(output_dir)
        with pymupdf.open(pdf_path) as doc:
            num_pages = doc.page_count
        pages = list(range(1, num_pages + 1)) if pages is None else list(pages)
        if not pages or pages != sorted(set(pages)) or not all(1 <= p <= num_pages for p in pages):
            raise ValueError(f"pages must be increasing, unique and within 1..{num_pages}")
        pdf_sha256 = _sha256_file(pdf_path)
        fingerprint = self._fingerprint(doc_id, pdf_sha256, pages)

        progress_path = output_dir / "progress.json"
        if restart:
            for record in (output_dir / "pages").glob("page_*.json"):
                record.unlink()
            progress_path.unlink(missing_ok=True)
        elif progress_path.exists():
            previous = json.loads(progress_path.read_text(encoding="utf-8"))
            if previous.get("fingerprint") != fingerprint:
                raise ValueError(
                    f"{output_dir} holds records from a different run (fingerprint mismatch); use restart=True"
                )

        metadata = GraphMetadata(
            doc_id=doc_id,
            num_pages=num_pages,
            created_at=_utc_now(),
            created_by=f"multimodal_document_extraction {multimodal_document_extraction.__version__} ladrag.ingestion",
            ingestion_model=self.model.model_id,
            config=self.config.to_dict(),
            provenance={
                "source_path": str(pdf_path),
                "pdf_sha256": pdf_sha256,
                "pages_ingested": pages,
                **(provenance or {}),
            },
        )
        graph = DocumentGraph(metadata)
        memory = initial_memory()
        records: list[dict[str, Any]] = []
        started = time.perf_counter()

        for page in pages:  # reuse the contiguous prefix of completed pages
            path = _page_record_path(output_dir, page)
            if not path.exists():
                break
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("fingerprint") != fingerprint:
                raise ValueError(f"page record {path} does not match this run")
            memory = self._apply_record(graph, record)
            records.append(record)
        resumed_pages = len(records)

        for page in pages[resumed_pages:]:
            page_started = time.perf_counter()
            record, memory = self._process_page(graph, memory, pdf_path, page, fingerprint)
            record["page_seconds"] = time.perf_counter() - page_started
            _write_json_atomic(_page_record_path(output_dir, page), record)
            records.append(record)
            _write_json_atomic(
                progress_path,
                {
                    "doc_id": doc_id,
                    "fingerprint": fingerprint,
                    "pages": pages,
                    "completed_pages": [r["page"] for r in records],
                    "updated_at": _utc_now(),
                },
            )

        if graph.graph.number_of_nodes():
            communities = nx.community.louvain_communities(
                graph.graph,
                weight=None,
                resolution=self.config.community_resolution,
                seed=self.config.community_seed,
            )
        else:
            communities = []
        graph.set_communities(communities)
        graph.save(output_dir / "graph.json")

        summary = self._summary(graph, records, resumed_pages, time.perf_counter() - started)
        _write_json_atomic(output_dir / "summary.json", summary)
        return IngestionResult(graph=graph, summary=summary, output_dir=output_dir)

    # --- internals -------------------------------------------------------------------------

    def _fingerprint(self, doc_id: str, pdf_sha256: str, pages: list[int]) -> str:
        payload = {
            "record_version": RECORD_VERSION,
            "doc_id": doc_id,
            "pdf_sha256": pdf_sha256,
            "pages": pages,
            "model_id": self.model.model_id,
            "config": self.config.to_dict(),
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()

    @staticmethod
    def _apply_record(graph: DocumentGraph, record: dict[str, Any]) -> dict[str, Any]:
        """Replay a completed page record into ``graph``; return the memory after that page."""
        for obj in record["objects"]:
            graph.add_node(obj["object_id"], record["page"], obj["order_on_page"], obj["attrs"])
        for rel in record["relations"]:
            if (
                graph.add_relation(rel["from_object"], rel["to_object"], rel["type"], rel["origin"])
                is not None
            ):
                raise ValueError(f"page {record['page']}: stored relation no longer valid: {rel}")
        return record["memory"]

    def _call_json(
        self,
        work: _PageWork,
        task: str,
        prompt: str,
        images: Sequence[ImageInput],
        expected: type,
        parser: Callable[[str, list[str]], Any] | None = None,
    ) -> Any:
        """Model call + JSON parsing with up to ``json_repair_retries`` repair calls (R17).

        ``parser(text, notes)`` (default: :func:`parse_json_reply` for ``expected``) may raise
        :class:`JsonReplyError` to trigger a repair call; notes (e.g. lenient escapes) become flags.
        """
        parse = parser or (lambda text, notes: parse_json_reply(text, expected, notes))

        def attempt_parse(text: str) -> Any:
            notes: list[str] = []
            value = parse(text, notes)
            work.flags.extend(f"json_{note}:{task}" for note in dict.fromkeys(notes))
            return value

        reply, record = self.client.call(task, prompt, images, self.config.params)
        work.calls.append({**record, "repair": 0})
        try:
            return attempt_parse(reply.text)
        except JsonReplyError:
            pass
        for attempt in range(1, self.config.json_repair_retries + 1):
            reply, record = self.client.call(
                task, prompt + REPAIR_SUFFIX[expected], images, self.config.params
            )
            work.calls.append({**record, "repair": attempt})
            work.repairs += 1
            try:
                return attempt_parse(reply.text)
            except JsonReplyError:
                continue
        work.flags.append(f"json_invalid:{task}")
        return None

    def _process_page(
        self,
        graph: DocumentGraph,
        memory: dict[str, Any],
        pdf_path: Path,
        page: int,
        fingerprint: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        work = _PageWork()
        image = render_page(pdf_path, page, self.config.render_dpi, self.config.image_max_side_px)

        # [A] node extraction (Fig. 9)
        parsed = self._call_json(
            work,
            TASK_NODE_EXTRACTION,
            render_node_extraction(page_prefix(page)),
            [image],
            list,
            parser=parse_objects_reply,
        )
        raw, shape = parsed if parsed is not None else ([], "list")
        if shape != "list":
            work.flags.append(f"container_normalized:{shape}")
        items = [o for o in raw if isinstance(o, dict)]
        if len(items) < len(raw):
            work.flags.append(f"non_object_items_dropped:{len(raw) - len(items)}")
        normalized = [normalize_object(o) for o in items]
        assignment = assign_ids([o["claimed_object_id"] for o in normalized], page)
        objects = []
        for order, (object_id, attrs) in enumerate(zip(assignment.ids, normalized, strict=True)):
            graph.add_node(object_id, page, order, attrs)
            objects.append({"object_id": object_id, "order_on_page": order, "attrs": attrs})

        # [B] section_queue update (Fig. 10), only with section-like candidates (R3)
        candidates = [
            {
                "text": o["attrs"]["title_or_heading"] or o["attrs"]["content"],
                "object_id": o["object_id"],
            }
            for o in objects
            if o["attrs"]["type"] in self.config.section_types
        ]
        if candidates:
            reply = self._call_json(
                work, TASK_RUNNING_MEMORY, render_running_memory(memory, candidates), [], dict
            )
            queue = reply.get("section_queue") if reply is not None else None
            if queue is not None and not validate_memory(
                {**initial_memory(), "section_queue": queue}
            ):
                memory = {**memory, "section_queue": queue}
            else:
                work.flags.append("section_queue_rejected")

        # [C] deterministic intra-page relations (R4)
        relations: list[dict[str, Any]] = []
        intra = [
            {
                "from_object": a["object_id"],
                "to_object": b["object_id"],
                "type": RELATION_NEXT_ON_PAGE,
            }
            for a, b in itertools.pairwise(objects)
        ]
        for rel in intra:
            if (
                graph.add_relation(
                    rel["from_object"], rel["to_object"], rel["type"], SOURCE_INTRA_PAGE
                )
                is None
            ):
                relations.append({**rel, "origin": SOURCE_INTRA_PAGE})
        layout = [
            {"object_id": o["object_id"], "layout_relation": o["attrs"]["layout_relation"]}
            for o in objects
            if o["attrs"]["layout_relation"]
        ]
        relations_text = json.dumps(intra + layout, ensure_ascii=False, indent=2)

        # [D] memory + cross-page relations (Fig. 11)
        objects_text = json.dumps(
            [
                {"object_id": o["object_id"], **{f: o["attrs"][f] for f in EXTRACTED_FIELDS}}
                for o in objects
            ],
            ensure_ascii=False,
            indent=2,
        )
        if objects:
            reply = self._call_json(
                work,
                TASK_GRAPH_CONSTRUCTION,
                render_graph_construction(objects_text, relations_text, memory),
                [image],
                dict,
            )
        else:  # R21: no nodes on this page → nothing to connect; memory unchanged
            reply = None
            work.flags.append("graph_construction_skipped:no_nodes")
        rejections: list[dict[str, Any]] = []
        if reply is not None:
            updated = reply.get("updated_memory")
            if isinstance(updated, dict):
                new_memory = {
                    **updated,
                    "section_queue": memory["section_queue"],
                }  # [B] result is kept
                for key in MEMORY_KEYS:
                    if not isinstance(new_memory.get(key), list):
                        new_memory[key] = memory[key]
                        work.flags.append(f"memory_key_kept:{key}")
                memory = new_memory
            else:
                work.flags.append("updated_memory_missing")
            cross = reply.get("cross_page_relationships")
            if not isinstance(cross, list):
                work.flags.append("cross_page_relationships_missing")
                cross = []
            for rel in cross:
                if not isinstance(rel, dict):
                    rejections.append({"relation": rel, "reason": "not an object"})
                    continue
                outcome = graph.add_relation(
                    rel.get("from_object"), rel.get("to_object"), rel.get("type"), SOURCE_FIG11
                )
                if outcome is None:
                    relations.append(
                        {
                            "from_object": rel["from_object"],
                            "to_object": rel["to_object"],
                            "type": rel["type"].strip(),
                            "origin": SOURCE_FIG11,
                        }
                    )
                else:
                    rejections.append({"relation": rel, "reason": outcome.reason})

        record = {
            "record_version": RECORD_VERSION,
            "fingerprint": fingerprint,
            "page": page,
            "image": {"sha256": image.sha256, "width": image.width, "height": image.height},
            "objects": objects,
            "ids_reassigned": assignment.reassigned,
            "relations": relations,
            "rejected_relations": rejections,
            "memory": memory,
            "memory_chars": len(json.dumps(memory, ensure_ascii=False)),
            "flags": work.flags,
            "repairs": work.repairs,
            "calls": work.calls,
        }
        return record, memory

    def _summary(
        self,
        graph: DocumentGraph,
        records: list[dict[str, Any]],
        resumed_pages: int,
        seconds: float,
    ) -> dict[str, Any]:
        calls = [c for r in records for c in r["calls"]]
        flags = Counter(
            f.split(":", 1)[0] if f.startswith("non_object") else f
            for r in records
            for f in r["flags"]
        )
        return {
            "doc_id": graph.doc_id,
            "model_id": self.model.model_id,
            "pages_processed": len(records),
            "pages_resumed": resumed_pages,
            "pages_with_flags": sum(bool(r["flags"]) for r in records),
            "flags": dict(sorted(flags.items())),
            "json_repairs": sum(r["repairs"] for r in records),
            "ids_reassigned": sum(r["ids_reassigned"] for r in records),
            "rejected_relations": dict(
                sorted(
                    Counter(x["reason"] for r in records for x in r["rejected_relations"]).items()
                )
            ),
            "calls": len(calls),
            "cached_calls": sum(c["cached"] for c in calls),
            "prompt_tokens": sum(c["usage"].get("prompt_tokens", 0) for c in calls),
            "completion_tokens": sum(c["usage"].get("completion_tokens", 0) for c in calls),
            "model_seconds": sum(c["latency_s"] for c in calls if not c["cached"]),
            "max_memory_chars": max((r["memory_chars"] for r in records), default=0),
            "run_seconds": seconds,
            "graph": graph.stats(),
        }
