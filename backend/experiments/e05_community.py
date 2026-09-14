"""E05: community detection comparison on one fixed undirected projection.

Every method partitions the same nodes with the same edge weights; only the
grouping procedure differs. Metrics are computed on the uncontracted graph so the
contraction used by the thesis method cannot inflate its own scores.
"""

import random
import time
from collections import defaultdict
from copy import deepcopy

import igraph as ig

from app.causal_graph import CAUSAL_TYPES, assign_communities
from experiments.harness import snapshot, write_result


def _weight(edge: dict) -> float:
    return edge.get("semantic_weight", edge.get("structural_weight", edge.get("rpc", 0)))

def _projection(nodes: list[dict], edges: list[dict], *, semantic_only: bool = False):
    index = {n["id"]: i for i, n in enumerate(nodes)}
    weights: dict[tuple[int, int], float] = defaultdict(float)
    for edge in edges:
        a, b = index[edge["source"]], index[edge["target"]]
        if a == b:
            continue
        value = edge.get("semantic_weight", 0.0) if semantic_only else _weight(edge)
        if value > 0:
            weights[tuple(sorted((a, b)))] += value
    graph = ig.Graph(n=len(nodes), edges=list(weights), directed=False)
    return graph, list(weights.values())

def _strong(edges: list[dict], nodes: dict, threshold: float) -> list[dict]:
    return [
        e
        for e in edges
        if e.get("type") in CAUSAL_TYPES
        and e.get("status") == "active"
        and e.get("compatible", True)
        and e.get("rpc", 0) >= threshold
        and nodes[e["source"]].get("status", "active") == "active"
        and nodes[e["target"]].get("status", "active") == "active"
    ]

def _metrics(
    membership: list[int], nodes: list[dict], edges: list[dict], profile: dict, categories: dict
) -> dict:
    graph, weights = _projection(nodes, edges)
    index = {n["id"]: i for i, n in enumerate(nodes)}
    node_map = {n["id"]: n for n in nodes}
    strong = _strong(edges, node_map, profile["strong_threshold"])
    kept = sum(membership[index[e["source"]]] == membership[index[e["target"]]] for e in strong)
    groups: dict[int, list[dict]] = defaultdict(list)
    for node, cid in zip(nodes, membership, strict=True):
        groups[cid].append(node)
    labelled = purity = mixed = 0
    for members in groups.values():
        owned = [m["matter_id"] for m in members if m.get("matter_id")]
        if not owned:
            continue
        labelled += len(owned)
        purity += max(owned.count(mid) for mid in set(owned))
        mixed += len({categories.get(mid) for mid in owned}) > 1
    sizes = sorted((len(v) for v in groups.values()), reverse=True)
    return {
        "modularity": round(graph.modularity(membership, weights=weights), 4),
        "communities": len(groups),
        "largest_share": round(sizes[0] / len(nodes), 4),
        "median_size": sizes[len(sizes) // 2],
        "strong_edge_keep_rate": round(kept / max(1, len(strong)), 4),
        "strong_edges": len(strong),
        "matter_purity": round(purity / max(1, labelled), 4),
        "category_mixed_communities": mixed,
    }

def _louvain(nodes, edges, profile, seed):
    graph, weights = _projection(nodes, edges)
    ig.set_random_number_generator(random.Random(seed))
    return list(graph.community_multilevel(weights=weights).membership)

def _leiden(nodes, edges, profile, seed):
    graph, weights = _projection(nodes, edges)
    ig.set_random_number_generator(random.Random(seed))
    return list(
        graph.community_leiden(
            objective_function="modularity",
            weights=weights,
            resolution=profile["resolution"],
            n_iterations=-1,
        ).membership
    )

def _leiden_semantic(nodes, edges, profile, seed):
    graph, weights = _projection(nodes, edges, semantic_only=True)
    ig.set_random_number_generator(random.Random(seed))
    return list(
        graph.community_leiden(
            objective_function="modularity",
            weights=weights,
            resolution=profile["resolution"],
            n_iterations=-1,
        ).membership
    )

def _constrained(nodes, edges, profile, seed):
    working = deepcopy(nodes)
    communities = assign_communities(working, edges, dict(profile, seed=seed))
    top = {c["id"]: i for i, c in enumerate(c for c in communities if c["level"] == 1)}
    fallback = len(top)
    return [top.get(n.get("community_ids", [None])[0], fallback) for n in working]

METHODS = {
    "Louvain": _louvain,
    "Leiden": _leiden,
    "语义权重Leiden": _leiden_semantic,
    "约束层次社区（本文）": _constrained,
}

def run(seeds: tuple[int, ...] = (42, 7, 13, 101, 2024)) -> dict:
    built = snapshot("full")
    nodes, edges, profile = built["graph"]["nodes"], built["graph"]["edges"], built["profile"]
    hierarchy = built["graph"]["communities"]
    categories = {m["id"]: m["category"] for m in built["corpus"]["matters"]}
    results = {}
    for name, method in METHODS.items():
        started = time.perf_counter()
        membership = method(nodes, edges, profile, profile["seed"])
        seconds = time.perf_counter() - started
        runs = [method(nodes, edges, profile, seed) for seed in seeds]
        pairs = [
            ig.compare_communities(runs[i], runs[j], method="nmi")
            for i in range(len(runs))
            for j in range(i + 1, len(runs))
        ]
        results[name] = dict(
            _metrics(membership, nodes, edges, profile, categories),
            seconds=round(seconds, 3),
            seed_nmi=round(sum(pairs) / len(pairs), 4),
        )
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "seeds": list(seeds),
        "hierarchy_records": len(hierarchy),
        "unsplittable_records": sum(c["unsplittable"] for c in hierarchy),
        "levels": sorted({c["level"] for c in hierarchy}),
        "methods": results,
    }

if __name__ == "__main__":
    write_result("e05-community", run())
