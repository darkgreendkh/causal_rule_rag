"""E11: knowledge-update consistency when a source document leaves the library.

Runs on an in-memory copy of the corpus, never on the live knowledge base. The hard
check is residual staleness: no rule, action or edge may survive while citing a unit
that has been removed.
"""

import json
import time

from app.causal_graph import build_graph
from app.research import ResearchService
from app.research_profiles import get_profile
from experiments.harness import corpus, snapshot, vectors, write_result


def _residual(corpus_after: dict, graph_after: dict, removed_units: set[str]) -> dict:
    return {
        "rules": sum(
            any(e["unit_id"] in removed_units for e in r["evidence"]) for r in corpus_after["rules"]
        ),
        "actions": sum(
            any(e["unit_id"] in removed_units for e in a["evidence"])
            for a in corpus_after["actions"]
        ),
        "edges": sum(
            any(e.get("unit_id") in removed_units for e in edge.get("evidence", []))
            or edge.get("source_chunk_id") in removed_units
            for edge in graph_after["edges"]
        ),
        "nodes": sum(
            any(uid in removed_units for uid in node["source_chunk_ids"])
            for node in graph_after["nodes"]
        ),
    }


def run(sample: int = 6) -> dict:
    base = corpus()
    built = snapshot("full")
    profile = get_profile("full")
    vecs = vectors()
    counts = {
        d["id"]: sum(u["document_id"] == d["id"] for u in base["units"]) for d in base["documents"]
    }
    targets = sorted(base["documents"], key=lambda d: -counts[d["id"]])[:sample]
    scenarios = []
    for document in targets:
        working = json.loads(json.dumps(base))
        removed_units = {u["id"] for u in working["units"] if u["document_id"] == document["id"]}
        after = ResearchService._without_documents(working, {document["id"]})
        similarities = {
            (e["unit_id"], r["id"]): max(0.0, float(vecs[e["unit_id"]] @ vecs[r["id"]]))
            for r in after["rules"]
            if r["status"] in ("active", "candidate")
            for e in r["evidence"]
            if e["unit_id"] in vecs
        }
        started = time.perf_counter()
        graph_after = build_graph(after, profile, similarities)
        seconds = time.perf_counter() - started
        degraded = sum(
            not m["capabilities"]["checkable"]
            for m in after["matters"]
            if any(
                original["id"] == m["id"] and original["capabilities"]["checkable"]
                for original in base["matters"]
            )
        )
        scenarios.append(
            {
                "document": document["source_path"],
                "removed_units": len(removed_units),
                "rules_after": len(after["rules"]),
                "rules_removed": len(base["rules"]) - len(after["rules"]),
                "matters_after": len(after["matters"]),
                "matters_no_longer_checkable": degraded,
                "edges_after": len(graph_after["edges"]),
                "edges_removed": len(built["graph"]["edges"]) - len(graph_after["edges"]),
                "residual_stale": _residual(after, graph_after, removed_units),
                "rebuild_seconds": round(seconds, 2),
            }
        )
    return {
        "baseline_units": len(base["units"]),
        "baseline_rules": len(base["rules"]),
        "baseline_edges": len(built["graph"]["edges"]),
        "scenarios": scenarios,
        "total_residual_stale": sum(
            value for s in scenarios for value in s["residual_stale"].values()
        ),
    }


if __name__ == "__main__":
    write_result("e11-update", run())
