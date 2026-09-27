"""Loader for MMLongBench-Doc (GitHub samples.json, 1,082 questions; decisions D-010, D-012).

Raw layout (produced by ``scripts/download_mmlongbench_doc.py``)::

    <raw_dir>/MANIFEST.json
    <raw_dir>/github/samples.json
    <raw_dir>/documents/<doc_id>

Policies (D-012):

- Question IDs: ``mmlb-<index:04d>-<sha1(doc_id + "\\n" + question)[:8]>``, index = position in
  ``samples.json``.
- Evidence pages are 1-based physical pages already (verified in CP-2.1); no conversion.
- Evidence pages outside ``1..num_pages`` are dropped and the question is flagged
  ``invalid_evidence_pages``. Questions on a known wrong PDF are flagged ``wrong_document``.
  All questions are loaded; flagged questions are excluded from :meth:`MMLongBenchDoc.clean_questions`.
"""

import ast
import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pymupdf

from multimodal_document_extraction.data_models import Document, Page, Question

DATASET_NAME = "MMLongBench-Doc"
DEFAULT_RAW_DIR = Path("data/raw/mmlongbench-doc")

FLAG_INVALID_EVIDENCE_PAGES = "invalid_evidence_pages"
FLAG_WRONG_DOCUMENT = "wrong_document"

KNOWN_WRONG_DOCUMENTS: dict[str, str] = {
    "dr-vorapptchapter1emissionsources-121120210508-phpapp02_95.pdf": (
        "shipped file is byte-identical to "
        "digitalmeasurementframework22feb2011v6novideo-110221233835-phpapp01_95.pdf; "
        "see docs/studies/ladrag/MMLONGBENCH_DOC.md §6.1"
    ),
}


def make_question_id(index: int, doc_id: str, question: str) -> str:
    digest = hashlib.sha1(f"{doc_id}\n{question}".encode()).hexdigest()[:8]
    return f"mmlb-{index:04d}-{digest}"


def _parse_list(raw: str, field: str, index: int) -> list:
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError) as exc:
        raise ValueError(f"sample {index}: cannot parse {field}={raw!r}") from exc
    if not isinstance(value, list):
        raise TypeError(f"sample {index}: {field} is not a list: {raw!r}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class MMLongBenchDoc:
    """Loaded dataset: documents by ID and questions in ``samples.json`` order."""

    documents: dict[str, Document]
    questions: tuple[Question, ...]

    def clean_questions(self) -> tuple[Question, ...]:
        """Questions without any quality flag."""
        return tuple(q for q in self.questions if not q.metadata.get("quality_flags"))

    def flagged_questions(self) -> tuple[Question, ...]:
        return tuple(q for q in self.questions if q.metadata.get("quality_flags"))

    def questions_for(self, doc_id: str) -> tuple[Question, ...]:
        return tuple(q for q in self.questions if q.doc_id == doc_id)

    def question(self, question_id: str) -> Question:
        for q in self.questions:
            if q.question_id == question_id:
                return q
        raise KeyError(question_id)


def load_mmlongbench_doc(
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    *,
    verify_pdfs: bool = False,
    wrong_documents: Iterable[str] | None = None,
) -> MMLongBenchDoc:
    """Load MMLongBench-Doc from ``raw_dir``.

    ``samples.json`` is always verified against ``MANIFEST.json``; PDFs only if ``verify_pdfs``
    (hashing ~670 MB). ``wrong_documents`` overrides :data:`KNOWN_WRONG_DOCUMENTS` (for tests).
    """
    raw_dir = Path(raw_dir)
    manifest = json.loads((raw_dir / "MANIFEST.json").read_text(encoding="utf-8"))
    samples_path = raw_dir / "github" / "samples.json"
    expected = manifest["files"]["github/samples.json"]["sha256"]
    if _sha256(samples_path) != expected:
        raise ValueError(f"{samples_path} does not match MANIFEST.json sha256 {expected}")
    samples: list[dict[str, Any]] = json.loads(samples_path.read_text(encoding="utf-8"))
    wrong = set(KNOWN_WRONG_DOCUMENTS if wrong_documents is None else wrong_documents)

    doc_types: dict[str, str] = {}
    for i, s in enumerate(samples):
        previous = doc_types.setdefault(s["doc_id"], s["doc_type"])
        if previous != s["doc_type"]:
            raise ValueError(
                f"sample {i}: doc {s['doc_id']} has doc_type {s['doc_type']!r} and {previous!r}"
            )

    documents: dict[str, Document] = {}
    for doc_id in sorted(doc_types):
        path = raw_dir / "documents" / doc_id
        if not path.is_file():
            raise FileNotFoundError(f"PDF for {doc_id} not found at {path}")
        if verify_pdfs:
            expected = manifest["files"][f"documents/{doc_id}"]["sha256"]
            if _sha256(path) != expected:
                raise ValueError(f"{path} does not match MANIFEST.json sha256 {expected}")
        with pymupdf.open(path) as pdf:
            num_pages = pdf.page_count
        metadata = (
            {"wrong_document_note": KNOWN_WRONG_DOCUMENTS.get(doc_id)} if doc_id in wrong else {}
        )
        documents[doc_id] = Document(
            doc_id=doc_id,
            num_pages=num_pages,
            dataset=DATASET_NAME,
            doc_type=doc_types[doc_id],
            source_path=str(path),
            metadata=metadata,
        )

    questions = []
    for i, s in enumerate(samples):
        document = documents[s["doc_id"]]
        raw_pages = _parse_list(s["evidence_pages"], "evidence_pages", i)
        sources = _parse_list(s["evidence_sources"], "evidence_sources", i)
        if not all(isinstance(p, int) and not isinstance(p, bool) for p in raw_pages):
            raise ValueError(f"sample {i}: non-integer evidence page in {raw_pages!r}")
        valid_pages = [p for p in raw_pages if document.has_page(p)]
        flags = []
        if len(valid_pages) != len(raw_pages):
            flags.append(FLAG_INVALID_EVIDENCE_PAGES)
        if s["doc_id"] in wrong:
            flags.append(FLAG_WRONG_DOCUMENT)
        question = Question(
            question_id=make_question_id(i, s["doc_id"], s["question"]),
            doc_id=s["doc_id"],
            question=s["question"],
            evidence_pages=valid_pages,
            answer=s["answer"],
            answer_format=s["answer_format"],
            evidence_sources=tuple(sources),
            metadata={
                "index": i,
                "doc_type": s["doc_type"],
                "raw_evidence_pages": raw_pages,
                "quality_flags": flags,
            },
        )
        question.validate_against(document)
        questions.append(question)

    return MMLongBenchDoc(documents=documents, questions=tuple(questions))


def load_pages(document: Document, *, with_text: bool = True) -> list[Page]:
    """Pages of ``document`` (1-based), optionally with PyMuPDF text (empty for image-only pages)."""
    if document.source_path is None:
        raise ValueError(f"document {document.doc_id} has no source_path")
    pages = []
    with pymupdf.open(document.source_path) as pdf:
        if pdf.page_count != document.num_pages:
            raise ValueError(
                f"{document.doc_id}: PDF has {pdf.page_count} pages, expected {document.num_pages}"
            )
        for index, page in enumerate(pdf):
            text = page.get_text() if with_text else None
            pages.append(Page(doc_id=document.doc_id, page_number=index + 1, text=text))
    return pages
