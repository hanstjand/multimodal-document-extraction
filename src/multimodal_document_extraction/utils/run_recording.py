"""Experiment run recording per docs/EXPERIMENT_PROTOCOL.md.

A run writes ``experiments/<study>/runs/<experiment_id>/`` (not committed): ``run_meta.json``,
``per_query.jsonl``, ``config.json`` and, if the working tree is dirty, ``git_diff.patch``.
Aggregated rows are appended to ``experiments/<study>/results/results.csv`` (committed).
"""

import csv
import json
import platform
import subprocess
from collections.abc import Iterable, Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

RESULTS_FIELDS = [
    "experiment_id",
    "date",
    "git_commit",
    "git_dirty",
    "source_label",
    "reproduction_level",
    "study",
    "dataset",
    "dataset_version",
    "dataset_subset",
    "question_set",
    "num_documents",
    "num_queries",
    "num_evidence_queries",
    "num_no_evidence_queries",
    "retrieval_method",
    "retrieval_unit",
    "components",
    "top_k",
    "seed",
    "hardware",
    "perfect_recall",
    "ipr",
    "no_evidence_ipr",
    "no_evidence_correct",
    "latency_mean_s",
    "latency_p50_s",
    "latency_p95_s",
    "token_usage",
    "notes",
]


def _git(args: list[str], cwd: Path) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, capture_output=True, text=True, check=True, encoding="utf-8"
    ).stdout


def git_state(repo_root: Path | str = ".") -> dict[str, Any]:
    """Commit hash, dirty flag, tracked diff against HEAD, and untracked files."""
    root = Path(repo_root)
    status = _git(["status", "--porcelain"], root)
    return {
        "commit": _git(["rev-parse", "HEAD"], root).strip(),
        "dirty": bool(status.strip()),
        "diff": _git(["diff", "HEAD"], root),
        "untracked": [line[3:] for line in status.splitlines() if line.startswith("??")],
    }


def hardware_summary() -> str:
    return (
        f"{platform.system()} {platform.release()}; {platform.processor()}; see docs/ENVIRONMENT.md"
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def create_run_dir(study_dir: Path | str, experiment_id: str) -> Path:
    """Create ``<study_dir>/runs/<experiment_id>``; refuse to reuse an experiment ID."""
    run_dir = Path(study_dir) / "runs" / experiment_id
    if run_dir.exists():
        raise FileExistsError(f"{run_dir} exists; experiment IDs are never reused")
    run_dir.mkdir(parents=True)
    return run_dir


def write_json(path: Path, data: Any) -> None:
    path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n"
    )


def write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def write_git_snapshot(run_dir: Path, state: Mapping[str, Any]) -> None:
    """Save the uncommitted diff (and untracked file list) so a dirty run stays reproducible."""
    if state["dirty"]:
        patch = state["diff"]
        if state["untracked"]:
            patch += "\n# Untracked files at run time (contents not included in this diff):\n"
            patch += "".join(f"#   {p}\n" for p in state["untracked"])
        (run_dir / "git_diff.patch").write_text(patch, encoding="utf-8", newline="\n")


def append_results(csv_path: Path | str, rows: Iterable[Mapping[str, Any]]) -> None:
    """Append rows to the results CSV (header created if missing; experiment IDs must be new)."""
    csv_path = Path(csv_path)
    rows = list(rows)
    existing_ids: set[str] = set()
    if csv_path.exists():
        with csv_path.open(encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            if reader.fieldnames != RESULTS_FIELDS:
                raise ValueError(f"{csv_path} has a different header; refusing to append")
            existing_ids = {r["experiment_id"] for r in reader}
    clash = existing_ids & {r["experiment_id"] for r in rows}
    if clash:
        raise ValueError(f"experiment IDs already in {csv_path}: {sorted(clash)}")
    unknown = {k for r in rows for k in r} - set(RESULTS_FIELDS)
    if unknown:
        raise ValueError(f"unknown result fields: {sorted(unknown)}")
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    new_file = not csv_path.exists()
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=RESULTS_FIELDS, lineterminator="\n")
        if new_file:
            writer.writeheader()
        writer.writerows(rows)
