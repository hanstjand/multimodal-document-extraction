"""LAD-RAG† document graph schema (CP-4.2; IMPLEMENTATION_SPEC.md §4, decision D-018).

One undirected NetworkX graph per document. Nodes are page objects extracted by a vision model
(prompt Fig. 9) with IDs ``page_{n}-obj_{k:03d}`` (R1, following the paper's Fig. 6); node attributes
are plain dict keys (the agent filters with ``node.get('type')``, Fig. 5). Edges merge relation types
(R7). Pages are 1-based physical page positions (D-007).

Field provenance:
- [PAPER-EXACT] ``EXTRACTED_FIELDS`` — the fields requested by the Fig. 9 prompt. ``object_id`` is also a
  Fig. 9 field, but its value is canonicalized (R1); the model's own ID is kept in ``claimed_object_id``.
- [RECONSTRUCTED] ``RECONSTRUCTED_NODE_FIELDS`` — added by us (document/page bookkeeping, unknown
  extracted keys preserved in ``extra_fields``, Louvain ``community``).
"""

import json
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import networkx as nx

SCHEMA_VERSION = "ladrag-graph/1"

# [PAPER-EXACT] fields requested by the node-extraction prompt (Fig. 9), in prompt order
# (object_id excluded: canonicalized, see module docstring).
EXTRACTED_FIELDS = (
    "type",
    "content",
    "title_or_heading",
    "position_on_page",
    "layout_relation",
    "summary",
    "visual_attributes",
    "page_metadata",
    "content_type",
    "document_context",
)
# [RECONSTRUCTED] node fields added by LAD-RAG†.
SYSTEM_FIELDS = ("object_id", "doc_id", "page", "order_on_page")
RECONSTRUCTED_NODE_FIELDS = (*SYSTEM_FIELDS, "claimed_object_id", "extra_fields", "community")
NODE_FIELDS = frozenset((*EXTRACTED_FIELDS, *RECONSTRUCTED_NODE_FIELDS))
EDGE_FIELDS = frozenset({"source", "target", "types", "sources"})

# [RECONSTRUCTED] default for the configurable `ingestion.section_types` (R3).
DEFAULT_SECTION_TYPES = ("title", "section_header")

# [PAPER-EXACT] working-memory keys named in the graph-construction prompt (Fig. 11).
MEMORY_KEYS = ("section_queue", "active_entities", "semantic_topics", "unresolved_objects")

RELATION_NEXT_ON_PAGE = "next_on_page"  # [RECONSTRUCTED] deterministic intra-page edge (R4)
SOURCE_INTRA_PAGE = "intra_page"
SOURCE_FIG11 = "fig11"

_NODE_ID = re.compile(r"^page_(\d+)-obj_(\d+)$")


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# --- IDs -----------------------------------------------------------------------------------------


def make_node_id(page: int, index: int) -> str:
    if not _is_int(page) or not _is_int(index) or page < 1 or index < 0:
        raise ValueError(f"invalid page/index {page!r}/{index!r}")
    return f"page_{page}-obj_{index:03d}"


def parse_node_id(node_id: Any) -> tuple[int, int] | None:
    """(page, object index) for a well-formed ID with page >= 1, else ``None``."""
    match = _NODE_ID.match(node_id) if isinstance(node_id, str) else None
    if not match or int(match.group(1)) < 1:
        return None
    return int(match.group(1)), int(match.group(2))


def page_prefix(page: int) -> str:
    """The ID prefix passed to the node-extraction prompt (Fig. 9) for a 1-based page."""
    if not _is_int(page) or page < 1:
        raise ValueError(f"invalid page {page!r}")
    return f"page_{page}"


@dataclass(frozen=True)
class IdAssignment:
    """Result of assigning canonical IDs to one page's objects (R1)."""

    ids: tuple[str, ...]  # canonical ID per object, in output order
    mapping: dict[str, str] = field(default_factory=dict)  # claimed ID → canonical ID
    reassigned: int = 0  # objects whose claimed ID was missing, malformed, off-page or duplicated


def assign_ids(claimed: Sequence[Any], page: int) -> IdAssignment:
    """Canonical IDs for a page's objects given the IDs the model claimed.

    A claimed ID is kept (normalized to ``page_{page}-obj_{k:03d}``) if it parses, is on this page and
    its index is unused; otherwise the object gets the next free index after the largest one in use.
    Deterministic in output order.
    """
    page_prefix(page)  # validates page
    used: set[int] = set()
    kept: list[int | None] = []
    for cid in claimed:
        parsed = parse_node_id(cid)
        if parsed and parsed[0] == page and parsed[1] not in used:
            used.add(parsed[1])
            kept.append(parsed[1])
        else:
            kept.append(None)
    next_index = max(used, default=0) + 1
    ids, mapping, reassigned = [], {}, 0
    for cid, index in zip(claimed, kept, strict=True):
        if index is None:
            index = next_index
            next_index += 1
            reassigned += 1
        canonical = make_node_id(page, index)
        ids.append(canonical)
        if isinstance(cid, str) and cid not in mapping:
            mapping[cid] = canonical
    return IdAssignment(ids=tuple(ids), mapping=mapping, reassigned=reassigned)


# --- extracted objects ---------------------------------------------------------------------------


def _as_text(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def normalize_object(raw: Mapping[str, Any]) -> dict[str, Any]:
    """Normalize one object returned for the Fig. 9 prompt.

    - Fig. 9 fields are kept (missing → ``None``); ``type`` is stripped and lower-cased
      (``None``/empty → ``"unknown"``); ``content``, ``summary`` and ``title_or_heading`` are coerced
      to text (non-text values, e.g. table rows as lists, become their JSON text).
    - The model's ``object_id`` is kept as ``claimed_object_id`` (canonical IDs come from
      :func:`assign_ids`).
    - Any other keys are preserved unchanged in ``extra_fields`` (nothing is silently discarded).
    """
    obj: dict[str, Any] = {name: raw.get(name) for name in EXTRACTED_FIELDS}
    obj["type"] = (_as_text(obj["type"]) or "unknown").strip().lower() or "unknown"
    for name in ("content", "summary", "title_or_heading"):
        obj[name] = _as_text(obj[name])
    obj["claimed_object_id"] = _as_text(raw.get("object_id"))
    known = {*EXTRACTED_FIELDS, "object_id"}
    obj["extra_fields"] = {k: v for k, v in raw.items() if k not in known}
    return obj


# --- working memory ------------------------------------------------------------------------------


def initial_memory() -> dict[str, list]:
    """Empty working memory (R6) with the four keys named in Fig. 11."""
    return {key: [] for key in MEMORY_KEYS}


def validate_memory(memory: Any) -> list[str]:
    """Problems with a working memory (empty list = valid).

    The four Fig. 11 keys must be lists; ``section_queue`` items must be ``{"text", "object_id"}``
    dicts or lists of such dicts (sibling sections, Fig. 10). Additional keys are allowed (the model
    may add some).
    """
    if not isinstance(memory, Mapping):
        return [f"memory is not an object: {type(memory).__name__}"]
    problems = [f"missing key {k!r}" for k in MEMORY_KEYS if k not in memory]
    problems += [
        f"{k!r} is not a list"
        for k in MEMORY_KEYS
        if k in memory and not isinstance(memory[k], list)
    ]

    def _is_section(item: Any) -> bool:
        return isinstance(item, Mapping) and "text" in item and "object_id" in item

    for i, item in enumerate(memory.get("section_queue") or []):
        siblings = item if isinstance(item, list) else [item]
        if not siblings or not all(_is_section(s) for s in siblings):
            problems.append(f"section_queue[{i}] is not a section or list of sections")
    return problems


# --- graph metadata ------------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphMetadata:
    """What is needed to interpret one document graph (detailed run records live elsewhere).

    ``ingestion_model`` is the model identifier if known (e.g. ``"scripted"`` or a local VLM
    ``id@revision``); ``config`` holds the reconstruction settings the graph depends on (e.g.
    community resolution/seed, section types); ``provenance`` holds free-form source information
    (dataset, source file, checksum, creating code).
    """

    doc_id: str
    num_pages: int
    schema_version: str = SCHEMA_VERSION
    created_at: str | None = None
    created_by: str | None = None
    ingestion_model: str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    provenance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.doc_id, str) or not self.doc_id:
            raise ValueError("doc_id must be a non-empty string")
        if not _is_int(self.num_pages) or self.num_pages < 1:
            raise ValueError(f"num_pages must be an int >= 1, got {self.num_pages!r}")
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError(f"unsupported schema_version {self.schema_version!r}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "num_pages": self.num_pages,
            "schema_version": self.schema_version,
            "created_at": self.created_at,
            "created_by": self.created_by,
            "ingestion_model": self.ingestion_model,
            "config": dict(self.config),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "GraphMetadata":
        unknown = set(data) - {f for f in cls.__dataclass_fields__}
        if unknown:
            raise ValueError(f"unknown metadata fields {sorted(unknown)}")
        return cls(**{k: data[k] for k in data})


# --- graph ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class EdgeRejection:
    source: Any
    target: Any
    relation: Any
    reason: str


class DocumentGraph:
    """Undirected document graph with validated nodes, merged typed edges and communities."""

    def __init__(self, metadata: GraphMetadata) -> None:
        self.metadata = metadata
        self.graph = nx.Graph(doc_id=metadata.doc_id)

    @property
    def doc_id(self) -> str:
        return self.metadata.doc_id

    # --- nodes ------------------------------------------------------------------------------

    def add_node(
        self, object_id: str, page: int, order_on_page: int, attrs: Mapping[str, Any]
    ) -> None:
        """Add a node; ``attrs`` is typically the output of :func:`normalize_object`."""
        parsed = parse_node_id(object_id)
        if parsed is None or parsed[0] != page:
            raise ValueError(f"node ID {object_id!r} does not match page {page!r}")
        if page > self.metadata.num_pages:
            raise ValueError(f"page {page} exceeds num_pages {self.metadata.num_pages}")
        if not _is_int(order_on_page) or order_on_page < 0:
            raise ValueError(f"order_on_page must be an int >= 0, got {order_on_page!r}")
        if object_id in self.graph:
            raise ValueError(f"duplicate node {object_id}")
        extra = attrs.get("extra_fields") or {}
        if not isinstance(extra, Mapping):
            raise TypeError("extra_fields must be an object")
        data: dict[str, Any] = {
            "object_id": object_id,
            "doc_id": self.doc_id,
            "page": page,
            "order_on_page": order_on_page,
        }
        data.update({name: attrs.get(name) for name in EXTRACTED_FIELDS})
        data["claimed_object_id"] = attrs.get("claimed_object_id")
        data["extra_fields"] = dict(extra)
        self.graph.add_node(object_id, **data)

    def has_node(self, object_id: Any) -> bool:
        return isinstance(object_id, str) and object_id in self.graph

    def node(self, object_id: str) -> dict[str, Any]:
        return self.graph.nodes[object_id]

    def nodes_on_page(self, page: int) -> list[str]:
        nodes = [n for n, d in self.graph.nodes(data=True) if d["page"] == page]
        return sorted(nodes, key=lambda n: self.graph.nodes[n]["order_on_page"])

    def pages(self) -> list[int]:
        return sorted({d["page"] for _, d in self.graph.nodes(data=True)})

    # --- edges ------------------------------------------------------------------------------

    def add_relation(
        self, source: Any, target: Any, relation: Any, origin: str
    ) -> EdgeRejection | None:
        """Add (or merge into) an undirected edge; return an :class:`EdgeRejection` if invalid (R7)."""
        if not isinstance(relation, str) or not relation.strip():
            return EdgeRejection(source, target, relation, "missing relation type")
        if not self.has_node(source) or not self.has_node(target):
            return EdgeRejection(source, target, relation, "unknown endpoint")
        if source == target:
            return EdgeRejection(source, target, relation, "self-loop")
        relation = relation.strip()
        if self.graph.has_edge(source, target):
            data = self.graph.edges[source, target]
            data["types"] = sorted(set(data["types"]) | {relation})
            data["sources"] = sorted(set(data["sources"]) | {origin})
        else:
            self.graph.add_edge(source, target, types=[relation], sources=[origin])
        return None

    def add_relations(
        self, relations: Iterable[Mapping[str, Any]], origin: str
    ) -> list[EdgeRejection]:
        """Add Fig. 11-style ``{"from_object", "to_object", "type"}`` relations; return rejections."""
        rejected = []
        for rel in relations:
            if not isinstance(rel, Mapping):
                rejected.append(EdgeRejection(None, None, None, "not an object"))
                continue
            outcome = self.add_relation(
                rel.get("from_object"), rel.get("to_object"), rel.get("type"), origin
            )
            if outcome is not None:
                rejected.append(outcome)
        return rejected

    # --- communities (R8) -------------------------------------------------------------------

    def set_communities(self, communities: Iterable[Iterable[str]]) -> None:
        """Store community IDs (0..n-1, ordered by the smallest member ID for determinism)."""
        groups = sorted(
            (sorted(c, key=_node_sort_key) for c in communities),
            key=lambda members: _node_sort_key(members[0]),
        )
        seen: set[str] = set()
        assignment: dict[str, int] = {}
        for index, members in enumerate(groups):
            for node in members:
                if node not in self.graph:
                    raise ValueError(f"community member {node} is not a node")
                if node in seen:
                    raise ValueError(f"node {node} is in more than one community")
                seen.add(node)
                assignment[node] = index
        missing = set(self.graph.nodes) - seen
        if missing:
            raise ValueError(f"{len(missing)} nodes without community, e.g. {min(missing)}")
        for node, index in assignment.items():
            self.graph.nodes[node]["community"] = index

    def community_members(self, object_id: str) -> list[str]:
        """All nodes in the community of ``object_id`` (in ID order)."""
        community = self.graph.nodes[object_id].get("community")
        if community is None:
            raise ValueError("communities have not been computed")
        members = (n for n, d in self.graph.nodes(data=True) if d.get("community") == community)
        return sorted(members, key=_node_sort_key)

    # --- validation -------------------------------------------------------------------------

    def validate(self) -> list[str]:
        """Check all graph invariants; return a list of problems (empty = valid)."""
        problems = []
        if self.graph.is_directed() or self.graph.is_multigraph():
            problems.append("graph must be an undirected simple graph")
        with_community = 0
        for node_id, data in self.graph.nodes(data=True):
            parsed = parse_node_id(node_id)
            if parsed is None:
                problems.append(f"malformed node ID {node_id!r}")
                continue
            if data.get("object_id") != node_id:
                problems.append(f"{node_id}: object_id attribute mismatch")
            if data.get("page") != parsed[0]:
                problems.append(f"{node_id}: page attribute does not match ID")
            if not (1 <= parsed[0] <= self.metadata.num_pages):
                problems.append(f"{node_id}: page outside 1..{self.metadata.num_pages}")
            if data.get("doc_id") != self.doc_id:
                problems.append(f"{node_id}: doc_id mismatch")
            unknown = set(data) - NODE_FIELDS
            if unknown:
                problems.append(f"{node_id}: unknown attributes {sorted(unknown)}")
            if "community" in data:
                with_community += 1
                if not _is_int(data["community"]) or data["community"] < 0:
                    problems.append(f"{node_id}: invalid community {data['community']!r}")
        if 0 < with_community < self.graph.number_of_nodes():
            problems.append("communities assigned to only some nodes")
        for a, b, data in self.graph.edges(data=True):
            types, sources = data.get("types"), data.get("sources")
            if a == b:
                problems.append(f"self-loop on {a}")
            if not types or not all(isinstance(t, str) and t for t in types):
                problems.append(f"edge {a}–{b}: invalid types {types!r}")
            if not sources or not all(isinstance(s, str) and s for s in sources):
                problems.append(f"edge {a}–{b}: invalid sources {sources!r}")
            unknown = set(data) - (EDGE_FIELDS - {"source", "target"})
            if unknown:
                problems.append(f"edge {a}–{b}: unknown attributes {sorted(unknown)}")
        return problems

    # --- serialization ----------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Node-link representation; nodes and edges sorted, edge endpoints ordered."""
        nodes = [dict(self.graph.nodes[n]) for n in sorted(self.graph.nodes, key=_node_sort_key)]
        pairs = sorted(
            (tuple(sorted(e, key=_node_sort_key)) for e in self.graph.edges),
            key=lambda e: (_node_sort_key(e[0]), _node_sort_key(e[1])),
        )
        edges = [{"source": a, "target": b, **self.graph.edges[a, b]} for a, b in pairs]
        return {
            "schema": SCHEMA_VERSION,
            "metadata": self.metadata.to_dict(),
            "nodes": nodes,
            "edges": edges,
        }

    def to_json(self) -> str:
        """Deterministic JSON text (sorted keys, fixed indentation, trailing newline)."""
        return json.dumps(self.to_dict(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"

    def save(self, path: Path | str) -> None:
        problems = self.validate()
        if problems:
            raise ValueError(f"refusing to save an invalid graph: {problems[:5]}")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8", newline="\n")

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "DocumentGraph":
        """Rebuild and validate a graph; raises ``ValueError`` on any schema violation."""
        if data.get("schema") != SCHEMA_VERSION:
            raise ValueError(f"unsupported graph schema {data.get('schema')!r}")
        graph = cls(GraphMetadata.from_dict(data["metadata"]))
        for node in data["nodes"]:
            unknown = set(node) - NODE_FIELDS
            if unknown:
                raise ValueError(
                    f"node {node.get('object_id')!r}: unknown attributes {sorted(unknown)}"
                )
            if node.get("doc_id") != graph.doc_id:
                raise ValueError(f"node {node.get('object_id')!r}: doc_id mismatch")
            graph.add_node(node["object_id"], node["page"], node["order_on_page"], node)
            if "community" in node:
                graph.graph.nodes[node["object_id"]]["community"] = node["community"]
        seen_edges: set[frozenset[str]] = set()
        for edge in data["edges"]:
            unknown = set(edge) - EDGE_FIELDS
            if unknown:
                raise ValueError(f"edge has unknown attributes {sorted(unknown)}")
            a, b = edge["source"], edge["target"]
            if not graph.has_node(a) or not graph.has_node(b):
                raise ValueError(f"edge {a!r}–{b!r} references an unknown node")
            key = frozenset((a, b))
            if key in seen_edges:
                raise ValueError(f"duplicate edge {a}–{b}")
            seen_edges.add(key)
            graph.graph.add_edge(a, b, types=list(edge["types"]), sources=list(edge["sources"]))
        problems = graph.validate()
        if problems:
            raise ValueError(f"invalid graph: {problems[:5]}")
        return graph

    @classmethod
    def from_json(cls, text: str) -> "DocumentGraph":
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: Path | str) -> "DocumentGraph":
        return cls.from_json(Path(path).read_text(encoding="utf-8"))

    def stats(self) -> dict[str, Any]:
        types: dict[str, int] = {}
        for _, _, d in self.graph.edges(data=True):
            for t in d["types"]:
                types[t] = types.get(t, 0) + 1
        communities = {d.get("community") for _, d in self.graph.nodes(data=True)} - {None}
        return {
            "nodes": self.graph.number_of_nodes(),
            "edges": self.graph.number_of_edges(),
            "pages_with_nodes": len(self.pages()),
            "edge_types": dict(sorted(types.items())),
            "communities": len(communities),
            "isolated_nodes": nx.number_of_isolates(self.graph),
        }


def _node_sort_key(node_id: str) -> tuple[int, int, str]:
    parsed = parse_node_id(node_id)
    return (*parsed, node_id) if parsed else (10**9, 10**9, node_id)
