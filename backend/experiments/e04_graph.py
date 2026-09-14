"""E04: structural effect of removing one construction component at a time.

Only the five profiles that actually change `build_graph` are rebuilt here; the
retrieval-side switches are exercised in E07 instead of being renamed as ablations.
"""

from collections import Counter

from experiments.harness import snapshot, write_result

BUILD_PROFILES = ("full", "without_rpc", "without_scs", "without_macro", "without_micro")


def _measure(profile_name: str) -> dict:
    built = snapshot(profile_name)
    graph, corpus = built["graph"], built["corpus"]
    nodes, edges = graph["nodes"], graph["edges"]
    degree = Counter()
    for edge in edges:
        degree[edge["source"]] += 1
        degree[edge["target"]] += 1
    layers = Counter(n["layer"] for n in nodes)
    types = Counter(e["type"] for e in edges)
    active_rules = {r["id"] for r in corpus["rules"] if r["status"] == "active"}
    reachable = {
        n["matter_id"]
        for n in nodes
        if n["matter_id"] and n["type"] in ("CONDITION", "ACTION", "RULE")
    }
    return {
        "nodes": len(nodes),
        "edges": len(edges),
        "macro_nodes": layers["macro"],
        "micro_nodes": layers["micro"],
        "cross_layer_edges": types["REALIZES"],
        "isolated_node_rate": round(sum(n["id"] not in degree for n in nodes) / len(nodes), 4),
        "mean_rpc": round(sum(e.get("rpc", 0) for e in edges) / max(1, len(edges)), 4),
        "incompatible_edge_rate": round(
            sum(not e.get("compatible", True) for e in edges) / max(1, len(edges)), 4
        ),
        "candidate_edge_rate": round(
            sum(e.get("status") != "active" for e in edges) / max(1, len(edges)), 4
        ),
        "communities": len(graph["communities"]),
        "executable_matters": len(reachable),
        "active_rules": len(active_rules),
        "build_seconds": round(built["build_seconds"], 2),
    }


def _thresholds() -> dict:
    """Does either screening threshold actually reject anything on this corpus?"""
    built = snapshot("full")
    edges, profile = built["graph"]["edges"], built["profile"]
    causal = [e for e in edges if e["type"] in ("REQUIRES", "PRODUCES", "PRECEDES", "EXCEPTS")]
    cross = [e for e in edges if e["type"] == "REALIZES"]
    return {
        "rpc_threshold": profile["rpc_threshold"],
        "scs_threshold": profile["scs_threshold"],
        "causal_edges": len(causal),
        "causal_rpc_below_threshold": sum(
            e.get("rpc", 0) < profile["rpc_threshold"] for e in causal
        ),
        "distinct_rpc_values": sorted({round(e.get("rpc", 0), 4) for e in causal}),
        "cross_layer_edges": len(cross),
        "cross_scs_below_threshold": sum(
            e.get("scs", 0) < profile["scs_threshold"] for e in cross
        ),
        "min_cross_scs": round(min((e.get("scs", 0) for e in cross), default=0.0), 4),
    }


def run() -> dict:
    return {
        "profiles": {name: _measure(name) for name in BUILD_PROFILES},
        "threshold_binding": _thresholds(),
    }


if __name__ == "__main__":
    write_result("e04-graph", run())
