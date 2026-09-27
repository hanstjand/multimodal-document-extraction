"""Paired comparison of retrieval runs on the same questions (from per_query.jsonl files).

For each k: PR per run (evidence questions), and for each run vs. the reference run the paired PR
difference with a seeded bootstrap 95% CI and win/tie/loss counts. Also reports the image-only vs.
text-layer split and first-k statistics. Output: JSON (committed) + printed table.

Usage:
  python scripts/compare_retrieval_runs.py --study ladrag --id CMP-0001 --reference EXP-0001-... \
      --runs EXP-0001-... EXP-0002-... EXP-0003-... [--ks 1 3 5 10 20] [--bootstrap 10000] [--seed 0]
"""

import argparse
import json
import random
import statistics
from pathlib import Path

from multimodal_document_extraction.utils.run_recording import utc_now, write_json


def _load(run_dir: Path) -> dict[str, dict]:
    rows = [
        json.loads(line)
        for line in (run_dir / "per_query.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    return {r["question_id"]: r for r in rows}


def _pr(row: dict, k: int) -> int:
    return int(set(row["evidence_pages"]) <= set(row["ranking"][:k]))


def _bootstrap_ci(diffs: list[int], n: int, seed: int) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(diffs, k=len(diffs))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--study", required=True)
    parser.add_argument("--id", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--runs", nargs="+", required=True)
    parser.add_argument("--ks", nargs="+", type=int, default=[1, 3, 5, 10, 20])
    parser.add_argument("--bootstrap", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    study_dir = Path("experiments") / args.study
    out_path = study_dir / "results" / "comparisons" / f"{args.id}.json"
    if out_path.exists():
        raise SystemExit(f"{out_path} exists; comparison IDs are never reused")
    runs = {rid: _load(study_dir / "runs" / rid) for rid in args.runs}
    if args.reference not in runs:
        raise SystemExit("--reference must be one of --runs")
    question_sets = {rid: set(rows) for rid, rows in runs.items()}
    if len({frozenset(s) for s in question_sets.values()}) != 1:
        raise SystemExit("runs do not cover the same questions")
    ref = runs[args.reference]
    evidence = sorted(q for q, r in ref.items() if r["evidence_pages"])
    groups = {
        "all_evidence": evidence,
        "text_layer": [q for q in evidence if not ref[q]["empty_index"]],
        "image_only": [q for q in evidence if ref[q]["empty_index"]],
        "multi_page": [q for q in evidence if ref[q]["is_multi_page"]],
    }

    report: dict = {
        "comparison_id": args.id,
        "created_at": utc_now(),
        "reference": args.reference,
        "runs": args.runs,
        "bootstrap": {"samples": args.bootstrap, "seed": args.seed, "ci": 0.95},
        "group_sizes": {g: len(qs) for g, qs in groups.items()},
        "pr": {},
        "paired_vs_reference": {},
        "first_perfect_recall_k": {},
    }
    for group, qs in groups.items():
        report["pr"][group] = {
            rid: {
                str(k): statistics.mean(_pr(rows[q], k) for q in qs) if qs else None
                for k in args.ks
            }
            for rid, rows in runs.items()
        }
    for rid, rows in runs.items():
        report["first_perfect_recall_k"][rid] = {
            "mean": statistics.mean(rows[q]["first_perfect_recall_k"] for q in evidence),
            "median": statistics.median(rows[q]["first_perfect_recall_k"] for q in evidence),
        }
        if rid == args.reference:
            continue
        per_k = {}
        for k in args.ks:
            diffs = [_pr(rows[q], k) - _pr(ref[q], k) for q in evidence]
            low, high = _bootstrap_ci(diffs, args.bootstrap, args.seed)
            per_k[str(k)] = {
                "diff": statistics.mean(diffs),
                "ci95": [low, high],
                "wins": sum(d > 0 for d in diffs),
                "ties": sum(d == 0 for d in diffs),
                "losses": sum(d < 0 for d in diffs),
            }
        fk = [
            rows[q]["first_perfect_recall_k"] - ref[q]["first_perfect_recall_k"] for q in evidence
        ]
        report["paired_vs_reference"][rid] = {
            "pr_at_k": per_k,
            "first_k_fewer_pages": sum(d < 0 for d in fk),
            "first_k_same": sum(d == 0 for d in fk),
            "first_k_more_pages": sum(d > 0 for d in fk),
        }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    write_json(out_path, report)

    print(f"{args.id}: {report['group_sizes']}")
    for group in ("all_evidence", "text_layer", "multi_page"):
        print(f"PR ({group}, n={len(groups[group])})")
        for rid in args.runs:
            vals = "  ".join(f"@{k}={report['pr'][group][rid][str(k)]:.3f}" for k in args.ks)
            print(f"  {rid:<40} {vals}")
    for rid, data in report["paired_vs_reference"].items():
        print(f"{rid} vs {args.reference} (all evidence):")
        for k, d in data["pr_at_k"].items():
            print(
                f"  PR@{k}: diff {d['diff']:+.3f}  CI95 [{d['ci95'][0]:+.3f}, {d['ci95'][1]:+.3f}]  "
                f"W/T/L {d['wins']}/{d['ties']}/{d['losses']}"
            )
        print(
            f"  first-k: fewer pages {data['first_k_fewer_pages']}, same {data['first_k_same']}, "
            f"more {data['first_k_more_pages']}"
        )
    print(f"written {out_path}")


if __name__ == "__main__":
    main()
