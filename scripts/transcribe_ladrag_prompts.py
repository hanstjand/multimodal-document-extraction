"""Transcribe the four LAD-RAG App. H prompts (Figs. 9-12) from the ACL PDF (CP-4.1).

Usage:
  python scripts/transcribe_ladrag_prompts.py src/multimodal_document_extraction/studies/ladrag/prompts 110

Method: PyMuPDF text of pages 21-24 of papers/ladrag/2026.acl-long.724.pdf. LaTeX listings wraps
long lines and marks each continuation line with ',→'; PyMuPDF emits the markers as separate lines
after the block. A physical line is treated as wrapped if it is long (>= threshold chars) and is
re-joined with the next line by one space. For each marker group, the number of wrapped lines in the
block it closes must equal the number of markers; mismatches are reported.
"""

import sys
from pathlib import Path

import pymupdf

PDF = Path("papers/ladrag/2026.acl-long.724.pdf")
FIGURES = {
    21: (
        "fig09_node_extraction.txt",
        "Prompt used for document graph node extraction",
        "Figure 9:",
    ),
    22: ("fig10_running_memory.txt", "Prompt used for running memory construction", "Figure 10:"),
    23: (
        "fig11_graph_construction.txt",
        "Prompt used for document graph construction",
        "Figure 11:",
    ),
    24: ("fig12_retriever_agent.txt", "Prompt used for retriever agent inference", "Figure 12:"),
}
MARKER = ",→"


def _join_block(block: list[str], wrapped: set[int]) -> list[str]:
    logical, current = [], None
    for i, line in enumerate(block):
        current = line if current is None else current + " " + line
        if i not in wrapped:
            logical.append(current)
            current = None
    if current is not None:
        logical.append(current)
    return logical


def transcribe(body: list[str], threshold: int) -> tuple[list[str], list[str]]:
    """Return (logical lines, mismatch reports) for the physical lines of one prompt figure."""
    logical: list[str] = []
    pending: list[str] = []
    mismatches: list[str] = []
    i = 0
    while i < len(body):
        if body[i] != MARKER:
            pending.append(body[i])
            i += 1
            continue
        markers = 0
        while i < len(body) and body[i] == MARKER:
            markers += 1
            i += 1
        # The markers close the shortest tail of pending lines containing `markers` long lines.
        start = len(pending) - 1
        while start >= 0 and sum(len(x) >= threshold for x in pending[start:-1]) < markers:
            start -= 1
        start = max(start, 0)
        block = pending[start:]
        logical.extend(pending[:start])
        pending = []
        wrapped = {j for j, x in enumerate(block[:-1]) if len(x) >= threshold}
        if len(wrapped) != markers:
            mismatches.append(f"markers={markers} wrapped={len(wrapped)}: {block[0][:60]!r}")
        logical.extend(_join_block(block, wrapped))
    logical.extend(pending)
    return logical, mismatches


def main() -> None:
    out_dir = Path(sys.argv[1])
    threshold = int(sys.argv[2]) if len(sys.argv) > 2 else 110
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    with pymupdf.open(PDF) as doc:
        for page_no, (name, title, caption) in FIGURES.items():
            lines = doc[page_no - 1].get_text().splitlines()
            end = next(i for i, x in enumerate(lines) if x.startswith(caption))
            body = lines[lines.index(title) + 1 : end]
            logical, mismatches = transcribe(body, threshold)
            (out_dir / name).write_text("\n".join(logical) + "\n", encoding="utf-8", newline="\n")
            print(f"{name}: {len(body)} physical lines -> {len(logical)} logical lines")
            for m in mismatches:
                print(f"  MISMATCH {m}")
            total += len(mismatches)
    print("problems:", total)


if __name__ == "__main__":
    main()
