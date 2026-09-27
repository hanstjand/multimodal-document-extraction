"""BM25 page retrieval over PyMuPDF page text (decision D-014).

One BM25 index per document; a question is scored against the pages of its own document and
**all** pages are returned, ranked by score (ties and zero scores by ascending page number), so that
evaluation can sweep any top-k. This is the "page-text" BM25 variant; the LAD-RAG paper's BM25
baseline ranks LVLM element summaries instead and is run after Phase 4 ingestion.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass

import bm25s

from multimodal_document_extraction.data_models import (
    Page,
    Question,
    RetrievalResult,
    RetrievedItem,
)

METHOD_NAME = "bm25-pagetext"


@dataclass(frozen=True)
class BM25Config:
    k1: float = 1.5
    b: float = 0.75
    method: str = "lucene"
    stopwords: str | None = "en"
    lowercase: bool = True

    def as_dict(self) -> dict:
        return {
            "k1": self.k1,
            "b": self.b,
            "method": self.method,
            "stopwords": self.stopwords,
            "lowercase": self.lowercase,
            "stemmer": None,
            "library": f"bm25s {bm25s.__version__}",
        }


@dataclass
class _DocumentIndex:
    page_numbers: list[int]
    retriever: bm25s.BM25 | None  # None when no page has any indexable token
    index_seconds: float


class BM25PageRetriever:
    """Per-document BM25 over page text. Call :meth:`index_document` before :meth:`retrieve`."""

    def __init__(self, config: BM25Config | None = None) -> None:
        self.config = config or BM25Config()
        self._indices: dict[str, _DocumentIndex] = {}

    def _tokenize(self, texts: list[str], return_ids: bool):
        return bm25s.tokenize(
            texts,
            lower=self.config.lowercase,
            stopwords=self.config.stopwords,
            return_ids=return_ids,
            show_progress=False,
        )

    def index_document(self, doc_id: str, pages: Sequence[Page]) -> None:
        if not pages:
            raise ValueError(f"document {doc_id} has no pages")
        if any(p.doc_id != doc_id for p in pages):
            raise ValueError(f"pages of another document passed for {doc_id}")
        numbers = [p.page_number for p in pages]
        if len(set(numbers)) != len(numbers):
            raise ValueError(f"duplicate page numbers for {doc_id}")
        start = time.perf_counter()
        tokens = self._tokenize([p.text or "" for p in pages], return_ids=True)
        retriever = None
        if any(len(ids) for ids in tokens.ids):
            retriever = bm25s.BM25(k1=self.config.k1, b=self.config.b, method=self.config.method)
            retriever.index(tokens, show_progress=False)
        self._indices[doc_id] = _DocumentIndex(numbers, retriever, time.perf_counter() - start)

    def is_indexed(self, doc_id: str) -> bool:
        return doc_id in self._indices

    def retrieve(self, question: Question) -> RetrievalResult:
        """Rank all pages of ``question.doc_id`` by BM25 score against the question text."""
        index = self._indices.get(question.doc_id)
        if index is None:
            raise KeyError(f"document {question.doc_id} is not indexed")
        start = time.perf_counter()
        if index.retriever is None:
            scores = [0.0] * len(index.page_numbers)
        else:
            query_tokens = self._tokenize([question.question], return_ids=False)[0]
            scores = [float(s) for s in index.retriever.get_scores(query_tokens)]
        order = sorted(range(len(scores)), key=lambda i: (-scores[i], index.page_numbers[i]))
        items = tuple(
            RetrievedItem(
                doc_id=question.doc_id,
                page_number=index.page_numbers[i],
                rank=rank,
                score=scores[i],
            )
            for rank, i in enumerate(order, start=1)
        )
        latency = time.perf_counter() - start
        return RetrievalResult(
            question_id=question.question_id,
            doc_id=question.doc_id,
            method=METHOD_NAME,
            items=items,
            latency_s=latency,
            metadata={
                "config": self.config.as_dict(),
                "index_seconds": index.index_seconds,
                "num_positive_scores": sum(s > 0 for s in scores),
                "empty_index": index.retriever is None,
            },
        )
