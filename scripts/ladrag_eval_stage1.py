"""CP-4.5A: ground-truth graph-expansion evaluation of retrieval-eval-v1, Stage 1 (frozen D-021).

Phase 1 (no gold): load the Stage-1 graphs and the saved NIDX-0001 indices (hashes checked), rank all
nodes per question with the primary E5-R10 index and the element baselines, build the page rankings
of conditions A/B/C/D and the unbudgeted sets, and persist them (``rankings.jsonl``) with their hash.
Phase 2 (gold): load official evidence pages, validate, compute PR/IPR per question / condition / k,
reachability diagnostics, aggregates, subgroups, per-document results, exploratory paired statistics
and reference baselines. Every validation assertion must pass before any aggregate is written.

Usage:
  python scripts/ladrag_eval_stage1.py experiments/ladrag/configs/EVAL-0001-stage1.json
Outputs: experiments/ladrag/results/eval/<eval_id>/ (committed).
"""

import argparse
import hashlib
import importlib.metadata
import json
import statistics
import sys
import time
from pathlib import Path

import torch

from multimodal_document_extraction.datasets.mmlongbench_doc import load_mmlongbench_doc
from multimodal_document_extraction.retrieval.dense import MODELS, SentenceTransformerEncoder
from multimodal_document_extraction.studies.ladrag.expansion_eval import (
    CONDITIONS,
    condition_pages,
    irrelevant_pages_ratio,
    paired_comparison,
    perfect_recall,
    reachability,
    semantic_pages,
    truncate,
    unbudgeted_sets,
)
from multimodal_document_extraction.studies.ladrag.graph_retrieval import GraphIndex
from multimodal_document_extraction.studies.ladrag.node_retrieval import (
    BM25NodeRetriever,
    DenseNodeConfig,
    DenseNodeRetriever,
)
from multimodal_document_extraction.studies.ladrag.schema import DocumentGraph
from multimodal_document_extraction.utils.run_recording import git_state, utc_now

SOURCE_GROUPS = ("text", "figure", "chart", "table", "layout")


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
        encoding="utf-8",
        newline="\n",
    )


def _mean(values: list[float]) -> float | None:
    return round(statistics.mean(values), 4) if values else None


# --- phase 1: rankings (no gold) ----------------------------------------------------------------


def phase1_rankings(plan: dict, out: Path) -> tuple[list[dict], dict]:
    stats = json.loads(Path(plan["subset_stats"]).read_text(encoding="utf-8"))
    question_ids = [(q["question_id"], q["doc_id"]) for q in stats["questions"]]
    ds = load_mmlongbench_doc()
    text = {q.question_id: q.question for q in ds.questions}  # question text only
    graphs_root = Path("data/processed/ladrag/graphs") / plan["ingestion_run"]
    nidx_report = json.loads(
        Path(f"experiments/ladrag/results/node_index/{plan['node_index']}.json").read_text(
            encoding="utf-8"
        )
    )
    nidx_plan = json.loads(
        Path(f"experiments/ladrag/configs/{plan['node_index']}.json").read_text(encoding="utf-8")
    )
    index_root = Path("data/processed/ladrag/node_index") / plan["node_index"]
    doc_ids = sorted(stats["documents"])
    indices, hashes = {}, {}
    for doc_id in doc_ids:
        path = graphs_root / doc_id / "graph.json"
        hashes[doc_id] = _sha(path)
        assert hashes[doc_id] == nidx_report["graph_sha256"][doc_id], f"graph hash {doc_id}"
        indices[doc_id] = GraphIndex(DocumentGraph.load(path))
        num_pages = indices[doc_id].document_graph.metadata.num_pages
        assert num_pages == stats["documents"][doc_id]["num_pages"], f"num_pages {doc_id}"

    retrievers, encoders = {}, {}
    for row in nidx_plan["retrievers"]:
        name = row["name"]
        if name != plan["primary_retriever"] and name not in plan["element_baselines"]:
            continue
        if row["kind"] == "bm25":
            retriever = BM25NodeRetriever(text_field=row["text_field"])
            for doc_id in doc_ids:
                retriever.index_graph(indices[doc_id])
        else:
            if row["model"] not in encoders:
                encoders[row["model"]] = SentenceTransformerEncoder(
                    MODELS[row["model"]], device=plan["device"], batch_size=row["batch_size"]
                )
            retriever = DenseNodeRetriever(
                MODELS[row["model"]],
                encoders[row["model"]],
                DenseNodeConfig(row["text_field"], row["window_tokens"], row["overlap_tokens"]),
            )
            for doc_id in doc_ids:
                meta = json.loads(
                    (index_root / name / f"{doc_id}.json").read_text(encoding="utf-8")
                )
                assert meta["provenance"]["graph_sha256"] == hashes[doc_id], f"index hash {name}"
                retriever.load(doc_id, index_root / name, indices[doc_id])  # verifies texts/config
        retrievers[name] = retriever

    m = plan["seeds_m"]
    rows = []
    for question_id, doc_id in question_ids:
        index = indices[doc_id]
        num_pages = index.document_graph.metadata.num_pages
        started = time.perf_counter()
        hits = retrievers[plan["primary_retriever"]].rank_nodes(text[question_id], doc_id)
        latency = time.perf_counter() - started
        ranked = [h.node_id for h in hits]
        row = {
            "question_id": question_id,
            "doc_id": doc_id,
            "num_pages": num_pages,
            "seed_nodes": ranked[:m],
            "seed_scores": [h.score for h in hits[:m]],
            "node_ranking": ranked,
            "conditions": {c: condition_pages(c, index, ranked, num_pages, m) for c in CONDITIONS},
            "unbudgeted": unbudgeted_sets(index, ranked, num_pages, m),
            "diagnostic_rankings": {"m5_seeds": ranked[:5]},
            "baselines": {
                name: semantic_pages(
                    index, [h.node_id for h in r.rank_nodes(text[question_id], doc_id)]
                )
                for name, r in retrievers.items()
                if name != plan["primary_retriever"]
            },
            "query_latency_s": round(latency, 4),
        }
        rows.append(row)
    _write_jsonl(out / "rankings.jsonl", rows)
    meta = {
        "graph_sha256": hashes,
        "rankings_sha256_before_gold": _sha(out / "rankings.jsonl"),
        "encoders": {k: e.device for k, e in encoders.items()},
    }
    return rows, meta


# --- phase 2: gold evaluation ----------------------------------------------------------------------


def _validate(rows: list[dict], gold: dict, plan: dict, indices_pages: dict) -> list[str]:
    problems = []
    for r in rows:
        n = r["num_pages"]
        full_a = r["conditions"]["A"]
        if r["conditions"]["C"] != full_a:
            problems.append(f"{r['question_id']}: C != A")
        for c, pages in r["conditions"].items():
            if len(set(pages)) != len(pages):
                problems.append(f"{r['question_id']} {c}: duplicate pages")
            if not all(1 <= p <= n for p in pages):
                problems.append(f"{r['question_id']} {c}: page out of range")
            for k in plan["ks"]:
                if len(truncate(pages, k)) != min(k, n):
                    problems.append(f"{r['question_id']} {c} k={k}: not exactly min(k, pages)")
        seeds_pages = [indices_pages[r["doc_id"]][s] for s in r["seed_nodes"]]
        if full_a[: len(dict.fromkeys(seeds_pages))] != list(dict.fromkeys(seeds_pages)):
            problems.append(f"{r['question_id']}: A prefix is not the seed pages")
        g = gold[r["question_id"]]
        if not all(1 <= p <= n for p in g["pages"]) or g["flags"]:
            problems.append(f"{r['question_id']}: invalid gold")
    return problems


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    out = Path("experiments/ladrag/results/eval") / plan["eval_id"]
    out.mkdir(parents=True, exist_ok=True)
    started_at, wall = utc_now(), time.perf_counter()
    torch.cuda.reset_peak_memory_stats()

    rows, meta = phase1_rankings(plan, out)
    print(
        f"phase 1 done: {len(rows)} questions ranked; rankings hash {meta['rankings_sha256_before_gold'][:12]}"
    )

    # ---- gold enters only here ----
    stats = json.loads(Path(plan["subset_stats"]).read_text(encoding="utf-8"))
    ds = load_mmlongbench_doc()
    by_id = {q.question_id: q for q in ds.questions}
    gold, info = {}, {}
    for q in stats["questions"]:
        dq = by_id[q["question_id"]]
        assert sorted(dq.evidence_pages) == q["evidence_pages"], q["question_id"]
        gold[q["question_id"]] = {
            "pages": sorted(dq.evidence_pages),
            "flags": dq.metadata["quality_flags"],
        }
        info[q["question_id"]] = q
    graphs_root = Path("data/processed/ladrag/graphs") / plan["ingestion_run"]
    indices = {
        d: GraphIndex(DocumentGraph.load(graphs_root / d / "graph.json"))
        for d in stats["documents"]
    }
    node_pages = {d: {n: ix.node_page(n) for n in ix.nodes_in_order()} for d, ix in indices.items()}
    problems = _validate(rows, gold, plan, node_pages)
    evidence_ids = [q for q in gold if gold[q]["pages"]]
    if len(evidence_ids) != 35:
        problems.append(f"expected 35 evidence questions, got {len(evidence_ids)}")
    if _sha(out / "rankings.jsonl") != meta["rankings_sha256_before_gold"]:
        problems.append("rankings changed after gold was loaded")
    if problems:
        (out / "validation_failures.json").write_text(json.dumps(problems, indent=1))
        raise SystemExit(f"VALIDATION FAILED ({len(problems)}): {problems[:5]}")
    print("validation passed")

    ks = plan["ks"]
    per_q = []
    for r in rows:
        g = gold[r["question_id"]]["pages"]
        q = info[r["question_id"]]
        entry = {
            "question_id": r["question_id"],
            "doc_id": r["doc_id"],
            "gold_pages": g,
            "has_evidence": bool(g),
            "multi_page": q["multi_page"],
            "source_groups": q["source_groups"],
            "metrics": {},
            "unbudgeted": {},
            "baselines": {},
        }
        for c in CONDITIONS:
            entry["metrics"][c] = {}
            for k in ks:
                pages = truncate(r["conditions"][c], k)
                entry["metrics"][c][str(k)] = {
                    "pages": pages,
                    "pr": perfect_recall(g, pages),
                    "ipr": irrelevant_pages_ratio(g, pages),
                }
            s = r["unbudgeted"][c]
            entry["unbudgeted"][c] = {
                "pages": s,
                "n_pages": len(s),
                "pr": perfect_recall(g, s),
                "ipr": irrelevant_pages_ratio(g, s),
            }
        for name, pages_full in r["baselines"].items():
            entry["baselines"][name] = {
                str(k): {
                    "pr": perfect_recall(g, truncate(pages_full, k)),
                    "ipr": irrelevant_pages_ratio(g, truncate(pages_full, k)),
                }
                for k in ks
            }
        if g:
            index = indices[r["doc_id"]]
            entry["reachability"] = {
                str(m): reachability(index, r["node_ranking"], g, r["num_pages"], m)
                for m in plan["diagnostic_m"]
            }
            zero = [
                p for m_ in entry["reachability"].values() for p in m_["gold_pages_without_nodes"]
            ]
            if zero:
                raise SystemExit(f"pipeline inconsistency: gold pages without nodes {zero}")
        per_q.append(entry)
    _write_jsonl(out / "per_question.jsonl", per_q)

    # ---- aggregates ----
    ev = [e for e in per_q if e["has_evidence"]]
    groups = {
        "all_evidence": ev,
        "multi_page": [e for e in ev if e["multi_page"]],
        "single_page": [e for e in ev if not e["multi_page"]],
        **{f"source:{s}": [e for e in ev if s in e["source_groups"]] for s in SOURCE_GROUPS},
        **{f"doc:{d}": [e for e in ev if e["doc_id"] == d] for d in sorted(stats["documents"])},
    }

    def table(entries: list[dict]) -> dict:
        res = {"n": len(entries), "descriptive_only": len(entries) < 10}
        for c in CONDITIONS:
            res[c] = {
                str(k): {
                    "pr": _mean([e["metrics"][c][str(k)]["pr"] for e in entries]),
                    "ipr": _mean([e["metrics"][c][str(k)]["ipr"] for e in entries]),
                }
                for k in ks
            }
            res[c]["unbudgeted"] = {
                "pr": _mean([e["unbudgeted"][c]["pr"] for e in entries]),
                "ipr": _mean([e["unbudgeted"][c]["ipr"] for e in entries]),
                "mean_pages": _mean([e["unbudgeted"][c]["n_pages"] for e in entries]),
            }
        return res

    aggregates = {name: table(entries) for name, entries in groups.items()}
    noev = [e for e in per_q if not e["has_evidence"]]
    aggregates["no_evidence"] = {
        "n": len(noev),
        "note": "every condition returns k >= 1 pages, so NoEvidenceCorrect = 0 and IPR = 1 for all",
        "no_evidence_correct": _mean(
            [0.0 if e["metrics"]["A"]["1"]["pages"] else 1.0 for e in noev]
        ),
    }

    comparisons = {}
    bs = plan["bootstrap"]
    for name in ("all_evidence", "multi_page", "single_page"):
        comparisons[name] = {}
        for other in ("A", "C", "D"):
            for k in ks:
                comparisons[name][f"B_vs_{other}@{k}"] = {
                    "pr": paired_comparison(
                        groups[name], "pr", "B", other, k, lambda a, b: a > b,
                        bs["resamples"], bs["seed"],
                    ),
                    "ipr": paired_comparison(
                        groups[name], "ipr", "B", other, k, lambda a, b: a < b,
                        bs["resamples"], bs["seed"],
                    ),
                }  # fmt: skip

    def diagnostic(entries: list[dict], m: int) -> dict:
        reach = [(e["question_id"], e["reachability"][str(m)]) for e in entries]
        incomplete = [(q, r) for q, r in reach if r["missing_gold_before"]]
        ids = lambda pred: [q for q, r in reach if pred(r)]
        classes = {}
        for q, r in reach:
            classes.setdefault(r["primary_class"], []).append(q)
        distances = {}
        for _, r in incomplete:
            for d in r["missing_gold_detail"]:
                distances[d["graph_distance"]] = distances.get(d["graph_distance"], 0) + 1
        return {
            "n": len(reach),
            "primary_class": {c: {"n": len(v), "ids": v} for c, v in sorted(classes.items())},
            "1_semantic_already_complete": ids(lambda r: not r["missing_gold_before"]),
            "2_graph_completes": ids(lambda r: r["graph_completes"]),
            "3_pm1_completes": ids(lambda r: r["adjacent_completes"]),
            "4_graph_unique": ids(lambda r: r["graph_completes"] and not r["adjacent_completes"]),
            "5_pm1_unique": ids(lambda r: r["adjacent_completes"] and not r["graph_completes"]),
            "6_graph_adds_some_not_all": ids(
                lambda r: r["gold_added_by_graph"] and not r["graph_completes"]
            ),
            "7_graph_adds_only_irrelevant_when_gold_missing": ids(
                lambda r: (
                    r["missing_gold_before"]
                    and r["graph_neighbour_pages"]
                    and not r["gold_added_by_graph"]
                )
            ),
            "8_gold_unreachable_after_one_hop": ids(lambda r: r["gold_unreachable"]),
            "missing_gold_distance_counts": distances,
            "recovered_gold_also_pm1": sum(
                d["recovered_by_graph"] and d["is_seed_page_pm1"]
                for _, r in reach
                for d in r["missing_gold_detail"]
            ),
            "recovered_gold_total": sum(len(r["gold_added_by_graph"]) for _, r in reach),
            "mean_irrelevant_pages_added_by_graph": _mean(
                [len(r["irrelevant_added_by_graph"]) for _, r in reach]
            ),
            "mean_graph_neighbour_pages": _mean(
                [len(r["graph_neighbour_pages"]) for _, r in reach]
            ),
            "mean_adjacent_pages": _mean([len(r["adjacent_pages"]) for _, r in reach]),
        }

    diagnostics = {
        f"{name}_m{m}": diagnostic(groups[name], m)
        for name in ("multi_page", "all_evidence", "single_page")
        for m in plan["diagnostic_m"]
    }

    baselines = {}
    for name in ("all_evidence", "multi_page", "single_page"):
        entries = groups[name]
        names = sorted(entries[0]["baselines"]) if entries else []
        baselines[name] = {
            b: {
                str(k): {
                    "pr": _mean([e["baselines"][b][str(k)]["pr"] for e in entries]),
                    "ipr": _mean([e["baselines"][b][str(k)]["ipr"] for e in entries]),
                }
                for k in ks
            }
            for b in names
        }
    pagetext = {}
    for label, path in plan["pagetext_baselines"].items():
        rows_pt = {}
        for line in Path(path).read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            rows_pt[row["question_id"]] = row["ranking"]
        pagetext[label] = {}
        for name in ("all_evidence", "multi_page", "single_page"):
            entries = groups[name]
            pagetext[label][name] = {
                str(k): {
                    "pr": _mean(
                        [
                            perfect_recall(e["gold_pages"], rows_pt[e["question_id"]][:k])
                            for e in entries
                        ]
                    ),
                    "ipr": _mean(
                        [
                            irrelevant_pages_ratio(e["gold_pages"], rows_pt[e["question_id"]][:k])
                            for e in entries
                        ]
                    ),
                }
                for k in ks
            }

    run_meta = {
        "eval_id": plan["eval_id"],
        "checkpoint": plan["checkpoint"],
        "plan": plan,
        "started_at": started_at,
        "finished_at": utc_now(),
        "wall_seconds": round(time.perf_counter() - wall, 1),
        "git_commit": git_state()["commit"],
        "git_dirty": git_state().get("dirty"),
        "git_untracked": git_state().get("untracked"),
        "code_sha256": {
            f: _sha(Path(f))
            for f in (
                "scripts/ladrag_eval_stage1.py",
                "src/multimodal_document_extraction/studies/ladrag/expansion_eval.py",
                "src/multimodal_document_extraction/studies/ladrag/graph_retrieval.py",
                "src/multimodal_document_extraction/studies/ladrag/node_retrieval.py",
            )
        },
        "versions": {
            "python": sys.version.split()[0],
            **{
                n: importlib.metadata.version(n)
                for n in ("torch", "transformers", "sentence-transformers", "bm25s", "networkx")
            },
        },
        "gpu": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 3),
        "api_cost_usd": 0,
        "validation": "all assertions passed",
        "query_latency_s_mean": _mean([r["query_latency_s"] for r in rows]),
        **meta,
    }
    for name, data in (
        ("aggregates", aggregates),
        ("comparisons", comparisons),
        ("diagnostics", diagnostics),
        ("baselines", {"element_summary_nodes": baselines, "pagetext_phase3": pagetext}),
        ("run_meta", run_meta),
    ):
        (out / f"{name}.json").write_text(
            json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
        )
    print(f"written {out}")


if __name__ == "__main__":
    main()
