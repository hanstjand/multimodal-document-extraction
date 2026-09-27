"""Dense page retrieval over PyMuPDF page text (decision D-016).

Each page's text is split into overlapping token windows that fit the model's input limit; every
window is embedded and a page is scored by its best window (cosine similarity, "MaxP"). Pages
without text get no score and are ranked after all scored pages, by page number. One index per
document; all pages are returned, ranked (ties by page number).

The paper's E5/BGE baselines embed LVLM element summaries; this "page-text" variant is ours.
"""

import time
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from multimodal_document_extraction.data_models import (
    Page,
    Question,
    RetrievalResult,
    RetrievedItem,
)


@dataclass(frozen=True)
class DenseModelSpec:
    name: str
    model_id: str
    revision: str
    query_prefix: str
    passage_prefix: str
    max_seq_length: int = 512


# Prefixes from the official model cards (checked 2026-09-27); revisions pinned.
E5_LARGE_V2 = DenseModelSpec(
    name="e5-large-v2",
    model_id="intfloat/e5-large-v2",
    revision="f169b11e22de13617baa190a028a32f3493550b6",
    query_prefix="query: ",
    passage_prefix="passage: ",
)
BGE_LARGE_EN = DenseModelSpec(
    name="bge-large-en",
    model_id="BAAI/bge-large-en",
    revision="abe7d9d814b775ca171121fb03f394dc42974275",
    query_prefix="Represent this sentence for searching relevant passages: ",
    passage_prefix="",
)
MODELS = {spec.name: spec for spec in (E5_LARGE_V2, BGE_LARGE_EN)}


class Encoder(Protocol):
    """Minimal encoder interface (real: :class:`SentenceTransformerEncoder`; tests: fakes)."""

    def token_offsets(self, text: str) -> list[tuple[int, int]]: ...

    def num_tokens(self, text: str) -> int: ...

    def encode(self, texts: list[str]) -> np.ndarray: ...  # L2-normalized rows

    @property
    def num_special_tokens(self) -> int: ...


class SentenceTransformerEncoder:
    def __init__(
        self, spec: DenseModelSpec, device: str | None = None, batch_size: int = 16
    ) -> None:
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(spec.model_id, revision=spec.revision, device=device)
        self.model.max_seq_length = spec.max_seq_length
        self.batch_size = batch_size

    def token_offsets(self, text: str) -> list[tuple[int, int]]:
        enc = self.model.tokenizer(text, add_special_tokens=False, return_offsets_mapping=True)
        return [tuple(o) for o in enc["offset_mapping"]]

    def num_tokens(self, text: str) -> int:
        return len(self.model.tokenizer(text, add_special_tokens=False)["input_ids"])

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=self.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )

    @property
    def num_special_tokens(self) -> int:
        return self.model.tokenizer.num_special_tokens_to_add()

    @property
    def device(self) -> str:
        return str(self.model.device)


@dataclass(frozen=True)
class DenseConfig:
    chunk_overlap_tokens: int = 64


def chunk_text(
    text: str, encoder: Encoder, prefix: str, max_seq_length: int, overlap: int
) -> list[str]:
    """Split ``text`` into windows of whole tokens that fit ``max_seq_length`` with ``prefix``.

    Windows are cut at tokenizer offsets of the original text (no detokenization); consecutive
    windows share ``overlap`` tokens. Returns ``[]`` for text without tokens.
    """
    offsets = encoder.token_offsets(text)
    if not offsets:
        return []
    budget = max_seq_length - encoder.num_special_tokens - encoder.num_tokens(prefix)
    if budget <= overlap:
        raise ValueError(f"window budget {budget} must exceed overlap {overlap}")
    stride = budget - overlap
    chunks, start = [], 0
    while True:
        end = min(start + budget, len(offsets))
        chunks.append(prefix + text[offsets[start][0] : offsets[end - 1][1]])
        if end == len(offsets):
            return chunks
        start += stride


@dataclass
class _DocumentIndex:
    page_numbers: list[int]
    chunk_page: np.ndarray  # page position of each chunk embedding
    embeddings: np.ndarray  # (num_chunks, dim), L2-normalized
    num_chunks_per_page: list[int]
    index_seconds: float


class DensePageRetriever:
    """Per-document dense retrieval with MaxP over token windows."""

    def __init__(
        self, spec: DenseModelSpec, encoder: Encoder, config: DenseConfig | None = None
    ) -> None:
        self.spec = spec
        self.encoder = encoder
        self.config = config or DenseConfig()
        self._indices: dict[str, _DocumentIndex] = {}

    @property
    def method_name(self) -> str:
        return f"dense-{self.spec.name}-pagetext"

    def config_dict(self) -> dict:
        return {
            "model_id": self.spec.model_id,
            "revision": self.spec.revision,
            "query_prefix": self.spec.query_prefix,
            "passage_prefix": self.spec.passage_prefix,
            "max_seq_length": self.spec.max_seq_length,
            "chunk_overlap_tokens": self.config.chunk_overlap_tokens,
            "page_score": "max cosine over chunks (MaxP)",
        }

    def index_document(self, doc_id: str, pages: Sequence[Page]) -> None:
        if not pages:
            raise ValueError(f"document {doc_id} has no pages")
        if any(p.doc_id != doc_id for p in pages):
            raise ValueError(f"pages of another document passed for {doc_id}")
        numbers = [p.page_number for p in pages]
        if len(set(numbers)) != len(numbers):
            raise ValueError(f"duplicate page numbers for {doc_id}")
        start = time.perf_counter()
        chunks, chunk_page, per_page = [], [], []
        for position, page in enumerate(pages):
            page_chunks = chunk_text(
                page.text or "",
                self.encoder,
                self.spec.passage_prefix,
                self.spec.max_seq_length,
                self.config.chunk_overlap_tokens,
            )
            chunks += page_chunks
            chunk_page += [position] * len(page_chunks)
            per_page.append(len(page_chunks))
        embeddings = self.encoder.encode(chunks) if chunks else np.zeros((0, 0), dtype=np.float32)
        self._indices[doc_id] = _DocumentIndex(
            page_numbers=numbers,
            chunk_page=np.asarray(chunk_page, dtype=np.int64),
            embeddings=np.asarray(embeddings, dtype=np.float32),
            num_chunks_per_page=per_page,
            index_seconds=time.perf_counter() - start,
        )

    def is_indexed(self, doc_id: str) -> bool:
        return doc_id in self._indices

    def retrieve(self, question: Question) -> RetrievalResult:
        index = self._indices.get(question.doc_id)
        if index is None:
            raise KeyError(f"document {question.doc_id} is not indexed")
        start = time.perf_counter()
        page_scores: list[float | None] = [None] * len(index.page_numbers)
        if len(index.chunk_page):
            query = self.encoder.encode([self.spec.query_prefix + question.question])[0]
            sims = index.embeddings @ np.asarray(query, dtype=np.float32)
            for position, sim in zip(index.chunk_page.tolist(), sims.tolist(), strict=True):
                current = page_scores[position]
                page_scores[position] = sim if current is None else max(current, sim)
        order = sorted(
            range(len(page_scores)),
            key=lambda i: (page_scores[i] is None, -(page_scores[i] or 0.0), index.page_numbers[i]),
        )
        items = tuple(
            RetrievedItem(
                doc_id=question.doc_id,
                page_number=index.page_numbers[i],
                rank=rank,
                score=page_scores[i],
            )
            for rank, i in enumerate(order, start=1)
        )
        return RetrievalResult(
            question_id=question.question_id,
            doc_id=question.doc_id,
            method=self.method_name,
            items=items,
            latency_s=time.perf_counter() - start,
            metadata={
                "config": self.config_dict(),
                "index_seconds": index.index_seconds,
                "num_chunks": len(index.chunk_page),
                "num_unscored_pages": sum(s is None for s in page_scores),
                "empty_index": not len(index.chunk_page),
            },
        )
