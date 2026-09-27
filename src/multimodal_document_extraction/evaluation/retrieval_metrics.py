"""Page-level retrieval metrics (LAD-RAG, Sourati et al., ACL 2026, §3.3).

Notation: P = gold evidence pages of a question, P-hat = pages covered by the retrieved items.

Questions are split into two subsets (decisions D-008, D-009):

- **evidence subset** (P non-empty) — paper-compatible LAD-RAG metrics: Perfect Recall and IPR.
- **no-evidence subset** (P empty) — Perfect Recall is *not* used (the empty set is trivially a
  subset of any retrieval); instead IPR and NoEvidenceCorrect (1 iff nothing was retrieved).

Edge cases: P non-empty and P-hat empty → PR = 0, IPR = 0.0. P empty and P-hat empty → IPR = 0.0,
NoEvidenceCorrect = 1. P empty and P-hat non-empty → IPR = 1.0, NoEvidenceCorrect = 0.
"""

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from multimodal_document_extraction.data_models import Question, RetrievalResult


def _as_page_set(pages: Iterable[int], name: str) -> frozenset[int]:
    if isinstance(pages, (str, bytes)) or not isinstance(pages, Iterable):
        raise TypeError(f"{name} must be an iterable of page numbers, got {pages!r}")
    page_set = frozenset(pages)
    for p in page_set:
        if isinstance(p, bool) or not isinstance(p, int) or p < 1:
            raise ValueError(f"{name} must contain ints >= 1 (1-based), got {p!r}")
    return page_set


def _check_pair(question: Question, result: RetrievalResult) -> None:
    if result.question_id != question.question_id:
        raise ValueError(f"result is for question {result.question_id}, not {question.question_id}")
    if result.doc_id != question.doc_id:
        raise ValueError(f"result is for document {result.doc_id}, not {question.doc_id}")


def perfect_recall(gold_pages: Iterable[int], retrieved_pages: Iterable[int]) -> float | None:
    """PR = 1 if P ⊆ P-hat else 0; ``None`` if P is empty (D-008)."""
    gold = _as_page_set(gold_pages, "gold_pages")
    retrieved = _as_page_set(retrieved_pages, "retrieved_pages")
    if not gold:
        return None
    return 1.0 if gold <= retrieved else 0.0


def perfect_recall_for(question: Question, result: RetrievalResult) -> float | None:
    """Perfect Recall of one retrieval result against its question's gold evidence pages."""
    _check_pair(question, result)
    return perfect_recall(question.evidence_pages, result.retrieved_pages)


@dataclass(frozen=True)
class MetricSummary:
    """Mean of a per-question metric, with the number of scored and excluded questions."""

    metric: str
    mean: float | None
    num_scored: int
    num_excluded: int

    @property
    def num_questions(self) -> int:
        return self.num_scored + self.num_excluded

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "mean": self.mean,
            "num_scored": self.num_scored,
            "num_excluded": self.num_excluded,
        }


def summarize(
    metric: str,
    per_question: Callable[[Question, RetrievalResult], float | None],
    pairs: Iterable[tuple[Question, RetrievalResult]],
) -> MetricSummary:
    """Average ``per_question`` over (question, result) pairs, skipping undefined (None) scores.

    Each question may appear only once. ``mean`` is ``None`` when no question could be scored.
    """
    seen: set[str] = set()
    scores: list[float] = []
    excluded = 0
    for question, result in pairs:
        if question.question_id in seen:
            raise ValueError(f"question {question.question_id} appears more than once")
        seen.add(question.question_id)
        score = per_question(question, result)
        if score is None:
            excluded += 1
        else:
            scores.append(score)
    mean = sum(scores) / len(scores) if scores else None
    return MetricSummary(metric=metric, mean=mean, num_scored=len(scores), num_excluded=excluded)


def mean_perfect_recall(pairs: Iterable[tuple[Question, RetrievalResult]]) -> MetricSummary:
    """Mean Perfect Recall over questions; questions without gold pages are excluded (D-008)."""
    return summarize("perfect_recall", perfect_recall_for, pairs)


def irrelevant_pages_ratio(gold_pages: Iterable[int], retrieved_pages: Iterable[int]) -> float:
    """IPR = |P-hat \\ P| / |P-hat|; defined as 0.0 when nothing was retrieved (D-009)."""
    gold = _as_page_set(gold_pages, "gold_pages")
    retrieved = _as_page_set(retrieved_pages, "retrieved_pages")
    if not retrieved:
        return 0.0
    return len(retrieved - gold) / len(retrieved)


def irrelevant_pages_ratio_for(question: Question, result: RetrievalResult) -> float:
    """IPR of one retrieval result against its question's gold evidence pages."""
    _check_pair(question, result)
    return irrelevant_pages_ratio(question.evidence_pages, result.retrieved_pages)


def no_evidence_correct(gold_pages: Iterable[int], retrieved_pages: Iterable[int]) -> float | None:
    """1.0 if a no-evidence question retrieved nothing, 0.0 otherwise; ``None`` if P is non-empty."""
    gold = _as_page_set(gold_pages, "gold_pages")
    retrieved = _as_page_set(retrieved_pages, "retrieved_pages")
    if gold:
        return None
    return 0.0 if retrieved else 1.0


def no_evidence_correct_for(question: Question, result: RetrievalResult) -> float | None:
    """NoEvidenceCorrect of one retrieval result (only defined for questions without gold pages)."""
    _check_pair(question, result)
    return no_evidence_correct(question.evidence_pages, result.retrieved_pages)


def _ipr_evidence_subset(question: Question, result: RetrievalResult) -> float | None:
    return irrelevant_pages_ratio_for(question, result) if question.has_evidence else None


def _ipr_no_evidence_subset(question: Question, result: RetrievalResult) -> float | None:
    return None if question.has_evidence else irrelevant_pages_ratio_for(question, result)


def mean_irrelevant_pages_ratio(
    pairs: Iterable[tuple[Question, RetrievalResult]],
) -> MetricSummary:
    """Mean IPR over the paper-compatible evidence subset; no-evidence questions are excluded."""
    return summarize("irrelevant_pages_ratio", _ipr_evidence_subset, pairs)


@dataclass(frozen=True)
class RetrievalEvaluation:
    """Retrieval metrics reported separately for the evidence and no-evidence subsets (D-009).

    ``perfect_recall`` and ``irrelevant_pages_ratio`` are the paper-compatible LAD-RAG metrics
    (evidence subset only). The no-evidence metrics are our addition and are never mixed in.
    """

    perfect_recall: MetricSummary
    irrelevant_pages_ratio: MetricSummary
    no_evidence_irrelevant_pages_ratio: MetricSummary
    no_evidence_correct: MetricSummary

    @property
    def num_questions(self) -> int:
        return self.perfect_recall.num_questions

    @property
    def num_evidence_questions(self) -> int:
        return self.perfect_recall.num_scored

    @property
    def num_no_evidence_questions(self) -> int:
        return self.no_evidence_correct.num_scored

    def to_dict(self) -> dict[str, Any]:
        return {
            "num_questions": self.num_questions,
            "evidence_subset": {
                "num_questions": self.num_evidence_questions,
                "perfect_recall": self.perfect_recall.mean,
                "irrelevant_pages_ratio": self.irrelevant_pages_ratio.mean,
            },
            "no_evidence_subset": {
                "num_questions": self.num_no_evidence_questions,
                "irrelevant_pages_ratio": self.no_evidence_irrelevant_pages_ratio.mean,
                "no_evidence_correct": self.no_evidence_correct.mean,
            },
        }


def evaluate_retrieval(pairs: Iterable[tuple[Question, RetrievalResult]]) -> RetrievalEvaluation:
    """Compute all retrieval metrics, split into evidence / no-evidence subsets."""
    pairs = list(pairs)
    return RetrievalEvaluation(
        perfect_recall=mean_perfect_recall(pairs),
        irrelevant_pages_ratio=mean_irrelevant_pages_ratio(pairs),
        no_evidence_irrelevant_pages_ratio=summarize(
            "no_evidence_irrelevant_pages_ratio", _ipr_no_evidence_subset, pairs
        ),
        no_evidence_correct=summarize("no_evidence_correct", no_evidence_correct_for, pairs),
    )


def evaluate_retrieval_at_k(
    pairs: Iterable[tuple[Question, RetrievalResult]], ks: Iterable[int]
) -> dict[int, RetrievalEvaluation]:
    """Evaluate each ranked result truncated to its first k items (``RetrievalResult.top_k``).

    For a result with fewer than k items, all items are kept (its document is exhausted).
    """
    pairs = list(pairs)
    return {k: evaluate_retrieval((q, r.top_k(k)) for q, r in pairs) for k in sorted(set(ks))}


def first_perfect_recall_k(question: Question, result: RetrievalResult) -> int | None:
    """Smallest k such that the top-k items cover all gold pages.

    ``None`` if the question has no gold pages or the full ranking never covers them.
    """
    _check_pair(question, result)
    if not question.has_evidence:
        return None
    remaining = set(question.evidence_pages)
    for k, item in enumerate(result.items, start=1):
        remaining.discard(item.page_number)
        if not remaining:
            return k
    return None
