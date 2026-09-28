"""CP-4.3B local VLM feasibility run: LAD-RAG† ingestion (steps A-D) on 5 representative pages.

Usage:
  python scripts/ladrag_vlm_feasibility.py qwen3.5-2b [--max-side 1280] [--max-new-tokens 8192]

Pages (chosen from pilot-v1 question metadata, see docs/studies/ladrag/LOCAL_VLM_FEASIBILITY.md):
  2305.14160v4.pdf p3-4 (text + chart, consecutive pages of multi-page question mmlb-0973) and p7 (table);
  reportq32015-…_95.pdf p10 (chart slide, no text layer); Campaign_038_…_v5e.pdf p9 (layout-heavy brochure).
Outputs: data/processed/ladrag/feasibility/<model>/<doc>/ (not committed) and
experiments/ladrag/results/feasibility/FEAS-<model>.json (committed). No API calls.
"""

import argparse
import importlib.metadata
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch

from multimodal_document_extraction.datasets.mmlongbench_doc import load_mmlongbench_doc, load_pages
from multimodal_document_extraction.studies.ladrag.ingestion import (
    DocumentIngestor,
    IngestionConfig,
)
from multimodal_document_extraction.studies.ladrag.local_vlm import (
    LOCAL_VLMS,
    TransformersVisionModel,
)
from multimodal_document_extraction.utils.model_cache import ModelCache
from multimodal_document_extraction.utils.run_recording import git_state, utc_now

PAGES = {
    "2305.14160v4.pdf": [3, 4, 7],
    "reportq32015-151009093138-lva1-app6891_95.pdf": [10],
    "Campaign_038_Introducing_AC_Whitepaper_v5e.pdf": [9],
}
PAGE_ROLES = {
    ("2305.14160v4.pdf", 3): "text-heavy + chart (cross-page pair, 1/2)",
    ("2305.14160v4.pdf", 4): "text-heavy + chart (cross-page pair, 2/2)",
    ("2305.14160v4.pdf", 7): "table",
    ("reportq32015-151009093138-lva1-app6891_95.pdf", 10): "chart slide, no text layer",
    ("Campaign_038_Introducing_AC_Whitepaper_v5e.pdf", 9): "layout-heavy brochure",
}
_WORD = re.compile(r"[a-z0-9]{3,}")


def _words(text: str) -> set[str]:
    return set(_WORD.findall(text.lower()))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("model", choices=sorted(LOCAL_VLMS))
    parser.add_argument("--max-side", type=int, default=1280)
    parser.add_argument("--max-new-tokens", type=int, default=8192)
    parser.add_argument("--restart", action="store_true", help="discard page records (cache kept)")
    args = parser.parse_args()

    spec = LOCAL_VLMS[args.model]
    config = IngestionConfig(image_max_side_px=args.max_side, max_output_tokens=args.max_new_tokens)
    ds = load_mmlongbench_doc()
    torch.cuda.reset_peak_memory_stats()
    model = TransformersVisionModel(spec)
    cache = ModelCache("data/processed/ladrag/llm_cache")
    ingestor = DocumentIngestor(model, config, cache)
    out_root = Path("data/processed/ladrag/feasibility") / args.model
    started = utc_now()
    rows, doc_summaries = [], {}

    for doc_id, pages in PAGES.items():
        document = ds.documents[doc_id]
        t = time.perf_counter()
        result = ingestor.ingest(
            doc_id, document.source_path, out_root / doc_id, pages=pages, restart=args.restart
        )
        doc_summaries[doc_id] = {**result.summary, "wall_seconds": time.perf_counter() - t}
        texts = {p.page_number: p.text or "" for p in load_pages(document)}
        for page in pages:
            record = json.loads(
                (out_root / doc_id / "pages" / f"page_{page:04d}.json").read_text(encoding="utf-8")
            )
            nodes = record["objects"]
            node_text = " ".join(
                " ".join(
                    str(o["attrs"].get(f) or "") for f in ("content", "title_or_heading", "summary")
                )
                for o in nodes
            )
            pdf_words = _words(texts[page])
            calls = record["calls"]
            rows.append(
                {
                    "doc_id": doc_id,
                    "page": page,
                    "role": PAGE_ROLES[(doc_id, page)],
                    "nodes": len(nodes),
                    "node_types": dict(Counter(o["attrs"]["type"] for o in nodes)),
                    "text_coverage": (len(pdf_words & _words(node_text)) / len(pdf_words))
                    if pdf_words
                    else None,
                    "pdf_words": len(pdf_words),
                    "flags": record["flags"],
                    "json_repairs": record["repairs"],
                    "ids_reassigned": record["ids_reassigned"],
                    "relations": dict(
                        Counter(f"{r['origin']}:{r['type']}" for r in record["relations"])
                    ),
                    "rejected_relations": dict(
                        Counter(x["reason"] for x in record["rejected_relations"])
                    ),
                    "calls": [
                        {
                            "task": c["task"],
                            "repair": c["repair"],
                            "cached": c["cached"],
                            "latency_s": round(c["latency_s"], 1),
                            "prompt_tokens": c["usage"].get("prompt_tokens"),
                            "completion_tokens": c["usage"].get("completion_tokens"),
                            "hit_max_tokens": c["usage"].get("completion_tokens")
                            == args.max_new_tokens,
                        }
                        for c in calls
                    ],
                    "page_model_seconds": round(
                        sum(c["latency_s"] for c in calls if not c["cached"]), 1
                    ),
                    "memory_chars": record["memory_chars"],
                }
            )

    report = {
        "feasibility_id": f"FEAS-{args.model}",
        "checkpoint": "CP-4.3B",
        "started_at": started,
        "finished_at": utc_now(),
        "git_commit": git_state()["commit"],
        "model_id": model.model_id,
        "load_seconds": round(model.load_seconds, 1),
        "peak_vram_gib": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "peak_reserved_vram_gib": round(torch.cuda.max_memory_reserved() / 2**30, 2),
        "device": torch.cuda.get_device_name(0),
        "versions": {
            n: importlib.metadata.version(n) for n in ("torch", "transformers", "pymupdf")
        },
        "config": config.to_dict(),
        "api_cost_usd": 0,
        "pages": rows,
        "documents": doc_summaries,
    }
    out = Path("experiments/ladrag/results/feasibility") / f"FEAS-{args.model}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )

    print(
        f"{model.model_id}: load {model.load_seconds:.1f}s, peak VRAM {report['peak_vram_gib']} GiB"
    )
    for r in rows:
        cov = "n/a" if r["text_coverage"] is None else f"{r['text_coverage']:.2f}"
        maxed = sum(c["hit_max_tokens"] for c in r["calls"])
        print(
            f"  {r['doc_id'][:28]:<28} p{r['page']:<3} {r['role'][:26]:<26} nodes={r['nodes']:<3} cov={cov:<5} "
            f"flags={r['flags']} repairs={r['json_repairs']} maxed={maxed} {r['page_model_seconds']}s rel={r['relations']}"
        )
    print(f"written {out}")


if __name__ == "__main__":
    main()
