"""Core, method-agnostic data models shared by datasets, retrievers, and evaluation.

Conventions (decision D-007):

- Page numbers are **1-based physical page positions** in the PDF (first page = 1), not printed
  page labels. Dataset loaders convert their native indexing to this convention.
- Models are frozen dataclasses; collections are stored as tuples / frozensets.
- ``metadata`` holds dataset- or method-specific extras. It is excluded from equality and
  hashing and must be JSON-serializable for results to be written as JSONL.
"""

import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

RETRIEVAL_UNITS = frozenset({"page", "element", "node"})
"""Granularity of a retrieved item. Element/node items are mapped to their page for page metrics."""


def _check_non_empty(value: str, name: str) -> None:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{name} must be a non-empty string, got {value!r}")


def _check_page_number(value: int, name: str = "page_number") -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ValueError(f"{name} must be an int >= 1 (1-based), got {value!r}")


def _check_optional_float(value: float | None, name: str) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number or None, got {value!r}")


@dataclass(frozen=True)
class Document:
    """A multi-page document (typically a PDF)."""

    doc_id: str
    num_pages: int
    dataset: str | None = None
    doc_type: str | None = None
    source_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        _check_non_empty(self.doc_id, "doc_id")
        _check_page_number(self.num_pages, "num_pages")

    def page_numbers(self) -> range:
        return range(1, self.num_pages + 1)

    def has_page(self, page_number: int) -> bool:
        return 1 <= page_number <= self.num_pages

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "num_pages": self.num_pages,
            "dataset": self.dataset,
            "doc_type": self.doc_type,
            "source_path": self.source_path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Document":
        return cls(
            doc_id=data["doc_id"],
            num_pages=data["num_pages"],
            dataset=data.get("dataset"),
            doc_type=data.get("doc_type"),
            source_path=data.get("source_path"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class Page:
    """One page of a document, with optional extracted text and rendered image."""

    doc_id: str
    page_number: int
    text: str | None = None
    image_path: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        _check_non_empty(self.doc_id, "doc_id")
        _check_page_number(self.page_number)

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "page_number": self.page_number,
            "text": self.text,
            "image_path": self.image_path,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Page":
        return cls(
            doc_id=data["doc_id"],
            page_number=data["page_number"],
            text=data.get("text"),
            image_path=data.get("image_path"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class Question:
    """A question about one document, with its gold evidence pages.

    ``evidence_pages`` may be empty (e.g. unanswerable questions); how metrics treat that case
    is decided by the metric, not here.
    """

    question_id: str
    doc_id: str
    question: str
    evidence_pages: frozenset[int] = frozenset()
    answer: str | None = None
    answer_format: str | None = None
    evidence_sources: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        _check_non_empty(self.question_id, "question_id")
        _check_non_empty(self.doc_id, "doc_id")
        _check_non_empty(self.question, "question")
        if isinstance(self.evidence_pages, (str, bytes)) or not isinstance(
            self.evidence_pages, Iterable
        ):
            raise TypeError(
                f"evidence_pages must be an iterable of ints, got {self.evidence_pages!r}"
            )
        pages = frozenset(self.evidence_pages)
        for p in pages:
            _check_page_number(p, "evidence page")
        object.__setattr__(self, "evidence_pages", pages)
        object.__setattr__(self, "evidence_sources", tuple(self.evidence_sources))

    @property
    def has_evidence(self) -> bool:
        return bool(self.evidence_pages)

    @property
    def is_multi_page(self) -> bool:
        return len(self.evidence_pages) > 1

    def validate_against(self, document: Document) -> None:
        """Raise ValueError if this question does not fit ``document``."""
        if self.doc_id != document.doc_id:
            raise ValueError(
                f"question {self.question_id} is for {self.doc_id}, not {document.doc_id}"
            )
        out_of_range = sorted(p for p in self.evidence_pages if not document.has_page(p))
        if out_of_range:
            raise ValueError(
                f"question {self.question_id}: evidence pages {out_of_range} exceed "
                f"{document.num_pages} pages of {document.doc_id}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "doc_id": self.doc_id,
            "question": self.question,
            "evidence_pages": sorted(self.evidence_pages),
            "answer": self.answer,
            "answer_format": self.answer_format,
            "evidence_sources": list(self.evidence_sources),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Question":
        return cls(
            question_id=data["question_id"],
            doc_id=data["doc_id"],
            question=data["question"],
            evidence_pages=frozenset(data.get("evidence_pages") or ()),
            answer=data.get("answer"),
            answer_format=data.get("answer_format"),
            evidence_sources=tuple(data.get("evidence_sources") or ()),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class RetrievedItem:
    """One retrieved unit (page, element, or graph node), always located on a page."""

    doc_id: str
    page_number: int
    rank: int
    score: float | None = None
    unit_type: str = "page"
    unit_id: str | None = None
    text: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        _check_non_empty(self.doc_id, "doc_id")
        _check_page_number(self.page_number)
        _check_page_number(self.rank, "rank")
        _check_optional_float(self.score, "score")
        if self.unit_type not in RETRIEVAL_UNITS:
            raise ValueError(
                f"unit_type must be one of {sorted(RETRIEVAL_UNITS)}, got {self.unit_type!r}"
            )
        if self.unit_type != "page" and not self.unit_id:
            raise ValueError(f"unit_id is required for unit_type={self.unit_type!r}")

    @property
    def key(self) -> tuple[str, str | int]:
        """Identity of the retrieved unit within a result (used to reject duplicates)."""
        if self.unit_type == "page":
            return ("page", self.page_number)
        return (self.unit_type, self.unit_id)  # type: ignore[return-value]

    def to_dict(self) -> dict[str, Any]:
        return {
            "doc_id": self.doc_id,
            "page_number": self.page_number,
            "rank": self.rank,
            "score": self.score,
            "unit_type": self.unit_type,
            "unit_id": self.unit_id,
            "text": self.text,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetrievedItem":
        return cls(
            doc_id=data["doc_id"],
            page_number=data["page_number"],
            rank=data["rank"],
            score=data.get("score"),
            unit_type=data.get("unit_type", "page"),
            unit_id=data.get("unit_id"),
            text=data.get("text"),
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass(frozen=True)
class RetrievalResult:
    """Ranked output of one retrieval method for one question.

    Invariants: all items belong to ``doc_id``; ranks are exactly 1..n in order; no unit appears
    twice. Methods without a natural ranking (e.g. an agent returning a set) assign ranks in
    output order.
    """

    question_id: str
    doc_id: str
    method: str
    items: tuple[RetrievedItem, ...] = ()
    latency_s: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        _check_non_empty(self.question_id, "question_id")
        _check_non_empty(self.doc_id, "doc_id")
        _check_non_empty(self.method, "method")
        items = tuple(self.items)
        object.__setattr__(self, "items", items)
        _check_optional_float(self.latency_s, "latency_s")
        if self.latency_s is not None and self.latency_s < 0:
            raise ValueError(f"latency_s must be >= 0, got {self.latency_s!r}")
        seen: set[tuple[str, str | int]] = set()
        for expected_rank, item in enumerate(items, start=1):
            if not isinstance(item, RetrievedItem):
                raise TypeError(f"items must be RetrievedItem, got {type(item).__name__}")
            if item.doc_id != self.doc_id:
                raise ValueError(f"item from {item.doc_id} in result for {self.doc_id}")
            if item.rank != expected_rank:
                raise ValueError(
                    f"ranks must be 1..n in order; expected {expected_rank}, got {item.rank}"
                )
            if item.key in seen:
                raise ValueError(f"duplicate retrieved unit {item.key}")
            seen.add(item.key)

    def __len__(self) -> int:
        return len(self.items)

    @property
    def retrieved_pages(self) -> frozenset[int]:
        """Set of pages covered by the retrieved items (P-hat in the LAD-RAG metrics)."""
        return frozenset(item.page_number for item in self.items)

    def pages_in_rank_order(self) -> tuple[int, ...]:
        """Distinct pages in order of their first appearance in the ranking."""
        return tuple(dict.fromkeys(item.page_number for item in self.items))

    def top_k(self, k: int) -> "RetrievalResult":
        """The first ``k`` retrieved items (k >= 0) as a new result."""
        if isinstance(k, bool) or not isinstance(k, int) or k < 0:
            raise ValueError(f"k must be an int >= 0, got {k!r}")
        return RetrievalResult(
            question_id=self.question_id,
            doc_id=self.doc_id,
            method=self.method,
            items=self.items[:k],
            latency_s=self.latency_s,
            metadata={**self.metadata, "top_k": k},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question_id": self.question_id,
            "doc_id": self.doc_id,
            "method": self.method,
            "items": [item.to_dict() for item in self.items],
            "latency_s": self.latency_s,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "RetrievalResult":
        return cls(
            question_id=data["question_id"],
            doc_id=data["doc_id"],
            method=data["method"],
            items=tuple(RetrievedItem.from_dict(i) for i in data.get("items") or ()),
            latency_s=data.get("latency_s"),
            metadata=dict(data.get("metadata") or {}),
        )
