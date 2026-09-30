"""Weekly-meeting figures from the committed EVAL-0001 Stage-1 outputs.

Read-only: this script only reads the committed Stage-1 JSON files; it does not rerun any
retrieval or model inference and does not write to the experiment directory. Every plotted
value is read from JSON, printed, and checked against the drawn matplotlib artists.

    python scripts/make_weekly_meeting_figures.py

Outputs (PNG 300 dpi transparent + SVG) and a `figure_data.json` manifest go to
docs/studies/ladrag/figures/weekly-meeting/.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator

ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = ROOT / "experiments" / "ladrag" / "results" / "eval" / "EVAL-0001-stage1"
OUT_DIR = ROOT / "docs" / "studies" / "ladrag" / "figures" / "weekly-meeting"
SOURCES = {
    "aggregates": EVAL_DIR / "aggregates.json",
    "diagnostics": EVAL_DIR / "diagnostics.json",
    "hub_analysis": EVAL_DIR / "hub_analysis.json",
}
FOOTER = "EVAL-0001 Stage 1"

# Restrained palette: navy for primary marks, gray for secondary, muted red only for
# failure / highlight.
NAVY = "#1F3A5F"
GRAY = "#8C96A3"
LIGHT_GRAY = "#A9B2BD"
MUTED_RED = "#B04A4A"
INK = "#222222"
MUTED_INK = "#666666"
GRID = "#D9DDE2"

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
        "font.size": 14,
        "axes.labelsize": 15,
        "xtick.labelsize": 13,
        "ytick.labelsize": 13,
        "legend.fontsize": 13,
        "axes.edgecolor": MUTED_INK,
        "axes.labelcolor": INK,
        "xtick.color": INK,
        "ytick.color": INK,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.linewidth": 0.8,
        "grid.color": GRID,
        "grid.linewidth": 0.7,
        "svg.fonttype": "none",  # keep SVG text as editable text in PowerPoint
    }
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git_commit() -> str:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def load(name: str) -> dict:
    return json.loads(SOURCES[name].read_text(encoding="utf-8"))


def annotate(ax, text: str) -> None:
    """Small left-aligned context line above the axes (not a figure title)."""
    ax.set_title(text, loc="left", fontsize=13, color=MUTED_INK, pad=10)


def save(fig, ax, stem: str, note: str | None = None) -> list[str]:
    """Footer (left) and optional note (right) on one line below the x-axis label."""
    below = {
        "xycoords": "axes fraction",
        "textcoords": "offset points",
        "va": "top",
        "fontsize": 10,
        "color": MUTED_INK,
    }
    ax.annotate(FOOTER, xy=(0, 0), xytext=(0, -58), ha="left", **below)
    if note:
        ax.annotate(note, xy=(1, 0), xytext=(0, -58), ha="right", **below)
    paths = []
    for ext, kw in (("png", {"dpi": 300}), ("svg", {})):
        path = OUT_DIR / f"{stem}.{ext}"
        fig.savefig(path, bbox_inches="tight", pad_inches=0.05, transparent=True, **kw)
        paths.append(str(path.relative_to(ROOT)).replace("\\", "/"))
    plt.close(fig)
    return paths


def check(label: str, plotted, expected) -> None:
    if list(plotted) != list(expected):
        raise AssertionError(f"{label}: plotted {list(plotted)} != source {list(expected)}")


def hbar_values(ax) -> list:
    """Bar widths in top-to-bottom order as drawn (y axis is inverted)."""
    bars = sorted(ax.patches, key=lambda p: p.get_y())
    return [p.get_width() for p in bars]


def label_bar_ends(ax, values, fmt="{:,}") -> None:
    xmax = max(values)
    for i, v in enumerate(values):
        ax.text(v + xmax * 0.012, i, fmt.format(v), va="center", ha="left", fontsize=13, color=INK)
    ax.set_xlim(0, xmax * 1.12)


def style_hbar(ax, xlabel: str) -> None:
    ax.invert_yaxis()
    ax.set_xlabel(xlabel)
    ax.xaxis.grid(True)
    ax.set_axisbelow(True)
    ax.spines["left"].set_visible(False)
    ax.tick_params(axis="y", length=0)


# ---------------------------------------------------------------- Figure 1
def figure_1(agg: dict) -> dict:
    mp = agg["multi_page"]
    budgets = ["1", "3", "5", "10"]
    # C is omitted because it is page-level identical to A; verify rather than assume.
    for k in budgets:
        if mp["C"][k]["pr"] != mp["A"][k]["pr"]:
            raise AssertionError(f"C differs from A at k={k}; omitting C is not justified")
    series = [
        ("A", "Semantic-only", NAVY, "-", "o"),
        ("B", "+ Graph (1-hop)", MUTED_RED, "--", "s"),
        ("D", "p±1 adjacency", GRAY, ":", "^"),
    ]
    xs = [int(k) for k in budgets]
    data = {m: [mp[m][k]["pr"] for k in budgets] for m, *_ in series}

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    for m, label, color, ls, marker in series:
        ax.plot(
            xs,
            data[m],
            color=color,
            linestyle=ls,
            linewidth=2.2,
            marker=marker,
            markersize=8,
            label=label,
            clip_on=False,
            zorder=3,
        )
    for m, label, color, *_ in series:
        ax.annotate(
            f"{label}  {data[m][-1]:.3f}",
            xy=(xs[-1], data[m][-1]),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            fontsize=13,
            color=INK,
        )
    ax.set_xticks(xs)
    ax.set_xlim(0.5, 10.4)
    ax.set_ylim(0.0, 1.0)
    ax.set_xlabel("Retrieval page budget k")
    ax.set_ylabel("Perfect Recall")
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    annotate(ax, f"Multi-page evidence questions, n={mp['n']}")

    for line, (m, *_rest) in zip(ax.get_lines(), series):
        check(f"fig1 {m} x", line.get_xdata(), xs)
        check(f"fig1 {m} PR", line.get_ydata(), [mp[m][k]["pr"] for k in budgets])
    files = save(fig, ax, "stage1_multi_page_pr_vs_k")
    return {
        "source": "aggregates.json -> multi_page -> {A,B,D} -> {1,3,5,10} -> pr",
        "n": mp["n"],
        "k": xs,
        "values": {f"{m} ({label})": data[m] for m, label, *_ in series},
        "omitted": "C (verified identical to A at page level for k in 1,3,5,10)",
        "files": files,
    }


# ---------------------------------------------------------------- Figure 2
def figure_2(diag: dict) -> dict:
    counts = diag["multi_page_m10"]["missing_gold_distance_counts"]
    order = [("1", "1 hop"), ("2", "2 hops"), ("3+", "3+ hops"), ("unreachable", "Unreachable")]
    if set(counts) != {key for key, _ in order}:
        raise AssertionError(f"unexpected distance keys {sorted(counts)}")
    labels = [lab for _, lab in order]
    values = [counts[key] for key, _ in order]
    colors = [MUTED_RED if key == "unreachable" else NAVY for key, _ in order]
    n = sum(values)

    fig, ax = plt.subplots(figsize=(7.2, 3.6))
    ax.barh(range(len(values)), values, color=colors, height=0.62)
    ax.set_yticks(range(len(values)), labels)
    style_hbar(ax, "Number of missing gold pages")
    ax.xaxis.set_major_locator(MaxNLocator(integer=True))
    label_bar_ends(ax, values)
    annotate(ax, f"Missing gold pages before graph expansion, n={n}")

    check("fig2 counts", hbar_values(ax), values)
    files = save(fig, ax, "stage1_missing_gold_graph_distance")
    return {
        "source": "diagnostics.json -> multi_page_m10 -> missing_gold_distance_counts",
        "values": dict(zip(labels, values)),
        "total": n,
        "files": files,
    }


# ---------------------------------------------------------------- Figure 3
def figure_3(hub: dict) -> dict:
    edge_types = hub["edge_types"]
    items = sorted(edge_types.items(), key=lambda kv: (-kv[1], kv[0]))
    labels = [k for k, _ in items]
    values = [v for _, v in items]
    # edge_types counts relation-type labels: each cross-page neighbour link carries the tuple
    # of relation types merged onto its edge (ladrag_eval_stage1_hubs.py: edge_types.update(
    # n.types)), so labels >= links. The link total is seed_cross_page_links, which must also
    # equal the per-link counts (earlier + later pages, and neighbour_node_types).
    links = hub["seed_cross_page_links"]
    if links != hub["links_to_earlier_pages"] + hub["links_to_later_pages"]:
        raise AssertionError("seed_cross_page_links != earlier + later")
    if links != sum(hub["neighbour_node_types"].values()):
        raise AssertionError("seed_cross_page_links != sum(neighbour_node_types)")
    labels_total = sum(values)
    if labels_total < links or max(values) > links:
        raise AssertionError(f"edge_types sum {labels_total} inconsistent with {links} links")
    total = links
    share = edge_types["is_part_of_section"] / total
    colors = [NAVY if k == "is_part_of_section" else LIGHT_GRAY for k in labels]

    fig, ax = plt.subplots(figsize=(7.6, 4.2))
    ax.barh(range(len(values)), values, color=colors, height=0.62)
    ax.set_yticks(range(len(values)), labels)
    style_hbar(ax, "Number of cross-page neighbour links")
    label_bar_ends(ax, values)
    annotate(ax, f"is_part_of_section = {share:.1%} of {total:,} cross-page neighbour links")

    check("fig3 counts", hbar_values(ax), values)
    files = save(
        fig,
        ax,
        "stage1_cross_page_relation_distribution",
        note=f"A link can carry more than one relation type "
        f"({labels_total:,} labels on {total:,} links)",
    )
    return {
        "source": "hub_analysis.json -> edge_types",
        "values": dict(items),
        "relation_labels_total": labels_total,
        "cross_page_links_total": total,
        "total_source": "hub_analysis.json -> seed_cross_page_links "
        "(= links_to_earlier_pages + links_to_later_pages "
        "= sum(neighbour_node_types))",
        "is_part_of_section_share_of_links": round(share, 6),
        "is_part_of_section_share_of_labels": round(
            edge_types["is_part_of_section"] / labels_total, 6
        ),
        "files": files,
    }


# ---------------------------------------------------------------- Figure 4
OTHER_MIN_SHARE = 0.025  # node types below 2.5% of reached nodes are grouped into "Other"


def figure_4(hub: dict) -> dict:
    node_types = hub["neighbour_node_types"]
    total = sum(node_types.values())
    items = sorted(node_types.items(), key=lambda kv: (-kv[1], kv[0]))
    major = [(k, v) for k, v in items if v / total >= OTHER_MIN_SHARE]
    grouped = [(k, v) for k, v in items if v / total < OTHER_MIN_SHARE]
    rows = major + ([("Other", sum(v for _, v in grouped))] if grouped else [])
    labels = [k for k, _ in rows]
    values = [v for _, v in rows]
    if sum(values) != total:
        raise AssertionError("figure 4 drops values")
    emph = {"section_header", "title"}
    share = sum(node_types[k] for k in emph) / total
    colors = [NAVY if k in emph else LIGHT_GRAY for k in labels]

    fig, ax = plt.subplots(figsize=(7.6, 4.6))
    ax.barh(range(len(values)), values, color=colors, height=0.62)
    ax.set_yticks(range(len(values)), labels)
    style_hbar(ax, "Number of reached neighbour nodes")
    label_bar_ends(ax, values)
    annotate(ax, f"section_header + title = {share:.1%} of {total:,} reached nodes")

    check("fig4 counts", hbar_values(ax), values)
    files = save(
        fig,
        ax,
        "stage1_reached_node_type_distribution",
        note="Counted once per cross-page neighbour link (a node reached twice counts twice)",
    )
    return {
        "source": "hub_analysis.json -> neighbour_node_types",
        "values": dict(rows),
        "total": total,
        "other_rule": f"types with share < {OTHER_MIN_SHARE:.1%} of total",
        "other_members": dict(grouped),
        "section_header_plus_title_share": round(share, 6),
        "files": files,
    }


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    hashes_before = {name: sha256(p) for name, p in SOURCES.items()}
    agg, diag, hub = load("aggregates"), load("diagnostics"), load("hub_analysis")

    figures = {
        "figure_1_multi_page_pr_vs_k": figure_1(agg),
        "figure_2_missing_gold_graph_distance": figure_2(diag),
        "figure_3_cross_page_relation_distribution": figure_3(hub),
        "figure_4_reached_node_type_distribution": figure_4(hub),
    }

    hashes_after = {name: sha256(p) for name, p in SOURCES.items()}
    if hashes_after != hashes_before:
        raise AssertionError("source JSON changed during the run")
    manifest = {
        "generated_by": "scripts/make_weekly_meeting_figures.py",
        "git_commit": git_commit(),
        "matplotlib": matplotlib.__version__,
        "sources": {
            name: {"path": str(p.relative_to(ROOT)).replace("\\", "/"), "sha256": h}
            for (name, p), h in zip(SOURCES.items(), hashes_before.values())
        },
        "figures": figures,
    }
    (OUT_DIR / "figure_data.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(manifest, indent=2))
    print("\nAll plotted values verified against source JSON; source files unchanged.")


if __name__ == "__main__":
    main()
