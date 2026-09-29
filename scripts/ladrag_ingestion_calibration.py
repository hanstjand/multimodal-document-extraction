"""Plan-driven local ingestion runs for LAD-RAG† (CP-4.3C calibration, CP-4.3D pilot; no API).

Usage:
  python scripts/ladrag_ingestion_calibration.py experiments/ladrag/configs/<ID>.json [--restart]

Modes (plan "mode"):
  full                  — steps A–D over contiguous page ranges per document (DocumentIngestor.ingest);
                          ``"pages": "all"`` ingests the full document from page 1;
  node_extraction_only  — step A only (DocumentIngestor.extract_nodes), e.g. for resolution comparisons.
Outputs: <records_root>/<id>/ (records, not committed; default data/processed/ladrag/calibration) and
<report_dir>/<id>.json (committed report; default experiments/ladrag/results/calibration), plus
<records_root>/<id>/run.log (resource failures etc.). Interrupting and re-running the same plan resumes
at the first unfinished page (full mode) and reuses cached model replies.

Timing fields (renamed after CAL-0001/CAL-0002; those two reports keep the old names
``model_seconds_all`` / ``model_seconds_uncached`` / ``model_seconds_per_page`` / ``model_seconds_total``):
  est_no_cache_model_seconds — sum of the latencies stored with every call of a page record, including
      the original latency of replies served from the cache. An ESTIMATE of the model time the page
      would need without any cache; not time spent in this run.
  model_seconds_this_run — sum over calls that actually ran the model when the page record was written.
  wall_seconds — wall clock of this invocation only; pages resumed from an earlier (interrupted)
      invocation are not included, while model loading and the determinism re-runs are.
"""

import argparse
import importlib.metadata
import json
import logging
import re
import statistics
import time
from collections import Counter
from pathlib import Path

import torch

from multimodal_document_extraction.datasets.mmlongbench_doc import load_mmlongbench_doc, load_pages
from multimodal_document_extraction.studies.ladrag.ingestion import (
    DocumentIngestor,
    IngestionConfig,
    render_page,
)
from multimodal_document_extraction.studies.ladrag.local_vlm import (
    LOCAL_VLMS,
    TransformersVisionModel,
)
from multimodal_document_extraction.studies.ladrag.models import (
    TASK_NODE_EXTRACTION,
    GenerationRequest,
    MockVisionModel,
)
from multimodal_document_extraction.studies.ladrag.prompts import render_node_extraction
from multimodal_document_extraction.studies.ladrag.schema import page_prefix, parse_node_id
from multimodal_document_extraction.utils.model_cache import ModelCache
from multimodal_document_extraction.utils.run_recording import git_state, utc_now

WORD = re.compile(r"[a-z0-9]{3,}")
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)?(?![\w])")
CACHE_DIR = Path("data/processed/ladrag/llm_cache")
logger = logging.getLogger("ladrag_ingestion_run")


def _node_text(objects: list[dict]) -> str:
    return " ".join(
        " ".join(str(o["attrs"].get(f) or "") for f in ("content", "title_or_heading", "summary"))
        for o in objects
    )


def _page_metrics(record: dict, pdf_text: str, max_tokens: int) -> dict:
    objects = record["objects"]
    pdf_words = set(WORD.findall(pdf_text.lower()))
    node_words = set(WORD.findall(_node_text(objects).lower()))
    pdf_nums = set(NUMBER.findall(pdf_text))
    node_nums = [n for o in objects for n in NUMBER.findall(o["attrs"].get("content") or "")]
    calls = record["calls"]
    relations = record.get("relations", [])
    cross = [
        r
        for r in relations
        if (parse_node_id(r["from_object"]) or (0,))[0]
        != (parse_node_id(r["to_object"]) or (0,))[0]
    ]
    return {
        "page": record["page"],
        "status": record.get("status", "ok"),
        "resource_failures": len(record.get("resource_failures", [])),
        "nodes": len(objects),
        "node_types": dict(Counter(o["attrs"]["type"] for o in objects)),
        "has_text_layer": bool(pdf_words),
        "text_coverage": len(pdf_words & node_words) / len(pdf_words) if pdf_words else None,
        "numbers_extracted": len(node_nums),
        "numbers_in_pdf_precision": (
            sum(n in pdf_nums for n in node_nums) / len(node_nums)
            if node_nums and pdf_nums
            else None
        ),
        "pdf_numbers_recall": len(pdf_nums & set(node_nums)) / len(pdf_nums) if pdf_nums else None,
        "flags": record["flags"],
        "json_repairs": record["repairs"],
        "ids_reassigned": record["ids_reassigned"],
        "relations": dict(Counter(f"{r['origin']}:{r['type']}" for r in relations)),
        "cross_page_relations": dict(Counter(r["type"] for r in cross)),
        "rejected_relations": dict(
            Counter(x["reason"] for x in record.get("rejected_relations", []))
        ),
        "memory_chars": record.get("memory_chars"),
        "calls": [
            {
                "task": c["task"],
                "repair": c["repair"],
                "cached": c["cached"],
                "latency_s": round(c["latency_s"], 1),
                "prompt_tokens": c["usage"].get("prompt_tokens"),
                "completion_tokens": c["usage"].get("completion_tokens"),
                "runaway": c["usage"].get("completion_tokens") == max_tokens,
            }
            for c in calls
        ],
        "model_seconds_this_run": round(sum(c["latency_s"] for c in calls if not c["cached"]), 1),
        "est_no_cache_model_seconds": round(sum(c["latency_s"] for c in calls), 1),
    }


def _aggregate(rows: list[dict]) -> dict:
    calls = [c for r in rows for c in r["calls"]]
    first_calls = [c for c in calls if c["repair"] == 0]
    page_seconds = [r["est_no_cache_model_seconds"] for r in rows]
    flags = Counter(
        f.split(":")[0] if f.startswith("non_object") else f for r in rows for f in r["flags"]
    )
    cov = [r["text_coverage"] for r in rows if r["text_coverage"] is not None]
    prec = [
        r["numbers_in_pdf_precision"] for r in rows if r["numbers_in_pdf_precision"] is not None
    ]
    rec = [r["pdf_numbers_recall"] for r in rows if r["pdf_numbers_recall"] is not None]
    return {
        "pages": len(rows),
        "pages_with_nodes": sum(r["nodes"] > 0 for r in rows),
        "pages_resource_failed": sum(r["status"] == "resource_failure" for r in rows),
        "pages_resource_retried": sum(r["resource_failures"] > 0 for r in rows),
        "pages_ok_without_nodes": sum(r["status"] == "ok" and r["nodes"] == 0 for r in rows),
        "nodes_total": sum(r["nodes"] for r in rows),
        "node_types": dict(sum((Counter(r["node_types"]) for r in rows), Counter()).most_common()),
        "pages_with_json_failure": sum(
            any(f.startswith("json_invalid") for f in r["flags"]) for r in rows
        ),
        "pages_repaired": sum(r["json_repairs"] > 0 for r in rows),
        "flags": dict(sorted(flags.items())),
        "calls_total": len(calls),
        "runaway_calls": sum(c["runaway"] for c in calls),
        "runaway_rate_first_calls": (sum(c["runaway"] for c in first_calls) / len(first_calls))
        if first_calls
        else None,
        "cached_calls": sum(c["cached"] for c in calls),
        "est_no_cache_model_seconds_per_page": {
            "mean": round(statistics.mean(page_seconds), 1),
            "median": round(statistics.median(page_seconds), 1),
            "max": round(max(page_seconds), 1),
        },
        "est_no_cache_model_seconds_total": round(sum(page_seconds), 1),
        "model_seconds_this_run_total": round(sum(r["model_seconds_this_run"] for r in rows), 1),
        "text_coverage_mean": round(statistics.mean(cov), 3) if cov else None,
        "numbers_in_pdf_precision_mean": round(statistics.mean(prec), 3) if prec else None,
        "pdf_numbers_recall_mean": round(statistics.mean(rec), 3) if rec else None,
        "cross_page_relations": dict(
            sum((Counter(r["cross_page_relations"]) for r in rows), Counter()).most_common()
        ),
        "rejected_relations": dict(
            sum((Counter(r["rejected_relations"]) for r in rows), Counter()).most_common()
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("plan", type=Path)
    parser.add_argument("--restart", action="store_true")
    parser.add_argument(
        "--mock", action="store_true", help="dry run with MockVisionModel (no GPU model)"
    )
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    cal_id = plan.get("run_id") or plan["calibration_id"]
    config = IngestionConfig(
        image_max_side_px=plan["max_side"], max_output_tokens=plan["max_new_tokens"]
    )
    ds = load_mmlongbench_doc()
    torch.cuda.reset_peak_memory_stats()
    if args.mock:
        cal_id += "-MOCK"
        model = MockVisionModel()
    else:
        model = TransformersVisionModel(LOCAL_VLMS[plan["model"]])
    cache = ModelCache(CACHE_DIR)
    ingestor = DocumentIngestor(model, config, cache)
    out_root = Path(plan.get("records_root", "data/processed/ladrag/calibration")) / cal_id
    out_root.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(out_root / "run.log", "a", "utf-8")],
    )
    started, wall_start = utc_now(), time.perf_counter()
    documents, rows = {}, []

    for doc_id, spec in plan["documents"].items():
        document = ds.documents[doc_id]
        texts = {p.page_number: p.text or "" for p in load_pages(document)}
        pages = list(document.page_numbers()) if spec["pages"] == "all" else list(spec["pages"])
        t = time.perf_counter()
        if plan["mode"] == "full":
            logger.info("ingesting %s (%d pages)", doc_id, len(pages))
            result = ingestor.ingest(
                doc_id,
                document.source_path,
                out_root / doc_id,
                pages=pages,
                restart=args.restart,
            )
            records = [
                json.loads(
                    (out_root / doc_id / "pages" / f"page_{p:04d}.json").read_text(encoding="utf-8")
                )
                for p in pages
            ]
            documents[doc_id] = {
                "role": spec["role"],
                "pages": spec["pages"],
                "num_pages": document.num_pages,
                "summary": result.summary,
                "memory_chars_series": [r["memory_chars"] for r in records],
                "wall_seconds": round(time.perf_counter() - t, 1),
            }
        elif plan["mode"] == "node_extraction_only":
            records = []
            for page in pages:
                path = out_root / doc_id / f"nodes_page_{page:04d}.json"
                if path.exists() and not args.restart:
                    records.append(json.loads(path.read_text(encoding="utf-8")))
                    continue
                record = ingestor.extract_nodes(document.source_path, page)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8", newline="\n"
                )
                records.append(record)
            documents[doc_id] = {
                "role": spec["role"],
                "pages": spec["pages"],
                "wall_seconds": round(time.perf_counter() - t, 1),
            }
        else:
            raise SystemExit(f"unknown mode {plan['mode']}")
        for record in records:
            rows.append(
                {
                    "doc_id": doc_id,
                    **_page_metrics(record, texts[record["page"]], plan["max_new_tokens"]),
                }
            )

    determinism = []
    for doc_id, page in plan.get("determinism_check", []):
        record = json.loads(
            (out_root / doc_id / "pages" / f"page_{page:04d}.json").read_text(encoding="utf-8")
        )
        first = next(
            c for c in record["calls"] if c["task"] == TASK_NODE_EXTRACTION and c["repair"] == 0
        )
        cached_text = cache.get(first["cache_key"])["reply"]["text"]
        image = render_page(
            ds.documents[doc_id].source_path, page, config.render_dpi, config.image_max_side_px
        )
        request = GenerationRequest(
            TASK_NODE_EXTRACTION, render_node_extraction(page_prefix(page)), (image,), config.params
        )
        rerun = model.generate(request)  # direct call, bypassing the cache
        determinism.append(
            {
                "doc_id": doc_id,
                "page": page,
                "identical_text": rerun.text == cached_text,
                "cached_chars": len(cached_text),
                "rerun_chars": len(rerun.text),
                "rerun_seconds": round(rerun.latency_s, 1),
            }
        )

    comparison = None
    if plan.get("compare_with"):
        base_root = Path("data/processed/ladrag/calibration") / (
            plan["compare_with"] + ("-MOCK" if args.mock else "")
        )
        comparison = []
        for row in rows:
            base_path = base_root / row["doc_id"] / "pages" / f"page_{row['page']:04d}.json"
            if not base_path.exists():
                continue
            base = json.loads(base_path.read_text(encoding="utf-8"))
            base_a = {k: base[k] for k in ("page", "objects", "flags", "repairs", "ids_reassigned")}
            base_a["flags"] = [
                f
                for f in base["flags"]
                if "node_extraction" in f or f.startswith(("container", "non_object"))
            ]
            base_a["calls"] = [c for c in base["calls"] if c["task"] == TASK_NODE_EXTRACTION]
            texts = {p.page_number: p.text or "" for p in load_pages(ds.documents[row["doc_id"]])}
            b = _page_metrics(base_a, texts[row["page"]], plan["max_new_tokens"])
            comparison.append(
                {
                    "doc_id": row["doc_id"],
                    "page": row["page"],
                    "nodes": [b["nodes"], row["nodes"]],
                    "figure_nodes": [
                        b["node_types"].get("figure", 0),
                        row["node_types"].get("figure", 0),
                    ],
                    "node_types": [b["node_types"], row["node_types"]],
                    "text_coverage": [b["text_coverage"], row["text_coverage"]],
                    "numbers_in_pdf_precision": [
                        b["numbers_in_pdf_precision"],
                        row["numbers_in_pdf_precision"],
                    ],
                    "json_repairs": [b["json_repairs"], row["json_repairs"]],
                    "est_no_cache_model_seconds": [
                        b["est_no_cache_model_seconds"],
                        row["est_no_cache_model_seconds"],
                    ],
                    "prompt_tokens": [
                        b["calls"][0]["prompt_tokens"],
                        row["calls"][0]["prompt_tokens"],
                    ],
                }
            )

    report = {
        "calibration_id": cal_id,
        "checkpoint": plan["checkpoint"],
        "mode": plan["mode"],
        "started_at": started,
        "finished_at": utc_now(),
        "wall_seconds": round(time.perf_counter() - wall_start, 1),
        "wall_seconds_scope": "this invocation only (excludes pages resumed from earlier invocations)",
        "git_commit": git_state()["commit"],
        "model_id": model.model_id,
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
        "device": torch.cuda.get_device_name(0),
        "versions": {
            n: importlib.metadata.version(n) for n in ("torch", "transformers", "pymupdf")
        },
        "config": config.to_dict(),
        "api_cost_usd": 0,
        "aggregate": _aggregate(rows),
        "documents": documents,
        "determinism": determinism,
        "comparison_with": plan.get("compare_with"),
        "comparison": comparison,
        "pages": rows,
    }
    out = (
        (out_root / "report.json")
        if args.mock
        else Path(plan.get("report_dir", "experiments/ladrag/results/calibration"))
        / f"{cal_id}.json"
    )
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )
    print(
        json.dumps(
            {
                k: report[k]
                for k in (
                    "calibration_id",
                    "model_id",
                    "peak_vram_gib",
                    "wall_seconds",
                    "aggregate",
                    "determinism",
                )
            },
            indent=1,
        )
    )
    print(f"written {out}")


if __name__ == "__main__":
    main()
