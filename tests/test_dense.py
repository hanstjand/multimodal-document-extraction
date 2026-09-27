import hashlib
import re
from pathlib import Path

import numpy as np
import pytest

from multimodal_document_extraction.data_models import Page, Question
from multimodal_document_extraction.retrieval.dense import (
    E5_LARGE_V2,
    MODELS,
    DenseConfig,
    DenseModelSpec,
    DensePageRetriever,
    chunk_text,
)

SPEC = DenseModelSpec("fake", "fake/model", "rev", "query: ", "passage: ", max_seq_length=12)


class FakeEncoder:
    """Whitespace tokens; bag-of-words hashed into 256 dims, L2-normalized."""

    num_special_tokens = 2

    def token_offsets(self, text):
        return [m.span() for m in re.finditer(r"\S+", text)]

    def num_tokens(self, text):
        return len(self.token_offsets(text))

    def encode(self, texts):
        out = np.zeros((len(texts), 256), dtype=np.float32)
        for row, text in enumerate(texts):
            for word in re.findall(r"\S+", text.lower()):
                if word in {"query:", "passage:"}:
                    continue
                out[row, int(hashlib.md5(word.encode()).hexdigest(), 16) % 256] += 1.0
            norm = np.linalg.norm(out[row])
            if norm:
                out[row] /= norm
        return out


def _pages(*texts, doc_id="d1"):
    return [Page(doc_id=doc_id, page_number=i, text=t) for i, t in enumerate(texts, start=1)]


def _question(text, doc_id="d1"):
    return Question(question_id="q1", doc_id=doc_id, question=text, evidence_pages=[1])


def test_model_specs_are_pinned():
    assert set(MODELS) == {"e5-large-v2", "bge-large-en"}
    assert all(len(s.revision) == 40 for s in MODELS.values())
    assert E5_LARGE_V2.query_prefix == "query: " and E5_LARGE_V2.passage_prefix == "passage: "


def test_chunk_text_windows_fit_and_overlap():
    enc = FakeEncoder()
    text = " ".join(f"w{i}" for i in range(20))
    # budget = 12 - 2 special - 1 prefix token = 9 tokens, stride 9 - 3 = 6
    chunks = chunk_text(text, enc, "passage: ", max_seq_length=12, overlap=3)
    bodies = [c.removeprefix("passage: ").split() for c in chunks]
    assert all(c.startswith("passage: ") for c in chunks)
    assert all(len(b) <= 9 for b in bodies)
    assert bodies[0][:1] == ["w0"] and bodies[-1][-1] == "w19"
    assert bodies[0][-3:] == bodies[1][:3]  # overlap
    assert {w for b in bodies for w in b} == {f"w{i}" for i in range(20)}  # full coverage


def test_chunk_text_short_empty_and_invalid():
    enc = FakeEncoder()
    assert chunk_text("a b c", enc, "passage: ", 12, 3) == ["passage: a b c"]
    assert chunk_text("   ", enc, "passage: ", 12, 3) == []
    with pytest.raises(ValueError):
        chunk_text("a b", enc, "passage: ", 12, overlap=9)


def test_ranks_pages_by_similarity():
    retriever = DensePageRetriever(SPEC, FakeEncoder(), DenseConfig(chunk_overlap_tokens=2))
    retriever.index_document(
        "d1", _pages("solar panel output", "wind turbine blades", "annual revenue")
    )
    result = retriever.retrieve(_question("wind turbine"))
    assert result.method == "dense-fake-pagetext"
    assert result.pages_in_rank_order()[0] == 2
    scores = [i.score for i in result.items]
    assert scores == sorted(scores, reverse=True)


def test_maxp_finds_evidence_beyond_first_window():
    filler = " ".join(f"filler{i}" for i in range(30))
    retriever = DensePageRetriever(SPEC, FakeEncoder(), DenseConfig(chunk_overlap_tokens=2))
    retriever.index_document("d1", _pages(filler + " zebra habitat", "zebra"))
    result = retriever.retrieve(_question("zebra habitat"))
    assert result.pages_in_rank_order()[0] == 1  # the last window of page 1 matches both words
    assert result.metadata["num_chunks"] > 2


def test_pages_without_text_are_ranked_last_without_score():
    retriever = DensePageRetriever(SPEC, FakeEncoder(), DenseConfig(chunk_overlap_tokens=2))
    retriever.index_document("d1", _pages("", "alpha", None, "beta"))
    result = retriever.retrieve(_question("gamma"))
    assert result.pages_in_rank_order()[2:] == (1, 3)
    assert [i.score for i in result.items][2:] == [None, None]
    assert result.metadata["num_unscored_pages"] == 2


def test_document_without_any_text():
    retriever = DensePageRetriever(SPEC, FakeEncoder(), DenseConfig(chunk_overlap_tokens=2))
    retriever.index_document("d1", _pages("", " ", None))
    result = retriever.retrieve(_question("anything"))
    assert result.pages_in_rank_order() == (1, 2, 3)
    assert result.metadata["empty_index"] is True


def test_errors():
    retriever = DensePageRetriever(SPEC, FakeEncoder(), DenseConfig(chunk_overlap_tokens=2))
    with pytest.raises(KeyError):
        retriever.retrieve(_question("x"))
    with pytest.raises(ValueError):
        retriever.index_document("d1", [])
    with pytest.raises(ValueError):
        retriever.index_document("d1", _pages("a", doc_id="d2"))


# --- Real model smoke test (only if the pinned model is already in the HF cache) --------------


def _cached(spec):
    try:
        from huggingface_hub import try_to_load_from_cache
    except ImportError:
        return False
    path = try_to_load_from_cache(spec.model_id, "config.json", revision=spec.revision)
    return isinstance(path, str) and Path(path).exists()


@pytest.mark.skipif(not _cached(E5_LARGE_V2), reason="e5-large-v2 not cached")
def test_real_e5_smoke():
    from multimodal_document_extraction.retrieval.dense import SentenceTransformerEncoder

    encoder = SentenceTransformerEncoder(E5_LARGE_V2, device="cpu")
    retriever = DensePageRetriever(E5_LARGE_V2, encoder)
    long_page = (
        "Unrelated boilerplate text. " * 300 + "The company reported revenue of 5 billion dollars."
    )
    retriever.index_document("d1", _pages("Cats are small domesticated animals.", long_page))
    result = retriever.retrieve(_question("What revenue did the company report?"))
    assert result.pages_in_rank_order()[0] == 2
    assert result.metadata["num_chunks"] >= 3
