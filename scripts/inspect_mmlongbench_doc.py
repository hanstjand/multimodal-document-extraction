"""Inspect the downloaded MMLongBench-Doc release (CP-2.1) and write a JSON report.

Checks: annotation parsing, statistics, per-document page counts, evidence-page indexing
(bounds + an empirical answer-in-page-text test), "Not answerable" vs empty evidence, duplicate
PDFs, and the difference between GitHub samples.json and the Hugging Face split.

Usage:
  python scripts/inspect_mmlongbench_doc.py [--raw data/raw/mmlongbench-doc]
                                            [--out data/processed/mmlongbench-doc/inspection.json]
"""

import argparse
import ast
import json
import re
import statistics
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

import pymupdf

HF_ROWS_API = "https://datasets-server.huggingface.co/rows"
HF_DATASET = "yubo2333/MMLongBench-Doc"


def _parse_list(raw: str) -> list:
    value = ast.literal_eval(raw)
    if not isinstance(value, list):
        raise TypeError(f"not a list: {raw!r}")
    return value


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _hf_rows() -> list[dict]:
    rows, offset = [], 0
    while True:
        query = urllib.parse.urlencode(
            {
                "dataset": HF_DATASET,
                "config": "default",
                "split": "train",
                "offset": offset,
                "length": 100,
            }
        )
        with urllib.request.urlopen(f"{HF_ROWS_API}?{query}", timeout=120) as r:
            page = json.load(r)
        rows += [x["row"] for x in page["rows"]]
        offset += 100
        if offset >= page["num_rows_total"]:
            return rows


def _key(row: dict) -> tuple:
    fields = ("doc_id", "question", "answer", "evidence_pages", "evidence_sources", "answer_format")
    return tuple(str(row[f]) for f in fields)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--raw", type=Path, default=Path("data/raw/mmlongbench-doc"))
    parser.add_argument(
        "--out", type=Path, default=Path("data/processed/mmlongbench-doc/inspection.json")
    )
    args = parser.parse_args()
    report: dict = {}

    samples = json.loads((args.raw / "github/samples.json").read_text(encoding="utf-8"))
    manifest = json.loads((args.raw / "MANIFEST.json").read_text(encoding="utf-8"))
    report["source"] = {
        k: manifest[k] for k in ("github", "huggingface", "pdf_source", "downloaded_at")
    }

    # --- Annotation parsing and statistics ---------------------------------------------------
    parse_errors = []
    for i, s in enumerate(samples):
        try:
            s["_pages"] = _parse_list(s["evidence_pages"])
            s["_sources"] = _parse_list(s["evidence_sources"])
        except (TypeError, ValueError, SyntaxError) as exc:
            parse_errors.append({"index": i, "error": str(exc)})
            s["_pages"], s["_sources"] = None, None
    parsed = [s for s in samples if s["_pages"] is not None]
    page_value_types = Counter(type(p).__name__ for s in parsed for p in s["_pages"])
    n_pages = Counter(len(s["_pages"]) for s in parsed)
    not_answerable = [s for s in parsed if s["answer"] == "Not answerable"]
    empty = [s for s in parsed if not s["_pages"]]
    report["annotations"] = {
        "num_questions": len(samples),
        "num_documents": len({s["doc_id"] for s in samples}),
        "fields": sorted({k for s in samples for k in s if not k.startswith("_")}),
        "field_types": {
            k: sorted({type(s[k]).__name__ for s in samples})
            for k in sorted({k for s in samples for k in s if not k.startswith("_")})
        },
        "parse_errors": parse_errors,
        "evidence_page_value_types": dict(page_value_types),
        "num_evidence_pages_distribution": dict(sorted(n_pages.items())),
        "single_page_questions": sum(1 for s in parsed if len(s["_pages"]) == 1),
        "multi_page_questions": sum(1 for s in parsed if len(s["_pages"]) > 1),
        "empty_evidence_questions": len(empty),
        "not_answerable_questions": len(not_answerable),
        "not_answerable_with_empty_evidence": sum(1 for s in not_answerable if not s["_pages"]),
        "empty_evidence_but_answerable": [
            {"doc_id": s["doc_id"], "question": s["question"], "answer": s["answer"]}
            for s in empty
            if s["answer"] != "Not answerable"
        ],
        "answer_format": dict(Counter(s["answer_format"] for s in samples).most_common()),
        "doc_type_questions": dict(Counter(s["doc_type"] for s in samples).most_common()),
        "evidence_sources": dict(Counter(x for s in parsed for x in s["_sources"]).most_common()),
        "duplicate_rows": sum(c - 1 for c in Counter(_key(s) for s in samples).values() if c > 1),
    }

    # --- PDFs ---------------------------------------------------------------------------------
    doc_dir = args.raw / "documents"
    pdf_names = sorted(p.name for p in doc_dir.glob("*.pdf"))
    referenced = sorted({s["doc_id"] for s in samples})
    num_pages, texts = {}, {}
    for name in pdf_names:
        with pymupdf.open(doc_dir / name) as doc:
            num_pages[name] = doc.page_count
            texts[name] = [_norm(page.get_text()) for page in doc]
    by_hash = defaultdict(list)
    for rel, entry in manifest["files"].items():
        if rel.startswith("documents/"):
            by_hash[entry["sha256"]].append(rel.split("/", 1)[1])
    duplicates = [names for names in by_hash.values() if len(names) > 1]
    doc_types = {s["doc_id"]: s["doc_type"] for s in samples}
    pages_list = [num_pages[d] for d in referenced if d in num_pages]
    report["pdfs"] = {
        "num_pdfs": len(pdf_names),
        "referenced_but_missing": [d for d in referenced if d not in num_pages],
        "present_but_unreferenced": [d for d in pdf_names if d not in referenced],
        "pages_mean": statistics.mean(pages_list),
        "pages_median": statistics.median(pages_list),
        "pages_min": min(pages_list),
        "pages_max": max(pages_list),
        "pages_total": sum(pages_list),
        "pages_mean_by_doc_type": {
            t: round(statistics.mean(num_pages[d] for d in referenced if doc_types[d] == t), 1)
            for t in sorted(set(doc_types.values()))
        },
        "documents_without_text_layer": [n for n, t in texts.items() if not any(t)],
        "identical_pdf_files": duplicates,
        "questions_on_identical_files": {
            n: sum(1 for s in samples if s["doc_id"] == n) for names in duplicates for n in names
        },
        "num_pages": num_pages,
    }

    # --- Evidence-page indexing -------------------------------------------------------------
    all_pages = [(s, p) for s in parsed for p in s["_pages"]]
    report["indexing_bounds"] = {
        "min_evidence_page": min(p for _, p in all_pages),
        "max_evidence_page": max(p for _, p in all_pages),
        "zero_valued_evidence_pages": sum(1 for _, p in all_pages if p == 0),
        "evidence_page_equal_to_num_pages": sum(
            1 for s, p in all_pages if p == num_pages[s["doc_id"]]
        ),
        "evidence_page_above_num_pages": [
            {"doc_id": s["doc_id"], "page": p, "num_pages": num_pages[s["doc_id"]]}
            for s, p in all_pages
            if p > num_pages[s["doc_id"]]
        ],
    }
    # Empirical test: for single-page questions whose short answer string occurs in the document
    # text, does it occur on page index p-1 (1-based annotation) or on index p (0-based)?
    hits = Counter()
    tested = 0
    for s in parsed:
        if len(s["_pages"]) != 1 or s["answer_format"] not in {"Str", "Int", "Float"}:
            continue
        answer = _norm(str(s["answer"]))
        if len(answer) < 4 or answer == "not answerable":
            continue
        pages = texts[s["doc_id"]]
        if sum(answer in t for t in pages) != 1:
            continue  # only answers that occur on exactly one page are informative
        tested += 1
        p = s["_pages"][0]
        hits["one_based"] += 0 <= p - 1 < len(pages) and answer in pages[p - 1]
        hits["zero_based"] += 0 <= p < len(pages) and answer in pages[p]
    report["indexing_empirical"] = {
        "tested_questions": tested,
        "answer_on_page_if_one_based": hits["one_based"],
        "answer_on_page_if_zero_based": hits["zero_based"],
    }

    # --- GitHub samples.json vs Hugging Face split ---------------------------------------------
    try:
        hf = _hf_rows()
        gh_keys, hf_keys = Counter(_key(s) for s in samples), Counter(_key(r) for r in hf)
        report["github_vs_huggingface"] = {
            "hf_rows_source": f"{HF_ROWS_API} (dataset viewer, default/train)",
            "hf_rows": len(hf),
            "github_rows": len(samples),
            "only_in_hf": [
                dict(
                    zip(
                        (
                            "doc_id",
                            "question",
                            "answer",
                            "evidence_pages",
                            "evidence_sources",
                            "answer_format",
                        ),
                        k,
                    )
                )
                for k in (hf_keys - gh_keys).elements()
            ],
            "only_in_github": [list(k) for k in (gh_keys - hf_keys).elements()],
        }
    except OSError as exc:
        report["github_vs_huggingface"] = {"error": str(exc)}

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    summary = {k: v for k, v in report.items() if k != "pdfs"}
    summary["pdfs"] = {k: v for k, v in report["pdfs"].items() if k != "num_pages"}
    print(json.dumps(summary, indent=1, ensure_ascii=False)[:12000])


if __name__ == "__main__":
    main()
