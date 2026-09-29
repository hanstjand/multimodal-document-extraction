"""retrieval-eval-v1 conditions, page rankings and graph diagnostics (CP-4.5A; D-021, frozen protocol).

Ranking functions never receive gold pages. Conditions (RETRIEVAL_EVAL_V1.md §3–4, [RECONSTRUCTED]):

- A  semantic-only: distinct pages in order of first appearance in the full node ranking;
- B  seeds (top ``m`` nodes, semantic order): per seed its page, then the pages of its one-hop
     neighbours over all edges in (page, node ID) order; then A's remaining pages;
- C  as B with intra-page edges only (must equal A at page level);
- D  as B with neighbours p − 1, p + 1 of the seed page (within 1..num_pages; no graph);
truncated at k distinct pages. Unbudgeted sets: A = seed pages; B = A ∪ cross-page neighbour pages;
D = A ∪ {p ± 1}.
"""

import random
import statistics
from collections import deque
from collections.abc import Callable, Iterable, Sequence
from typing import Any

from multimodal_document_extraction.studies.ladrag.graph_retrieval import (
    SCOPE_ALL,
    SCOPE_CROSS_PAGE,
    SCOPE_INTRA_PAGE,
    GraphIndex,
)

CONDITIONS = ("A", "B", "C", "D")


def distinct(pages: Iterable[int]) -> list[int]:
    return list(dict.fromkeys(pages))


def semantic_pages(index: GraphIndex, ranked_nodes: Sequence[str]) -> list[int]:
    """A: distinct pages in order of first appearance in the node ranking."""
    return distinct(index.node_page(n) for n in ranked_nodes)


def adjacent_pages(page: int, num_pages: int) -> list[int]:
    """D neighbours of a seed page: p − 1, then p + 1, within 1..num_pages."""
    return [p for p in (page - 1, page + 1) if 1 <= p <= num_pages]


def condition_pages(
    condition: str,
    index: GraphIndex,
    ranked_nodes: Sequence[str],
    num_pages: int,
    m: int = 10,
) -> list[int]:
    """Full (untruncated) distinct page ranking of a condition; depends only on the node ranking."""
    base = semantic_pages(index, ranked_nodes)
    if condition == "A":
        return base
    seeds = list(ranked_nodes[:m])
    if condition in ("B", "C"):
        scope = SCOPE_ALL if condition == "B" else SCOPE_INTRA_PAGE
        head = [item.page for item in index.ordered_one_hop_expansion(seeds, scope=scope)]
    elif condition == "D":
        head = []
        for seed in seeds:
            page = index.node_page(seed)
            head += [page, *adjacent_pages(page, num_pages)]
    else:
        raise ValueError(f"unknown condition {condition!r}")
    return distinct([*head, *base])


def truncate(pages: Sequence[int], k: int) -> list[int]:
    return list(pages[:k])


def unbudgeted_sets(
    index: GraphIndex, ranked_nodes: Sequence[str], num_pages: int, m: int = 10
) -> dict[str, list[int]]:
    """Secondary view: A = seed pages; B = + cross-page neighbour pages; C = + intra-page (= A);
    D = + p ± 1. Pages in emission order."""
    seeds = list(ranked_nodes[:m])
    seed_pages = distinct(index.node_page(s) for s in seeds)
    cross = [i.page for i in index.ordered_one_hop_expansion(seeds, scope=SCOPE_CROSS_PAGE)]
    intra = [i.page for i in index.ordered_one_hop_expansion(seeds, scope=SCOPE_INTRA_PAGE)]
    adjacent = [p for s in seed_pages for p in adjacent_pages(s, num_pages)]
    return {
        "A": seed_pages,
        "B": distinct([*seed_pages, *cross]),
        "C": distinct([*seed_pages, *intra]),
        "D": distinct([*seed_pages, *adjacent]),
    }


# --- metrics (D-008 / D-009) ---------------------------------------------------------------------


def perfect_recall(gold: Iterable[int], retrieved: Iterable[int]) -> float | None:
    gold = set(gold)
    return None if not gold else float(gold <= set(retrieved))


def irrelevant_pages_ratio(gold: Iterable[int], retrieved: Iterable[int]) -> float:
    retrieved = set(retrieved)
    return 0.0 if not retrieved else len(retrieved - set(gold)) / len(retrieved)


# --- reachability diagnostic (uses gold; never feeds back into rankings) --------------------------


def seed_distances(index: GraphIndex, seeds: Sequence[str]) -> dict[str, int]:
    """Shortest undirected hop distance (all edges) from the nearest seed node to every node."""
    distance = {s: 0 for s in seeds}
    queue = deque(seeds)
    while queue:
        node = queue.popleft()
        for n in index.neighbors(node, SCOPE_ALL):
            if n.node_id not in distance:
                distance[n.node_id] = distance[node] + 1
                queue.append(n.node_id)
    return distance


def reachability(
    index: GraphIndex,
    ranked_nodes: Sequence[str],
    gold: Sequence[int],
    num_pages: int,
    m: int,
) -> dict[str, Any]:
    """Frozen diagnostic (RETRIEVAL_EVAL_V1.md §6) for one evidence question.

    S = seed pages, N = one-hop cross-page neighbour pages not in S, A = p ± 1 of seed pages not in S.
    ``primary_class`` is exclusive with precedence: semantic_already_complete →
    expansion_completes → expansion_adds_some_missing_gold → no_expansion_possible →
    expansion_adds_only_irrelevant; ``gold_unreachable`` is a separate flag (G ⊄ S ∪ N).
    """
    seeds = list(ranked_nodes[:m])
    sets = unbudgeted_sets(index, ranked_nodes, num_pages, m)
    s_pages = set(sets["A"])
    n_pages = set(sets["B"]) - s_pages
    adj_pages = set(sets["D"]) - s_pages
    g = set(gold)
    missing = sorted(g - s_pages)
    added_gold = sorted(n_pages & g)
    if not missing:
        primary = "semantic_already_complete"
    elif added_gold and g <= s_pages | n_pages:
        primary = "expansion_completes"
    elif added_gold:
        primary = "expansion_adds_some_missing_gold"
    elif not n_pages:
        primary = "no_expansion_possible"
    else:
        primary = "expansion_adds_only_irrelevant"
    pages_with_nodes = set(index.pages_of(index.nodes_in_order()))
    distances = seed_distances(index, seeds)
    missing_detail = []
    for page in missing:
        on_page = [n for n in index.nodes_in_order() if index.node_page(n) == page]
        reached = [distances[n] for n in on_page if n in distances]
        d = min(reached) if reached else None
        missing_detail.append(
            {
                "page": page,
                "nodes_on_page": len(on_page),
                "graph_distance": "unreachable" if d is None else (str(d) if d < 3 else "3+"),
                "recovered_by_graph": page in n_pages,
                "is_seed_page_pm1": page in adj_pages,
            }
        )
    return {
        "m": m,
        "seed_pages": sorted(s_pages),
        "graph_neighbour_pages": sorted(n_pages),
        "adjacent_pages": sorted(adj_pages),
        "missing_gold_before": missing,
        "gold_added_by_graph": added_gold,
        "irrelevant_added_by_graph": sorted(n_pages - g),
        "gold_added_by_adjacent": sorted(adj_pages & g),
        "graph_completes": bool(missing) and g <= s_pages | n_pages,
        "adjacent_completes": bool(missing) and g <= s_pages | adj_pages,
        "gold_unreachable": not g <= s_pages | n_pages,
        "primary_class": primary,
        "missing_gold_detail": missing_detail,
        "gold_pages_without_nodes": sorted(g - pages_with_nodes),
    }


# --- exploratory paired statistics (D-017 procedure) ----------------------------------------------


def percentile_bootstrap(
    values: Sequence[float], n: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    means = sorted(statistics.mean(rng.choices(values, k=len(values))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def cluster_bootstrap(
    groups: dict[str, list[float]], n: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    """Whole-document bootstrap: resample documents with replacement, pool their questions."""
    rng = random.Random(seed)
    keys = sorted(groups)
    means = []
    for _ in range(n):
        pooled = [v for key in rng.choices(keys, k=len(keys)) for v in groups[key]]
        means.append(statistics.mean(pooled))
    means.sort()
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def paired_comparison(
    rows: Sequence[dict[str, Any]],
    metric: str,
    first: str,
    second: str,
    k: int,
    better: Callable[[float, float], bool],
    n: int = 10_000,
    seed: int = 0,
) -> dict[str, Any]:
    """Mean difference first − second of ``metric`` at ``k``; win = ``better(first, second)``."""
    diffs, by_doc = [], {}
    wins = ties = losses = 0
    win_ids, loss_ids = [], []
    for row in rows:
        a = row["metrics"][first][str(k)][metric]
        b = row["metrics"][second][str(k)][metric]
        diffs.append(a - b)
        by_doc.setdefault(row["doc_id"], []).append(a - b)
        if a == b:
            ties += 1
        elif better(a, b):
            wins += 1
            win_ids.append(row["question_id"])
        else:
            losses += 1
            loss_ids.append(row["question_id"])
    if not diffs:
        return {"n": 0}
    return {
        "n": len(diffs),
        "mean_difference": statistics.mean(diffs),
        "question_bootstrap_95": percentile_bootstrap(diffs, n, seed),
        "document_bootstrap_95_sensitivity": cluster_bootstrap(by_doc, n, seed),
        "wins": wins,
        "ties": ties,
        "losses": losses,
        "win_question_ids": win_ids,
        "loss_question_ids": loss_ids,
    }
