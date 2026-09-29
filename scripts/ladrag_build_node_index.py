"""Build node indices (CP-4.5) over the Stage-1 graphs and validate them without gold data.

Plan-driven (``experiments/ladrag/configs/NIDX-*.json``). For every retriever in the plan and every
graph of the ingestion run: index all nodes, save dense embeddings (reused by CP-4.5A so that seeds
are identical), and run validation checks — node count equals graph, node→page preserved, unique IDs,
node-ID index order, finite scores, deterministic re-ranking, re-built index reproducibility,
load-from-disk equality, top-k larger than the node count. Smoke searches use neutral, non-benchmark
queries from the plan; NO question text and NO gold evidence is read. No API.

Usage:
  python scripts/ladrag_build_node_index.py experiments/ladrag/configs/NIDX-0001-stage1.json
Writes data/processed/ladrag/node_index/<id>/<retriever>/ (not committed) and
experiments/ladrag/results/node_index/<id>.json (committed).
"""

import argparse
import importlib.metadata
import json
import math
import statistics
import sys
import time
from pathlib import Path

import numpy as np
import torch

from multimodal_document_extraction.retrieval.dense import MODELS, SentenceTransformerEncoder
from multimodal_document_extraction.studies.ladrag.graph_retrieval import GraphIndex
from multimodal_document_extraction.studies.ladrag.node_retrieval import (
    BM25NodeRetriever,
    DenseNodeConfig,
    DenseNodeRetriever,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph
from multimodal_document_extraction.utils.run_recording import git_state, utc_now


def _file_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate(retriever, index: GraphIndex, doc_id: str, queries: list[str]) -> dict:
    doc = retriever.indices[doc_id]
    ids = [r.node_id for r in doc.records]
    checks = {
        "all_graph_nodes_indexed": len(ids) == index.graph.number_of_nodes(),
        "unique_node_ids": len(set(ids)) == len(ids),
        "node_id_order": ids == index.nodes_in_order(),
        "pages_preserved": all(r.page == index.node_page(r.node_id) for r in doc.records),
    }
    finite, deterministic, latencies, smoke = True, True, [], {}
    for query in queries:
        started = time.perf_counter()
        hits = retriever.rank_nodes(query, doc_id)
        latencies.append(time.perf_counter() - started)
        finite &= all(h.score is None or math.isfinite(h.score) for h in hits)
        deterministic &= retriever.rank_nodes(query, doc_id) == hits
        smoke[query] = [h.node_id for h in hits[:3]]
    big_k = retriever.semantic_search(queries[0], doc_id, top_k_nodes=len(ids) + 100)
    checks.update(
        scores_finite=finite,
        ranking_deterministic=deterministic,
        top_k_larger_than_nodes_safe=len(big_k) == len(ids),
    )
    return {
        "stats": doc.stats(),
        "checks": checks,
        "query_latency_s": {
            "mean": round(statistics.mean(latencies), 4),
            "max": round(max(latencies), 4),
        },
        "smoke_top3": smoke,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    graphs_root = Path("data/processed/ladrag/graphs") / plan["ingestion_run"]
    out_root = Path("data/processed/ladrag/node_index") / plan["index_id"]
    doc_ids = sorted(p.name for p in graphs_root.iterdir() if p.is_dir())
    indices = {d: GraphIndex(DocumentGraph.load(graphs_root / d / "graph.json")) for d in doc_ids}
    graph_sha = {d: _file_sha256(graphs_root / d / "graph.json") for d in doc_ids}
    queries = plan["neutral_smoke_queries"]
    device = plan.get("device", "cuda")
    started_at, wall = utc_now(), time.perf_counter()
    torch.cuda.reset_peak_memory_stats()
    results, all_ok = {}, True

    for spec_row in plan["retrievers"]:
        name = spec_row["name"]
        row: dict = {"kind": spec_row["kind"], "text_field": spec_row["text_field"]}
        if spec_row["kind"] == "dense":
            spec = MODELS[spec_row["model"]]
            load_started = time.perf_counter()
            encoder = SentenceTransformerEncoder(
                spec, device=device, batch_size=spec_row.get("batch_size", 16)
            )
            row["model_load_seconds"] = round(time.perf_counter() - load_started, 2)
            config = DenseNodeConfig(
                text_field=spec_row["text_field"],
                window_tokens=spec_row["window_tokens"],
                overlap_tokens=spec_row["overlap_tokens"],
            )
            retriever = DenseNodeRetriever(spec, encoder, config)
            model = encoder.model
            row["provenance"] = {
                "model_id": spec.model_id,
                "revision": spec.revision,
                "embedding_dim": model.get_sentence_embedding_dimension(),
                "dtype": str(next(model.parameters()).dtype),
                "device": encoder.device,
                "max_seq_length": model.max_seq_length,
                "query_prefix": spec.query_prefix,
                "passage_prefix": spec.passage_prefix,
                "batch_size": spec_row.get("batch_size", 16),
            }
        else:
            retriever = BM25NodeRetriever(text_field=spec_row["text_field"])
        row["method"] = retriever.method_name
        row["config"] = retriever.config_dict()
        row["documents"] = {}
        for doc_id in doc_ids:
            retriever.index_graph(indices[doc_id])
            doc_row = _validate(retriever, indices[doc_id], doc_id, queries)
            if spec_row["kind"] == "dense":
                first = retriever.indices[doc_id]
                directory = out_root / name
                retriever.save(
                    doc_id,
                    directory,
                    {"ingestion_run": plan["ingestion_run"], "graph_sha256": graph_sha[doc_id]},
                )
                # rebuild from scratch: embeddings and rankings must reproduce
                rebuilt = DenseNodeRetriever(retriever.spec, retriever.encoder, retriever.config)
                rebuilt.index_graph(indices[doc_id])
                diff = float(
                    np.max(np.abs(rebuilt.indices[doc_id].embeddings - first.embeddings))
                    if first.embeddings.size
                    else 0.0
                )
                loaded = DenseNodeRetriever(retriever.spec, retriever.encoder, retriever.config)
                loaded.load(doc_id, directory, indices[doc_id])
                same_rebuilt = all(
                    rebuilt.rank_nodes(q, doc_id) == retriever.rank_nodes(q, doc_id)
                    for q in queries
                )
                same_loaded = all(
                    loaded.rank_nodes(q, doc_id) == retriever.rank_nodes(q, doc_id) for q in queries
                )
                doc_row["checks"].update(
                    rebuilt_rankings_identical=same_rebuilt, loaded_rankings_identical=same_loaded
                )
                doc_row["rebuild_max_abs_embedding_diff"] = diff
                retriever.indices[doc_id] = first
            all_ok &= all(doc_row["checks"].values())
            row["documents"][doc_id] = doc_row
        docs = row["documents"].values()
        row["totals"] = {
            key: sum(d["stats"][key] for d in docs)
            for key in (
                "nodes",
                "unscored_nodes",
                "single_window_nodes",
                "multi_window_nodes",
                "total_windows",
                "converted_non_string",
            )
        }
        row["totals"]["index_seconds"] = round(sum(d["stats"]["index_seconds"] for d in docs), 2)
        row["totals"]["max_windows"] = max(d["stats"]["max_windows"] for d in docs)
        row["totals"]["tokens_max"] = max(d["stats"]["tokens_max"] for d in docs)
        results[name] = row
        if spec_row["kind"] == "dense":
            del retriever, encoder, model
            torch.cuda.empty_cache()

    report = {
        "index_id": plan["index_id"],
        "checkpoint": plan["checkpoint"],
        "ingestion_run": plan["ingestion_run"],
        "graph_sha256": graph_sha,
        "started_at": started_at,
        "finished_at": utc_now(),
        "wall_seconds": round(time.perf_counter() - wall, 1),
        "git_commit": git_state()["commit"],
        "versions": {
            "python": sys.version.split()[0],
            **{
                n: importlib.metadata.version(n)
                for n in ("torch", "transformers", "sentence-transformers", "bm25s", "numpy")
            },
        },
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 2**30, 3),
        "api_cost_usd": 0,
        "neutral_smoke_queries": queries,
        "all_checks_passed": all_ok,
        "retrievers": results,
    }
    out = Path("experiments/ladrag/results/node_index") / f"{plan['index_id']}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1) + "\n", encoding="utf-8", newline="\n")
    summary = {name: {"totals": r["totals"], "method": r["method"]} for name, r in results.items()}
    print(
        json.dumps({k: report[k] for k in ("all_checks_passed", "peak_vram_gib", "wall_seconds")})
    )
    print(json.dumps(summary, indent=1))
    print(f"written {out}")
    if not all_ok:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
