"""E09: first-error localisation and plan repair on statically generated defects.

Defects are injected into checker-verified reference plans, so both the expected
first-error position and an upper bound on the optimal repair cost are known before
any method runs. That bound is what the methods are scored against.
"""

import time
from copy import deepcopy

from app.workflow import check_workflow, next_steps, repair_workflow
from experiments.harness import _completed_refs, corpus, reference_cases, write_result


def _dependents(source: dict, case: dict) -> dict[str, set[str]]:
    """Static `completed` references only; no rule evaluation is involved."""
    actions = {a["id"]: a for a in source["actions"]}
    rules = [r for r in source["rules"] if r["matter_id"] == case["matter_id"]]
    needs = {}
    for aid in case["steps"]:
        refs = _completed_refs(actions[aid].get("preconditions", {}))
        for rule in rules:
            if rule.get("action_id") == aid and rule["status"] == "active":
                refs |= _completed_refs(rule["condition"])
        needs[aid] = refs & set(case["steps"])
    return needs


def defects(source: dict, case: dict) -> list[dict]:
    steps, needs = case["steps"], _dependents(source, case)
    found = []
    for i, action_id in enumerate(steps):
        later = [j for j in range(i + 1, len(steps)) if action_id in needs[steps[j]]]
        if not later:
            continue
        mutated = steps[:i] + steps[i + 1 :]
        found.append(
            {
                "kind": "delete",
                "steps": mutated,
                "expected_index": later[0] - 1,
                "cost_bound": 1,
            }
        )
        if later[0] == i + 1:
            found.append(
                {
                    "kind": "swap",
                    "steps": steps[:i] + [steps[i + 1], action_id] + steps[i + 2 :],
                    "expected_index": i,
                    "cost_bound": 2,
                }
            )
        found.append(
            {
                "kind": "premature",
                "steps": steps[:i] + [steps[later[0]]] + steps[i:],
                "expected_index": i,
                "cost_bound": 1,
            }
        )
    return found


def fact_defects(source: dict, case: dict) -> list[dict]:
    """Removing a required applicant fact cannot be repaired by editing steps."""
    matter = next(m for m in source["matters"] if m["id"] == case["matter_id"])
    roles = {f["id"]: f for f in matter["fields"]}
    found = []
    for key in case["facts"]:
        if roles.get(key, {}).get("role") != "applicant" or roles[key].get("mutable"):
            continue
        facts = {k: v for k, v in case["facts"].items() if k != key}
        if check_workflow(source, dict(case, facts=facts))["status"] != "unknown":
            continue
        found.append({"kind": "missing_fact", "facts": facts, "dropped_field": key})
        break
    return found


def _levenshtein(left: list[str], right: list[str]) -> int:
    previous = list(range(len(right) + 1))
    for i, a in enumerate(left, 1):
        current = [i]
        for j, b in enumerate(right, 1):
            current.append(
                min(previous[j] + 1, current[j - 1] + 1, previous[j - 1] + (a != b))
            )
        previous = current
    return previous[-1]


def _extend(source: dict, request: dict, steps: list[str], limit: int = 20) -> list[str] | None:
    """Append any currently executable action until the goal holds or nothing is ready."""
    steps = list(steps)
    for _ in range(limit):
        if check_workflow(source, dict(request, steps=steps))["status"] == "satisfied":
            return steps
        options = next_steps(source, dict(request, steps=steps, goal=None))
        ready = sorted(
            c["action_id"]
            for c in options["candidates"]
            if c["status"] == "satisfied" and c["action_id"] not in steps
        )
        if not ready:
            return None
        steps.append(ready[0])
    return None


def _truncate_and_extend(source: dict, request: dict) -> dict:
    """Baseline: cut the plan at the first reported error, then greedily complete it."""
    first = check_workflow(source, request).get("first_error") or {}
    index = first.get("index")
    prefix = request["steps"][: index if isinstance(index, int) and index >= 0 else 0]
    return {"steps": _extend(source, request, prefix)}


def _replan(source: dict, request: dict) -> dict:
    """Baseline: discard the submitted order and greedily build any reaching plan."""
    return {"steps": _extend(source, request, [])}


def _constrained(source: dict, request: dict) -> dict:
    result = repair_workflow(source, deepcopy(request))
    return {
        "steps": result["steps"] if result["status"] in ("repaired", "already_valid") else None,
        "declared_cost": result["cost"],
        "explored": result["explored_states"],
        "truncated": result["truncated"],
    }


METHODS = {
    "仅规则检查": lambda source, request: {"steps": None},
    "截断后贪心补全": _truncate_and_extend,
    "重新规划（最短路径类比）": _replan,
    "受约束序列修复": _constrained,
}


def run() -> dict:
    source = corpus()
    cases, unsolved = reference_cases()
    samples, fact_samples = [], []
    for case in cases:
        for defect in defects(source, case):
            samples.append((case, defect))
        for defect in fact_defects(source, case):
            fact_samples.append((case, defect))

    localisation = {"total": 0, "exact": 0, "detected": 0, "by_kind": {}}
    for case, defect in samples:
        checked = check_workflow(source, dict(case, steps=defect["steps"]))
        first = checked.get("first_error") or {}
        hit = checked["status"] != "satisfied"
        exact = hit and first.get("index") == defect["expected_index"]
        localisation["total"] += 1
        localisation["detected"] += hit
        localisation["exact"] += exact
        kind = localisation["by_kind"].setdefault(
            defect["kind"], {"total": 0, "detected": 0, "exact": 0}
        )
        kind["total"] += 1
        kind["detected"] += hit
        kind["exact"] += exact

    methods = {}
    for name, method in METHODS.items():
        legal = bound_ok = explored = truncated = 0
        costs, seconds = [], 0.0
        by_kind: dict[str, list[int]] = {}
        for case, defect in samples:
            request = dict(case, steps=defect["steps"])
            started = time.perf_counter()
            result = method(source, request)
            seconds += time.perf_counter() - started
            explored += result.get("explored", 0)
            truncated += bool(result.get("truncated"))
            if result["steps"] is None:
                continue
            recheck = check_workflow(source, dict(request, steps=result["steps"]))
            if recheck["status"] != "satisfied":
                continue
            # One uniform measure for every method: unit edit distance from the submitted plan.
            cost = _levenshtein(defect["steps"], result["steps"])
            legal += 1
            costs.append(cost)
            by_kind.setdefault(defect["kind"], []).append(cost)
            bound_ok += cost <= defect["cost_bound"]
        alternative = fabricated = 0
        for case, defect in fact_samples:
            request = dict(case, facts=defect["facts"])
            result = method(source, request)
            if result["steps"] is None:
                continue
            recheck = check_workflow(source, dict(request, steps=result["steps"]))
            alternative += recheck["status"] == "satisfied"
            fabricated += recheck["status"] != "satisfied"
        methods[name] = {
            "legal_repair_rate": round(legal / max(1, len(samples)), 4),
            "within_injected_bound_rate": round(bound_ok / max(1, len(samples)), 4),
            "mean_edit_cost": round(sum(costs) / len(costs), 3) if costs else None,
            "mean_edit_cost_by_kind": {
                kind: round(sum(values) / len(values), 3) for kind, values in sorted(by_kind.items())
            },
            "mean_explored_states": round(explored / max(1, len(samples)), 1),
            "truncated_rate": round(truncated / max(1, len(samples)), 4),
            "mean_seconds": round(seconds / max(1, len(samples)), 4),
            "missing_fact_alternative_plan": alternative,
            "missing_fact_fabricated_plan": fabricated,
        }

    return {
        "reference_cases": len(cases),
        "unsolved_matters": len(unsolved),
        "step_defects": len(samples),
        "fact_defects": len(fact_samples),
        "defect_kinds": {
            kind: sum(d["kind"] == kind for _, d in samples)
            for kind in sorted({d["kind"] for _, d in samples})
        },
        "localisation": localisation,
        "methods": methods,
    }


if __name__ == "__main__":
    write_result("e09-repair", run())
