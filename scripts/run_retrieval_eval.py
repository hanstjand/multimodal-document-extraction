"""Run a page-retrieval evaluation experiment from a JSON config (EXPERIMENT_PROTOCOL.md).

Usage:
  python scripts/run_retrieval_eval.py experiments/ladrag/configs/<experiment_id>.json

Writes experiments/<study>/runs/<experiment_id>/ (run_meta.json, per_query.jsonl, config.json,
git_diff.patch if the tree is dirty) and appends one row per k to
experiments/<study>/results/results.csv.

Supported config methods:
  "bm25-pagetext"   with "bm25": {k1, b, method, stopwords}
  "dense-pagetext"  with "dense": {model: e5-large-v2 | bge-large-en, chunk_overlap_tokens, device,
                    batch_size}  (needs the `dense` extra)
"""

import argparse
import importlib.metadata
import json
import statistics
import sys
from pathlib import Path
from typing import Any

from multimodal_document_extraction.datasets.mmlongbench_doc import load_mmlongbench_doc, load_pages
from multimodal_document_extraction.datasets.subsets import Subset
from multimodal_document_extraction.evaluation.retrieval_metrics import (
    evaluate_retrieval,
    evaluate_retrieval_at_k,
    first_perfect_recall_k,
)
from multimodal_document_extraction.retrieval.bm25 import BM25Config, BM25PageRetriever
from multimodal_document_extraction.utils.run_recording import (
    append_results,
    create_run_dir,
    git_state,
    hardware_summary,
    utc_now,
    write_git_snapshot,
    write_json,
    write_jsonl,
)


def _versions(extra: list[str]) -> dict[str, str]:
    names = ["multimodal-document-extraction", "bm25s", "pymupdf", "numpy", *extra]
    return {"python": sys.version.split()[0], **{n: importlib.metadata.version(n) for n in names}}


def _build_retriever(config: dict) -> tuple[Any, str, list[str], dict]:
    """Return (retriever, components string, extra package names, runtime info)."""
    if config["method"] == "bm25-pagetext":
        retriever = BM25PageRetriever(BM25Config(**config["bm25"]))
        components = (
            f"bm25s={importlib.metadata.version('bm25s')}; text=pymupdf-page-text; "
            + "; ".join(f"{k}={v}" for k, v in config["bm25"].items())
        )
        return retriever, components, [], {}
    if config["method"] == "dense-pagetext":
        from multimodal_document_extraction.retrieval.dense import (
            MODELS,
            DenseConfig,
            DensePageRetriever,
            SentenceTransformerEncoder,
        )

        dense = config["dense"]
        spec = MODELS[dense["model"]]
        encoder = SentenceTransformerEncoder(
            spec, device=dense.get("device"), batch_size=dense.get("batch_size", 16)
        )
        retriever = DensePageRetriever(
            spec, encoder, DenseConfig(chunk_overlap_tokens=dense["chunk_overlap_tokens"])
        )
        components = (
            f"model={spec.model_id}@{spec.revision[:8]}; text=pymupdf-page-text; "
            f"window={spec.max_seq_length}; overlap={dense['chunk_overlap_tokens']}; score=MaxP-cosine; "
            f"sentence-transformers={importlib.metadata.version('sentence-transformers')}"
        )
        extra = ["torch", "sentence-transformers", "transformers"]
        return retriever, components, extra, {"device": encoder.device}
    raise SystemExit(f"unsupported method {config['method']}")


def _fmt(x: float | None) -> str:
    return "  n/a" if x is None else f"{x:.3f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("config", type=Path)
    args = parser.parse_args()
    config = json.loads(args.config.read_text(encoding="utf-8"))
    if config["method"] not in {"bm25-pagetext", "dense-pagetext"}:
        raise SystemExit(f"unsupported method {config['method']}")

    study_dir = Path("experiments") / config["study"]
    git = git_state()
    run_dir = create_run_dir(study_dir, config["experiment_id"])
    started = utc_now()

    ds = load_mmlongbench_doc()
    subset = Subset.load(config["subset"])
    questions = subset.select(ds.questions)
    if config["question_set"] == "clean":
        questions = tuple(q for q in questions if not q.metadata["quality_flags"])
    documents = [ds.documents[d] for d in subset.doc_ids]

    retriever, components, extra_packages, runtime = _build_retriever(config)
    for document in documents:
        retriever.index_document(document.doc_id, load_pages(document))
    results = [retriever.retrieve(q) for q in questions]
    method_name = results[0].method
    pairs = list(zip(questions, results, strict=True))

    k_max = max(d.num_pages for d in documents)
    by_k = evaluate_retrieval_at_k(pairs, range(1, k_max + 1))
    latencies = [r.latency_s for r in results]
    p95 = statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 2 else latencies[0]

    first_k = [first_perfect_recall_k(q, r) for q, r in pairs]
    evidence_first_k = [k for q, k in zip(questions, first_k, strict=True) if q.has_evidence]
    single = [(q, r) for q, r in pairs if q.has_evidence and not q.is_multi_page]
    multi = [(q, r) for q, r in pairs if q.is_multi_page]
    breakdown = {
        str(k): {
            "single_page_pr": evaluate_retrieval(
                (q, r.top_k(k)) for q, r in single
            ).perfect_recall.mean,
            "multi_page_pr": evaluate_retrieval(
                (q, r.top_k(k)) for q, r in multi
            ).perfect_recall.mean,
        }
        for k in config["report_ks"]
        if k <= k_max
    }

    dataset_version = f"github@{ds_commit}" if (ds_commit := _dataset_commit()) else "unknown"
    rows = []
    for k, evaluation in by_k.items():
        rows.append(
            {
                "experiment_id": config["experiment_id"],
                "date": started,
                "git_commit": git["commit"],
                "git_dirty": git["dirty"],
                "source_label": config["source_label"],
                "reproduction_level": config["reproduction_level"],
                "study": config["study"],
                "dataset": config["dataset"],
                "dataset_version": dataset_version,
                "dataset_subset": subset.name,
                "question_set": config["question_set"],
                "num_documents": len(documents),
                "num_queries": len(questions),
                "num_evidence_queries": evaluation.num_evidence_questions,
                "num_no_evidence_queries": evaluation.num_no_evidence_questions,
                "retrieval_method": method_name,
                "retrieval_unit": config["retrieval_unit"],
                "components": components,
                "top_k": k,
                "seed": "",
                "hardware": hardware_summary(),
                "perfect_recall": evaluation.perfect_recall.mean,
                "ipr": evaluation.irrelevant_pages_ratio.mean,
                "no_evidence_ipr": evaluation.no_evidence_irrelevant_pages_ratio.mean,
                "no_evidence_correct": evaluation.no_evidence_correct.mean,
                "latency_mean_s": statistics.mean(latencies),
                "latency_p50_s": statistics.median(latencies),
                "latency_p95_s": p95,
                "token_usage": 0,
                "notes": config.get("notes", ""),
            }
        )

    write_json(run_dir / "config.json", config)
    write_git_snapshot(run_dir, git)
    write_jsonl(
        run_dir / "per_query.jsonl",
        (
            {
                "question_id": q.question_id,
                "doc_id": q.doc_id,
                "doc_type": q.metadata["doc_type"],
                "evidence_pages": sorted(q.evidence_pages),
                "has_evidence": q.has_evidence,
                "is_multi_page": q.is_multi_page,
                "num_pages": ds.documents[q.doc_id].num_pages,
                "ranking": list(r.pages_in_rank_order()),
                "scores": [i.score for i in r.items],
                "first_perfect_recall_k": fk,
                "latency_s": r.latency_s,
                "empty_index": r.metadata["empty_index"],
            }
            for (q, r), fk in zip(pairs, first_k, strict=True)
        ),
    )
    write_json(
        run_dir / "run_meta.json",
        {
            "experiment_id": config["experiment_id"],
            "started_at": started,
            "finished_at": utc_now(),
            "git": {k: git[k] for k in ("commit", "dirty", "untracked")},
            "versions": _versions(extra_packages),
            "hardware": hardware_summary(),
            "runtime": runtime,
            "retrieval_method": method_name,
            "dataset_version": dataset_version,
            "subset": {
                "name": subset.name,
                "path": config["subset"],
                "metadata_totals": subset.metadata["totals"],
            },
            "index_seconds": {r.doc_id: r.metadata["index_seconds"] for r in results},
            "first_perfect_recall_k": {
                "evidence_questions": len(evidence_first_k),
                "mean": statistics.mean(evidence_first_k),
                "median": statistics.median(evidence_first_k),
                "max": max(evidence_first_k),
            },
            "pr_breakdown_single_vs_multi": breakdown,
            "results_rows": len(rows),
        },
    )
    append_results(study_dir / "results" / "results.csv", rows)

    print(
        f"{config['experiment_id']}: {len(questions)} questions, {len(documents)} documents, k=1..{k_max}"
    )
    print(f"{'k':>3}  {'PR':>6}  {'IPR':>6}  {'NE-IPR':>6}  {'NE-corr':>7}  single-PR  multi-PR")
    for k in config["report_ks"]:
        if k in by_k:
            e = by_k[k]
            b = breakdown.get(str(k), {})
            print(
                f"{k:>3}  {_fmt(e.perfect_recall.mean):>6}  {_fmt(e.irrelevant_pages_ratio.mean):>6}  "
                f"{_fmt(e.no_evidence_irrelevant_pages_ratio.mean):>6}  {_fmt(e.no_evidence_correct.mean):>7}  "
                f"{_fmt(b.get('single_page_pr')):>9}  {_fmt(b.get('multi_page_pr')):>8}"
            )
    print(
        f"first k with PR=1 (evidence questions): mean {statistics.mean(evidence_first_k):.1f}, "
        f"median {statistics.median(evidence_first_k)}, max {max(evidence_first_k)}"
    )
    print(f"latency per query: mean {statistics.mean(latencies) * 1000:.2f} ms; run dir {run_dir}")


def _dataset_commit() -> str | None:
    manifest = Path("data/raw/mmlongbench-doc/MANIFEST.json")
    if not manifest.exists():
        return None
    return json.loads(manifest.read_text(encoding="utf-8"))["github"]["commit"]


if __name__ == "__main__":
    main()
