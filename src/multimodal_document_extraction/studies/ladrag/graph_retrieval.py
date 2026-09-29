"""Symbolic graph retrieval utilities for LAD-RAG† (CP-4.4; IMPLEMENTATION_SPEC §5, D-018, D-021).

Deterministic, read-only helpers over a persisted :class:`DocumentGraph` (CPU only, no model):

- node → physical page mapping (1-based, D-007), validated against the node ID (R1);
- one-hop neighbours with an edge **scope** (all / cross-page / intra-page) and optional relation
  type and origin filters; an edge is *cross-page* iff its two endpoints lie on different physical
  pages — never inferred from the relation type or origin;
- the ordered one-hop expansion used by retrieval-eval-v1 (D-021, [RECONSTRUCTED]);
- ``get_community_for_node`` over the persisted Louvain communities (R8; not recomputed).

The graph is undirected (R7): a neighbour is reachable from either endpoint of an edge.
"Node ID order" is the canonical order of ``page_N-obj_KKK`` IDs: page number, then object index
(numeric, so ``page_2`` precedes ``page_10``).
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from multimodal_document_extraction.studies.ladrag.schema import (
    DocumentGraph,
    _node_sort_key,
    parse_node_id,
)

SCOPE_ALL = "all"
SCOPE_CROSS_PAGE = "cross_page"
SCOPE_INTRA_PAGE = "intra_page"
SCOPES = (SCOPE_ALL, SCOPE_CROSS_PAGE, SCOPE_INTRA_PAGE)


class UnknownNodeError(KeyError):
    """A node ID that is not in the graph."""


class GraphConsistencyError(ValueError):
    """Graph data contradicts itself (e.g. the ``page`` attribute does not match the node ID)."""


def node_order_key(node_id: str) -> tuple[int, int, str]:
    """Canonical node ID order: (page, object index, ID)."""
    return _node_sort_key(node_id)


@dataclass(frozen=True)
class Neighbor:
    """One neighbour of a node across one (merged, undirected) edge; edge metadata preserved."""

    node_id: str
    page: int
    types: tuple[str, ...]  # relation types merged on the edge (R7)
    sources: tuple[str, ...]  # origins of the edge: "intra_page" (R4) and/or "fig11"
    cross_page: bool


@dataclass(frozen=True)
class ExpansionItem:
    """One entry of an ordered one-hop expansion (see :func:`ordered_one_hop_expansion`)."""

    node_id: str
    page: int
    role: str  # "seed" or "neighbor"
    seed_id: str  # the seed through which this entry was first reached (itself for seeds)
    seed_rank: int  # 1-based rank of that seed in the given seed order
    types: tuple[str, ...] = ()  # edge metadata for neighbours (empty for seeds)
    sources: tuple[str, ...] = ()
    cross_page: bool = False


class GraphIndex:
    """Read-only query helpers over one :class:`DocumentGraph`."""

    def __init__(self, graph: DocumentGraph) -> None:
        self.document_graph = graph
        self.graph = graph.graph
        self._pages: dict[str, int] = {}
        for node_id, data in self.graph.nodes(data=True):
            parsed = parse_node_id(node_id)
            if parsed is None:
                raise GraphConsistencyError(f"malformed node ID {node_id!r}")
            page = data.get("page")
            if page != parsed[0]:
                raise GraphConsistencyError(
                    f"{node_id}: page attribute {page!r} does not match the ID"
                )
            self._pages[node_id] = page

    @property
    def doc_id(self) -> str:
        return self.document_graph.doc_id

    # --- nodes and pages ---------------------------------------------------------------------

    def has_node(self, node_id: Any) -> bool:
        return isinstance(node_id, str) and node_id in self._pages

    def _require(self, node_id: Any) -> str:
        if not self.has_node(node_id):
            raise UnknownNodeError(f"unknown node {node_id!r} in {self.doc_id}")
        return node_id

    def node(self, node_id: str) -> dict[str, Any]:
        """A copy of the node's attributes."""
        return dict(self.graph.nodes[self._require(node_id)])

    def node_page(self, node_id: str) -> int:
        """1-based physical page of a node (from the ``page`` attribute, validated against the ID)."""
        return self._pages[self._require(node_id)]

    def pages_of(self, node_ids: Iterable[str]) -> tuple[int, ...]:
        """Distinct pages of ``node_ids`` in order of first appearance."""
        return tuple(dict.fromkeys(self.node_page(n) for n in node_ids))

    def nodes_in_order(self) -> list[str]:
        return sorted(self._pages, key=node_order_key)

    # --- edges -------------------------------------------------------------------------------

    def is_cross_page(self, a: str, b: str) -> bool:
        """True iff the two endpoints lie on different physical pages."""
        return self.node_page(a) != self.node_page(b)

    def neighbors(
        self,
        node_id: str,
        scope: str = SCOPE_ALL,
        relation_types: Iterable[str] | None = None,
        origins: Iterable[str] | None = None,
    ) -> list[Neighbor]:
        """One-hop neighbours of ``node_id``, ordered by (page, node ID order).

        ``scope`` selects all / cross-page / intra-page edges (endpoint pages decide). An edge passes
        ``relation_types`` / ``origins`` if at least one of its merged types / sources is listed.
        """
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {scope!r}")
        wanted_types = None if relation_types is None else frozenset(relation_types)
        wanted_origins = None if origins is None else frozenset(origins)
        page = self.node_page(node_id)
        result = []
        for other in self.graph.neighbors(node_id):
            data = self.graph.edges[node_id, other]
            other_page = self.node_page(other)
            cross = other_page != page
            if (scope == SCOPE_CROSS_PAGE and not cross) or (scope == SCOPE_INTRA_PAGE and cross):
                continue
            if wanted_types is not None and wanted_types.isdisjoint(data["types"]):
                continue
            if wanted_origins is not None and wanted_origins.isdisjoint(data["sources"]):
                continue
            result.append(
                Neighbor(other, other_page, tuple(data["types"]), tuple(data["sources"]), cross)
            )
        return sorted(result, key=lambda n: node_order_key(n.node_id))

    def edges(self, scope: str = SCOPE_ALL) -> list[tuple[str, str, dict[str, Any]]]:
        """Edges ``(a, b, attributes copy)`` with a before b in node ID order, sorted; filtered by scope."""
        if scope not in SCOPES:
            raise ValueError(f"scope must be one of {SCOPES}, got {scope!r}")
        rows = []
        for a, b, data in self.graph.edges(data=True):
            a, b = sorted((a, b), key=node_order_key)
            cross = self.is_cross_page(a, b)
            if (scope == SCOPE_CROSS_PAGE and not cross) or (scope == SCOPE_INTRA_PAGE and cross):
                continue
            rows.append((a, b, {"types": list(data["types"]), "sources": list(data["sources"])}))
        return sorted(rows, key=lambda r: (node_order_key(r[0]), node_order_key(r[1])))

    # --- retrieval-eval-v1 expansion (D-021) ------------------------------------------------------

    def ordered_one_hop_expansion(
        self,
        seeds: Sequence[str],
        scope: str = SCOPE_ALL,
        relation_types: Iterable[str] | None = None,
        origins: Iterable[str] | None = None,
    ) -> list[ExpansionItem]:
        """Ordered one-hop expansion of seeds given in semantic rank order [RECONSTRUCTED, D-021].

        For each seed in the given order: emit the seed, then its neighbours (scope/filters as in
        :meth:`neighbors`) ordered by (1) physical page, (2) node ID order. Every node is emitted
        once, at its first occurrence (deterministic deduplication); every seed is still expanded
        even if it was already emitted as an earlier seed's neighbour. Uses no gold information.
        Page truncation (budget k) is left to the caller (CP-4.5A).
        """
        items: list[ExpansionItem] = []
        emitted: set[str] = set()
        for rank, seed in enumerate(seeds, start=1):
            seed_page = self.node_page(seed)
            if seed not in emitted:
                emitted.add(seed)
                items.append(ExpansionItem(seed, seed_page, "seed", seed, rank))
            for n in self.neighbors(seed, scope, relation_types, origins):
                if n.node_id in emitted:
                    continue
                emitted.add(n.node_id)
                items.append(
                    ExpansionItem(
                        n.node_id, n.page, "neighbor", seed, rank, n.types, n.sources, n.cross_page
                    )
                )
        return items

    # --- communities (R8) --------------------------------------------------------------------

    def community_of(self, node_id: str) -> int | None:
        return self.graph.nodes[self._require(node_id)].get("community")

    def get_community_for_node(self, node_id: str) -> list[tuple[str, dict[str, Any]]]:
        """All nodes in the Louvain community of ``node_id`` as ``(node_id, attributes copy)``, in
        node ID order. Uses the persisted assignment (no recomputation). A node without a community
        assignment (graph saved without communities) is returned as its own singleton."""
        community = self.community_of(node_id)
        if community is None:
            members = [node_id]
        else:
            members = sorted(
                (n for n, d in self.graph.nodes(data=True) if d.get("community") == community),
                key=node_order_key,
            )
        return [(n, dict(self.graph.nodes[n])) for n in members]


def get_community_for_node(node_id: str, doc_graph: GraphIndex) -> list[tuple[str, dict[str, Any]]]:
    """Paper-named tool (Fig. 6/12): ``get_community_for_node(node_id, doc_graph)`` [PAPER-EXACT name]."""
    return doc_graph.get_community_for_node(node_id)
