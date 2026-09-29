"""Neural node retrieval and element-level baselines over LAD-RAG† graphs (CP-4.5; R10, D-016, D-021).

One index per document graph; every node of the graph is indexed (unit = node, never page). Node
text is chosen by ``text_field``:

- ``"r10"`` — ``summary + "\\n" + content`` (R10; the LAD-RAG† neural index used for semantic seeds);
- ``"summary"`` — the element summary only (paper-style element-summary baselines, D-014/D-016).

Missing fields count as ``""``; non-string field values (e.g. table cell lists) are serialized with
``json.dumps(sort_keys=True)`` and counted. A node whose text has no tokens is **unscored**.

Dense scoring (E5-large-v2 / BGE-large-en, pinned in ``retrieval.dense``): the node text is split
into token windows that fit ``window_tokens`` including the passage prefix and special tokens, with
``overlap_tokens`` shared tokens (Phase-3 ``chunk_text``); nothing is truncated — every token is in
at least one window. Embeddings are L2-normalized; a node's score is the maximum cosine over its
windows (MaxP). BM25 (``bm25s``) scores node texts with the Phase-3 BM25 settings.

Ranking (deterministic): scored nodes by score descending, ties by canonical node ID order (page,
object index); unscored nodes after all scored ones, in node ID order. ``semantic_search`` returns
the top ``top_k_nodes`` nodes (all if fewer exist); mapping nodes to a page ranking is left to the
caller (CP-4.5A, frozen retrieval-eval-v1 rules).
"""

import hashlib
import json
import time
from collections.abc import Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from multimodal_document_extraction.retrieval.dense import (
    DenseModelSpec,
    Encoder,
    chunk_text,
)
from multimodal_document_extraction.studies.ladrag.graph_retrieval import GraphIndex

TEXT_FIELDS = ("r10", "summary")


def _as_text(value: Any) -> tuple[str, bool]:
    """(text, converted) — ``None`` → ``""``; non-strings → canonical JSON (converted = True)."""
    if value is None:
        return "", False
    if isinstance(value, str):
        return value, False
    return json.dumps(value, ensure_ascii=False, sort_keys=True), True


def node_text(attrs: dict[str, Any], text_field: str) -> tuple[str, bool]:
    """Text used to index a node, and whether a non-string field value had to be serialized."""
    summary, converted_summary = _as_text(attrs.get("summary"))
    if text_field == "summary":
        return summary, converted_summary
    if text_field == "r10":
        content, converted_content = _as_text(attrs.get("content"))
        return summary + "\n" + content, converted_summary or converted_content
    raise ValueError(f"text_field must be one of {TEXT_FIELDS}, got {text_field!r}")


@dataclass(frozen=True)
class NodeRecord:
    doc_id: str
    node_id: str
    page: int
    node_type: str | None
    text: str
    text_sha256: str
    num_tokens: int
    num_windows: int  # 0 = unscored (no tokens); dense only (BM25: 1 if any token)
    converted_non_string: bool


@dataclass(frozen=True)
class NodeHit:
    rank: int
    node_id: str
    page: int
    node_type: str | None
    score: float | None  # None = unscored node (no indexable text)


@dataclass
class DocumentNodeIndex:
    doc_id: str
    records: list[NodeRecord]
    window_node: np.ndarray = field(default_factory=lambda: np.zeros(0, dtype=np.int64))
    embeddings: np.ndarray = field(default_factory=lambda: np.zeros((0, 0), dtype=np.float32))
    bm25: Any = None
    index_seconds: float = 0.0

    def stats(self) -> dict[str, Any]:
        windows = [r.num_windows for r in self.records]
        tokens = sorted(r.num_tokens for r in self.records)
        return {
            "nodes": len(self.records),
            "unscored_nodes": sum(w == 0 for w in windows),
            "single_window_nodes": sum(w == 1 for w in windows),
            "multi_window_nodes": sum(w > 1 for w in windows),
            "max_windows": max(windows, default=0),
            "total_windows": len(self.window_node),
            "tokens_median": tokens[len(tokens) // 2] if tokens else 0,
            "tokens_p95": tokens[int(0.95 * (len(tokens) - 1))] if tokens else 0,
            "tokens_max": tokens[-1] if tokens else 0,
            "converted_non_string": sum(r.converted_non_string for r in self.records),
            "index_seconds": round(self.index_seconds, 3),
        }


def _records(index: GraphIndex, text_field: str) -> list[tuple[str, dict, str, bool]]:
    rows = []
    for node_id in index.nodes_in_order():
        attrs = index.node(node_id)
        text, converted = node_text(attrs, text_field)
        rows.append((node_id, attrs, text, converted))
    return rows


def _rank(records: list[NodeRecord], scores: list[float | None]) -> list[NodeHit]:
    # records are in canonical node ID order, so the position is the node-ID tie-breaker
    order = sorted(
        range(len(records)),
        key=lambda i: (scores[i] is None, -(scores[i] if scores[i] is not None else 0.0), i),
    )
    return [
        NodeHit(rank, records[i].node_id, records[i].page, records[i].node_type, scores[i])
        for rank, i in enumerate(order, start=1)
    ]


def _check_top_k(top_k_nodes: int | None) -> None:
    if top_k_nodes is not None and (
        isinstance(top_k_nodes, bool) or not isinstance(top_k_nodes, int) or top_k_nodes < 1
    ):
        raise ValueError(f"top_k_nodes must be an int >= 1 or None, got {top_k_nodes!r}")


# --- dense ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class DenseNodeConfig:
    text_field: str = "r10"
    window_tokens: int = 512  # R10; model input length incl. prefix and special tokens
    overlap_tokens: int = 64  # R10

    def __post_init__(self) -> None:
        if self.text_field not in TEXT_FIELDS:
            raise ValueError(f"text_field must be one of {TEXT_FIELDS}")


class DenseNodeRetriever:
    """Dense node retrieval with MaxP over token windows (one index per document graph)."""

    def __init__(
        self, spec: DenseModelSpec, encoder: Encoder, config: DenseNodeConfig | None = None
    ) -> None:
        self.spec = spec
        self.encoder = encoder
        self.config = config or DenseNodeConfig()
        if self.config.window_tokens > spec.max_seq_length:
            raise ValueError(
                f"window_tokens {self.config.window_tokens} exceeds {spec.name} limit"
                f" {spec.max_seq_length}"
            )
        self.indices: dict[str, DocumentNodeIndex] = {}

    @property
    def method_name(self) -> str:
        return f"dense-{self.spec.name}-nodes-{self.config.text_field}"

    def config_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.spec.model_id,
            "revision": self.spec.revision,
            "query_prefix": self.spec.query_prefix,
            "passage_prefix": self.spec.passage_prefix,
            **asdict(self.config),
            "node_score": "max cosine over windows (MaxP)",
            "normalized_embeddings": True,
            "ties": "score desc, then node ID order (page, object index); unscored last",
        }

    def index_graph(self, index: GraphIndex) -> DocumentNodeIndex:
        start = time.perf_counter()
        records, windows, window_node = [], [], []
        for position, (node_id, attrs, text, converted) in enumerate(
            _records(index, self.config.text_field)
        ):
            node_windows = chunk_text(
                text,
                self.encoder,
                self.spec.passage_prefix,
                self.config.window_tokens,
                self.config.overlap_tokens,
            )
            windows += node_windows
            window_node += [position] * len(node_windows)
            records.append(
                NodeRecord(
                    index.doc_id,
                    node_id,
                    index.node_page(node_id),
                    attrs.get("type"),
                    text,
                    hashlib.sha256(text.encode("utf-8")).hexdigest(),
                    self.encoder.num_tokens(text),
                    len(node_windows),
                    converted,
                )
            )
        embeddings = (
            np.asarray(self.encoder.encode(windows), dtype=np.float32)
            if windows
            else np.zeros((0, 0), dtype=np.float32)
        )
        doc_index = DocumentNodeIndex(
            index.doc_id,
            records,
            np.asarray(window_node, dtype=np.int64),
            embeddings,
            index_seconds=time.perf_counter() - start,
        )
        self.indices[index.doc_id] = doc_index
        return doc_index

    def _index(self, doc_id: str) -> DocumentNodeIndex:
        if doc_id not in self.indices:
            raise KeyError(f"document {doc_id} is not indexed")
        return self.indices[doc_id]

    def rank_nodes(self, question: str, doc_id: str) -> list[NodeHit]:
        """All nodes of ``doc_id`` ranked for ``question`` (see module docstring)."""
        index = self._index(doc_id)
        scores: list[float | None] = [None] * len(index.records)
        if len(index.window_node):
            query = np.asarray(
                self.encoder.encode([self.spec.query_prefix + question])[0], dtype=np.float32
            )
            sims = index.embeddings @ query
            for position, sim in zip(index.window_node.tolist(), sims.tolist(), strict=True):
                current = scores[position]
                scores[position] = sim if current is None else max(current, sim)
        return _rank(index.records, scores)

    def semantic_search(
        self, question: str, doc_id: str, top_k_nodes: int | None = 10
    ) -> list[NodeHit]:
        """Top ``top_k_nodes`` nodes (R10 default 10; ``None`` = all); fewer if fewer nodes exist."""
        _check_top_k(top_k_nodes)
        return self.rank_nodes(question, doc_id)[:top_k_nodes]

    # --- persistence (embeddings reused by CP-4.5A for identical seeds) ---------------------------

    def save(self, doc_id: str, directory: Path, provenance: dict[str, Any]) -> Path:
        index = self._index(doc_id)
        directory.mkdir(parents=True, exist_ok=True)
        np.savez(
            directory / f"{doc_id}.npz", embeddings=index.embeddings, window_node=index.window_node
        )
        meta = {
            "doc_id": doc_id,
            "method": self.method_name,
            "config": self.config_dict(),
            "provenance": provenance,
            "stats": index.stats(),
            "records": [asdict(r) for r in index.records],
        }
        path = directory / f"{doc_id}.json"
        path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n"
        )
        return path

    def load(self, doc_id: str, directory: Path, index: GraphIndex) -> DocumentNodeIndex:
        """Load a saved index; refuses if config or the graph's node texts differ."""
        meta = json.loads((directory / f"{doc_id}.json").read_text(encoding="utf-8"))
        if meta["config"] != self.config_dict():
            raise ValueError(f"saved index for {doc_id} was built with a different config")
        current = [
            (node_id, hashlib.sha256(text.encode("utf-8")).hexdigest())
            for node_id, _, text, _ in _records(index, self.config.text_field)
        ]
        saved = [(r["node_id"], r["text_sha256"]) for r in meta["records"]]
        if current != saved:
            raise ValueError(f"saved index for {doc_id} does not match the graph's nodes/texts")
        arrays = np.load(directory / f"{doc_id}.npz")
        doc_index = DocumentNodeIndex(
            doc_id,
            [NodeRecord(**r) for r in meta["records"]],
            arrays["window_node"],
            arrays["embeddings"],
            index_seconds=0.0,
        )
        self.indices[doc_id] = doc_index
        return doc_index


# --- BM25 ----------------------------------------------------------------------------------------


class BM25NodeRetriever:
    """BM25 over node texts (paper-style element baseline with ``text_field="summary"``)."""

    def __init__(self, text_field: str = "summary", bm25_config: Any = None) -> None:
        from multimodal_document_extraction.retrieval.bm25 import BM25Config

        if text_field not in TEXT_FIELDS:
            raise ValueError(f"text_field must be one of {TEXT_FIELDS}")
        self.text_field = text_field
        self.config = bm25_config or BM25Config()
        self.indices: dict[str, DocumentNodeIndex] = {}

    @property
    def method_name(self) -> str:
        return f"bm25-nodes-{self.text_field}"

    def config_dict(self) -> dict[str, Any]:
        return {
            "text_field": self.text_field,
            **self.config.as_dict(),
            "ties": "score desc, then node ID order (page, object index); unscored last",
        }

    def _tokenize(self, texts: list[str], return_ids: bool) -> Any:
        import bm25s

        return bm25s.tokenize(
            texts,
            lower=self.config.lowercase,
            stopwords=self.config.stopwords,
            return_ids=return_ids,
            show_progress=False,
        )

    def index_graph(self, index: GraphIndex) -> DocumentNodeIndex:
        import bm25s

        start = time.perf_counter()
        rows = _records(index, self.text_field)
        tokens = self._tokenize([text for _, _, text, _ in rows], return_ids=True)
        records = [
            NodeRecord(
                index.doc_id,
                node_id,
                index.node_page(node_id),
                attrs.get("type"),
                text,
                hashlib.sha256(text.encode("utf-8")).hexdigest(),
                len(ids),
                int(bool(len(ids))),
                converted,
            )
            for (node_id, attrs, text, converted), ids in zip(rows, tokens.ids, strict=True)
        ]
        retriever = None
        if any(r.num_windows for r in records):
            retriever = bm25s.BM25(k1=self.config.k1, b=self.config.b, method=self.config.method)
            retriever.index(tokens, show_progress=False)
        doc_index = DocumentNodeIndex(
            index.doc_id, records, bm25=retriever, index_seconds=time.perf_counter() - start
        )
        self.indices[index.doc_id] = doc_index
        return doc_index

    def rank_nodes(self, question: str, doc_id: str) -> list[NodeHit]:
        if doc_id not in self.indices:
            raise KeyError(f"document {doc_id} is not indexed")
        index = self.indices[doc_id]
        scores: list[float | None] = [None] * len(index.records)
        if index.bm25 is not None:
            query = self._tokenize([question], return_ids=False)[0]
            raw = index.bm25.get_scores(query)
            scores = [
                float(s) if r.num_windows else None for s, r in zip(raw, index.records, strict=True)
            ]
        return _rank(index.records, scores)

    def semantic_search(
        self, question: str, doc_id: str, top_k_nodes: int | None = 10
    ) -> list[NodeHit]:
        _check_top_k(top_k_nodes)
        return self.rank_nodes(question, doc_id)[:top_k_nodes]


def hits_as_dicts(hits: Sequence[NodeHit]) -> list[dict[str, Any]]:
    return [asdict(h) for h in hits]
