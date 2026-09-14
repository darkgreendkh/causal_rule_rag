"""E10: next-action recommendation measured against the reference plan.

Every prefix of a verified plan is replayed as completed history; the reference plan's
following action is the target. Recommendations are re-checked independently so an
"executable" label that does not survive replay is counted as a violation.
"""

import time

import numpy as np

from app.workflow import check_workflow, next_steps
from experiments.harness import corpus, embed_queries, reference_cases, write_result


def _rank_catalogue(candidates, _question, _vectors):
    """Current production behaviour: matter action order, no scoring."""
    return [c["action_id"] for c in candidates]


def _rank_alphabetical(candidates, _question, _vectors):
    return sorted(c["action_id"] for c in candidates)


def _rank_semantic(candidates, question, vectors):
    query = vectors[question]
    return [
        c["action_id"]
        for c in sorted(
            candidates, key=lambda c: -float(np.dot(query, vectors[c["label"]]))
        )
    ]


METHODS = {
    "事项目录顺序（当前实现）": _rank_catalogue,
    "字典序": _rank_alphabetical,
    "语义相似度排序": _rank_semantic,
}


def run() -> dict:
    source = corpus()
    cases, _ = reference_cases()
    matters = {m["id"]: m for m in source["matters"]}
    samples = []
    for case in cases:
        for k in range(1, len(case["steps"])):
            samples.append(
                {
                    "case": case,
                    "prefix": case["steps"][:k],
                    "gold": case["steps"][k],
                    "question": matters[case["matter_id"]]["name"],
                }
            )
    labels = {a["id"]: a["label"] for a in source["actions"]}
    texts = sorted({s["question"] for s in samples} | set(labels.values()))
    vectors = embed_queries(texts)

    prepared = []
    violations = 0
    for sample in samples:
        case = sample["case"]
        request = dict(case, steps=[], completed_steps=sample["prefix"], goal=None)
        options = next_steps(source, request)
        ready = [c for c in options["candidates"] if c["status"] == "satisfied"]
        for candidate in ready:
            recheck = check_workflow(
                source, dict(request, steps=[candidate["action_id"]], goal=None)
            )
            violations += recheck["status"] != "satisfied"
        prepared.append((sample, ready))

    methods = {}
    for name, rank in METHODS.items():
        hit1 = hit3 = rr = 0.0
        seconds = 0.0
        for sample, ready in prepared:
            started = time.perf_counter()
            ordered = rank(ready, sample["question"], vectors)
            seconds += time.perf_counter() - started
            if sample["gold"] in ordered:
                position = ordered.index(sample["gold"]) + 1
                hit1 += position == 1
                hit3 += position <= 3
                rr += 1 / position
        methods[name] = {
            "Top-1命中率": round(hit1 / max(1, len(prepared)), 4),
            "Top-3命中率": round(hit3 / max(1, len(prepared)), 4),
            "MRR": round(rr / max(1, len(prepared)), 4),
            "平均排序耗时毫秒": round(seconds * 1000 / max(1, len(prepared)), 4),
        }
    sizes = [len(ready) for _, ready in prepared]
    return {
        "samples": len(prepared),
        "cases": len(cases),
        "mean_candidate_count": round(sum(sizes) / max(1, len(sizes)), 2),
        "gold_in_candidates_rate": round(
            sum(s["gold"] in [c["action_id"] for c in ready] for s, ready in prepared)
            / max(1, len(prepared)),
            4,
        ),
        "violating_recommendations": violations,
        "methods": methods,
    }


if __name__ == "__main__":
    write_result("e10-next", run())
