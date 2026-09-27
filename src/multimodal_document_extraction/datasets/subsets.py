"""Versioned document/question subsets and deterministic stratified document selection.

A :class:`Subset` is stored as JSON (committed, e.g. ``data/splits/<dataset>/<name>.json``) and
lists document IDs and question IDs; the ``metadata`` records how it was produced.
"""

import itertools
import json
import random
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from multimodal_document_extraction.data_models import Question


@dataclass(frozen=True)
class Subset:
    name: str
    dataset: str
    doc_ids: tuple[str, ...]
    question_ids: tuple[str, ...]
    metadata: dict[str, Any] = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "doc_ids", tuple(self.doc_ids))
        object.__setattr__(self, "question_ids", tuple(self.question_ids))
        if len(set(self.doc_ids)) != len(self.doc_ids):
            raise ValueError(f"subset {self.name}: duplicate doc_ids")
        if len(set(self.question_ids)) != len(self.question_ids):
            raise ValueError(f"subset {self.name}: duplicate question_ids")

    def select(self, questions: Iterable[Question]) -> tuple[Question, ...]:
        """The subset's questions, in the order given by ``questions``; all IDs must be found."""
        wanted = set(self.question_ids)
        selected = tuple(q for q in questions if q.question_id in wanted)
        missing = wanted - {q.question_id for q in selected}
        if missing:
            raise KeyError(
                f"subset {self.name}: {len(missing)} question IDs not found, e.g. {min(missing)}"
            )
        outside = {q.doc_id for q in selected} - set(self.doc_ids)
        if outside:
            raise ValueError(
                f"subset {self.name}: questions from documents not in the subset: {outside}"
            )
        return selected

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "dataset": self.dataset,
            "doc_ids": list(self.doc_ids),
            "question_ids": list(self.question_ids),
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Subset":
        return cls(
            name=data["name"],
            dataset=data["dataset"],
            doc_ids=tuple(data["doc_ids"]),
            question_ids=tuple(data["question_ids"]),
            metadata=dict(data.get("metadata") or {}),
        )

    def save(self, path: Path | str) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )

    @classmethod
    def load(cls, path: Path | str) -> "Subset":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


@dataclass(frozen=True)
class DocumentStats:
    """Per-document facts used for subset selection."""

    doc_id: str
    doc_type: str
    num_pages: int
    num_questions: int
    num_multi_page: int
    num_no_evidence: int
    image_only: bool


@dataclass(frozen=True)
class SelectionConstraints:
    num_documents: int = 10
    max_pages_per_document: int = 40
    total_pages: tuple[int, int] = (200, 250)
    total_questions: tuple[int, int] = (70, 90)
    min_multi_page_share: float = 0.25
    min_no_evidence: int = 5
    min_image_only: int = 1
    one_per_doc_type: bool = True

    def check(self, docs: Sequence[DocumentStats]) -> bool:
        pages = sum(d.num_pages for d in docs)
        questions = sum(d.num_questions for d in docs)
        return (
            len(docs) == self.num_documents
            and self.total_pages[0] <= pages <= self.total_pages[1]
            and self.total_questions[0] <= questions <= self.total_questions[1]
            and questions > 0
            and sum(d.num_multi_page for d in docs) / questions >= self.min_multi_page_share
            and sum(d.num_no_evidence for d in docs) >= self.min_no_evidence
            and sum(d.image_only for d in docs) >= self.min_image_only
        )


def select_documents(
    stats: Iterable[DocumentStats],
    constraints: SelectionConstraints,
    seed: int,
    max_attempts: int = 100_000,
) -> tuple[list[DocumentStats], int]:
    """Seeded rejection sampling of documents satisfying ``constraints``.

    Each attempt draws one document per doc type (if ``one_per_doc_type``) and fills the rest at
    random from the remaining eligible documents. Deterministic for a given seed and input set
    (inputs are sorted by ``doc_id`` first). Returns the selection (sorted by doc_id) and the
    1-based attempt number.
    """
    eligible = sorted(
        (d for d in stats if d.num_pages <= constraints.max_pages_per_document),
        key=lambda d: d.doc_id,
    )
    by_type: dict[str, list[DocumentStats]] = {}
    for d in eligible:
        by_type.setdefault(d.doc_type, []).append(d)
    types = sorted(by_type) if constraints.one_per_doc_type else []
    if len(types) > constraints.num_documents:
        raise ValueError(f"{len(types)} doc types but only {constraints.num_documents} documents")

    rng = random.Random(seed)
    for attempt in range(1, max_attempts + 1):
        chosen = [rng.choice(by_type[t]) for t in types]
        rest = [d for d in eligible if d not in chosen]
        chosen += rng.sample(rest, constraints.num_documents - len(chosen))
        if constraints.check(chosen):
            return sorted(chosen, key=lambda d: d.doc_id), attempt
    raise RuntimeError(f"no selection satisfied the constraints in {max_attempts} attempts")


def select_calibration(
    docs: Iterable[DocumentStats],
    seed: int,
    size: int = 2,
    max_total_pages: int = 35,
    require_image_only_and_text: bool = False,
) -> list[DocumentStats]:
    """Pick ``size`` documents (each with >= 1 multi-page question) with few total pages.

    If ``require_image_only_and_text``, the set must contain both an image-only and a text-layer
    document. Among all valid combinations one is chosen with the seeded RNG.
    """
    candidates = sorted((d for d in docs if d.num_multi_page > 0), key=lambda d: d.doc_id)
    valid = [
        combo
        for combo in itertools.combinations(candidates, size)
        if sum(d.num_pages for d in combo) <= max_total_pages
        and (
            not require_image_only_and_text
            or (any(d.image_only for d in combo) and not all(d.image_only for d in combo))
        )
    ]
    if not valid:
        raise RuntimeError("no calibration combination satisfies the constraints")
    return list(random.Random(seed).choice(valid))
