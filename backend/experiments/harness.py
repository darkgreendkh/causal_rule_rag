"""Offline rebuild of research snapshots plus reference cases for the E04-E10 runs.

Uses the cached BGE-M3 vectors written by ResearchService, so the experiments need
neither Neo4j nor the LLM endpoint. Nothing here writes into the live knowledge base.
"""

import hashlib
import json
import time
from functools import lru_cache
from pathlib import Path

import numpy as np

from app.causal_graph import build_graph
from app.corpus import build_corpus
from app.research_profiles import get_profile
from app.workflow import check_workflow

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
CACHE_DIR = ROOT / ".runtime" / "research"
RESULT_DIR = ROOT / "docs" / "thesis" / "experiments"
EMBEDDING_MODEL = "BAAI/bge-m3"
# Fixed so repeated runs stay comparable; rules without a start date use this date.
AS_OF_FALLBACK = "2026-01-01"


@lru_cache(maxsize=1)
def corpus() -> dict:
    return build_corpus(DATA_DIR)


@lru_cache(maxsize=1)
def vectors() -> dict:
    """Reuse the build cache; a missing key means the snapshot was never built here."""
    cache = json.loads((CACHE_DIR / "embeddings.json").read_text("utf-8"))
    source = corpus()
    texts = {u["id"]: u["title"] + " " + u["text"] for u in source["units"]}
    texts.update(
        {
            r["id"]: r["label"] + " " + " ".join(e["quote"] for e in r["evidence"])
            for r in source["rules"]
            if r["status"] in ("active", "candidate")
        }
    )
    missing, result = [], {}
    for key, text in texts.items():
        digest = hashlib.sha256((EMBEDDING_MODEL + "\n" + text).encode()).hexdigest()
        if digest in cache:
            result[key] = np.asarray(cache[digest], dtype=np.float32)
        else:
            missing.append(key)
    if missing:
        raise RuntimeError(f"缺少{len(missing)}个向量缓存，请先在概览页完成一次完整构建")
    return result


def embed_queries(texts: list[str]) -> dict[str, np.ndarray]:
    """Encode evaluation questions with the same BGE-M3 model, cached across runs."""
    path = CACHE_DIR / "query-embeddings.json"
    cache = json.loads(path.read_text("utf-8")) if path.exists() else {}
    keys = {
        text: hashlib.sha256((EMBEDDING_MODEL + "\n" + text).encode()).hexdigest() for text in texts
    }
    missing = [text for text, key in keys.items() if key not in cache]
    if missing:
        from sentence_transformers import SentenceTransformer

        from app.embedding import SentenceTransformerEmbedder

        # CPU keeps the experiment runnable while the backend holds the GPU copy.
        embedder = SentenceTransformerEmbedder(
            EMBEDDING_MODEL, SentenceTransformer(EMBEDDING_MODEL, device="cpu")
        )
        for start in range(0, len(missing), 16):
            batch = missing[start : start + 16]
            cache.update(zip((keys[t] for t in batch), embedder.embed(batch), strict=True))
        path.write_text(json.dumps(cache), encoding="utf-8")
    return {text: np.asarray(cache[key], dtype=np.float32) for text, key in keys.items()}


@lru_cache(maxsize=16)
def snapshot(profile_name: str = "full") -> dict:
    profile = get_profile(profile_name)
    source = corpus()
    vecs = vectors()
    similarities = {
        (e["unit_id"], r["id"]): max(0.0, float(np.dot(vecs[e["unit_id"]], vecs[r["id"]])))
        for r in source["rules"]
        if r["status"] in ("active", "candidate")
        for e in r["evidence"]
        if e["unit_id"] in vecs
    }
    started = time.perf_counter()
    graph = build_graph(json.loads(json.dumps(source)), profile, similarities)
    seconds = time.perf_counter() - started
    return {"corpus": source, "graph": graph, "profile": profile, "build_seconds": seconds}


# --- reference workflow cases -------------------------------------------------


def _fields(matter: dict) -> dict:
    return {f["id"]: f for f in matter["fields"]}


def _assign(facts: dict, fields: dict, key: str, value) -> None:
    field = fields.get(key)
    if field is None or field["role"] == "policy":
        return
    facts[key] = value


def _witness(expression: dict, facts: dict, fields: dict, want: bool = True) -> None:
    """Propose field values that make an expression true; the engine verifies afterwards."""
    if not isinstance(expression, dict):
        return
    if "not" in expression:
        return _witness(expression["not"], facts, fields, not want)
    for key in ("all", "any"):
        if key in expression:
            children = expression[key]
            decisive = key == "any"
            targets = children if want is not decisive else children[:1]
            for child in targets:
                _witness(child, facts, fields, want)
            return
    if set(expression) == {"field"}:
        return _assign(facts, fields, expression["field"], want)
    if "op" not in expression or "left" not in expression:
        return
    left, right, op = expression["left"], expression["right"], expression["op"]
    if op == "contains" and isinstance(left, dict) and "field" in left and "value" in right:
        key = left["field"]
        if want and fields.get(key, {}).get("type") == "set":
            _assign(facts, fields, key, sorted({*facts.get(key, []), right["value"]}))
        return
    if op == "in" and isinstance(left, dict) and "field" in left and "value" in right:
        options = right["value"]
        if want and isinstance(options, list) and options:
            _assign(facts, fields, left["field"], options[0])
        return
    field_node, value_node, flip = left, right, False
    if "field" not in field_node and isinstance(right, dict) and "field" in right:
        field_node, value_node, flip = right, left, True
    if "field" not in field_node or "value" not in value_node:
        return
    key, value = field_node["field"], value_node["value"]
    kind = fields.get(key, {}).get("type")
    order = {"gt": "gt", "gte": "gte", "lt": "lt", "lte": "lte"}
    if flip:
        order = {"gt": "lt", "gte": "lte", "lt": "gt", "lte": "gte"}
    effective = order.get(op, op)
    if not want:
        effective = {
            "eq": "ne",
            "ne": "eq",
            "gt": "lte",
            "gte": "lt",
            "lt": "gte",
            "lte": "gt",
        }.get(effective, effective)
    if effective == "eq":
        _assign(facts, fields, key, value)
    elif effective == "ne":
        if isinstance(value, bool):
            _assign(facts, fields, key, not value)
        elif kind == "number":
            _assign(facts, fields, key, value + 1)
        elif kind in ("string", "text", "enum"):
            options = [o for o in fields.get(key, {}).get("options", []) if o != value]
            if options:
                _assign(facts, fields, key, options[0])
    elif kind == "number" and effective in ("gt", "gte", "lt", "lte"):
        step = {"gt": 1, "gte": 0, "lt": -1, "lte": 0}[effective]
        current = facts.get(key)
        proposed = value + step
        bound = max if effective in ("gt", "gte") else min
        _assign(facts, fields, key, proposed if current is None else bound(current, proposed))
    elif kind == "date" and effective in ("gt", "gte", "lt", "lte") and isinstance(value, str):
        _assign(facts, fields, key, value)


def _completed_refs(expression: dict) -> set[str]:
    found = set()
    stack = [expression]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            if isinstance(node.get("completed"), str):
                found.add(node["completed"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return found


def _plan_order(matter: dict, actions: dict, rules: list[dict]) -> list[str]:
    ids = [aid for aid in matter["action_ids"] if aid in actions]
    needs = {aid: set() for aid in ids}
    for aid in ids:
        needs[aid] |= _completed_refs(actions[aid].get("preconditions", {})) & set(ids)
    for rule in rules:
        if rule.get("action_id") in needs and rule["status"] == "active":
            needs[rule["action_id"]] |= _completed_refs(rule["condition"]) & set(ids)
    ordered, remaining = [], list(ids)
    while remaining:
        ready = [aid for aid in remaining if needs[aid] <= set(ordered)]
        if not ready:  # a cycle means the catalogue order is the only available guess
            ordered.extend(remaining)
            break
        ordered.extend(ready)
        remaining = [aid for aid in remaining if aid not in ready]
    return ordered


def _context(matter: dict, rules: list[dict]) -> tuple[str, str]:
    scopes = [r["scope"] for r in rules if r["status"] == "active" and r.get("scope")]
    regions = {s.get("region") for s in scopes if s.get("region")} or {"全国"}
    region = "武汉" if regions - {"全国"} else "全国"
    starts = [s["valid_from"] for s in scopes if s.get("valid_from")]
    ends = [s["valid_to"] for s in scopes if s.get("valid_to")]
    as_of = max(starts) if starts else AS_OF_FALLBACK
    if ends and as_of > min(ends):
        as_of = min(ends)
    return region, as_of


@lru_cache(maxsize=1)
def reference_cases() -> tuple[tuple[dict, ...], tuple[dict, ...]]:
    """Valid (facts, plan) pairs verified by the checker; unsolved matters are reported."""
    source = corpus()
    actions = {a["id"]: a for a in source["actions"]}
    cases, unsolved = [], []
    for matter in source["matters"]:
        if len(matter["action_ids"]) < 2:
            continue
        rules = [r for r in source["rules"] if r["matter_id"] == matter["id"]]
        fields = _fields(matter)
        plan = _plan_order(matter, actions, rules)
        region, as_of = _context(matter, rules)
        facts: dict = {}
        for _ in range(3):
            for rule in rules:
                if rule["status"] == "active":
                    _witness(rule["condition"], facts, fields)
            for aid in plan:
                _witness(actions[aid].get("preconditions", {}), facts, fields)
                if actions[aid]["kind"] == "external":
                    for key, value in actions[aid].get("effects", {}).items():
                        if fields.get(key, {}).get("role") == "external":
                            facts[key] = value
        goal = matter["goals"][-1]["id"] if matter.get("goals") else None
        request = {
            "matter_id": matter["id"],
            "region": region,
            "as_of": as_of,
            "facts": facts,
            "steps": plan,
            "completed_steps": [],
            "goal": goal,
        }
        checked = check_workflow(source, request)
        if checked["status"] == "satisfied" and checked.get("goal_satisfied"):
            cases.append(dict(request, category=matter["category"], matter_name=matter["name"]))
        else:
            unsolved.append(
                {
                    "matter_id": matter["id"],
                    "status": checked["status"],
                    "reason": (checked.get("first_error") or {}).get("message", ""),
                }
            )
    return tuple(cases), tuple(unsolved)


def reference_report() -> dict:
    multi = [m for m in corpus()["matters"] if len(m["action_ids"]) >= 2]
    cases, unsolved = reference_cases()
    return {
        "multi_action_matters": len(multi),
        "solved": len(cases),
        "solved_ratio": round(len(cases) / max(1, len(multi)), 4),
        "unsolved_status": {
            status: sum(u["status"] == status for u in unsolved)
            for status in sorted({u["status"] for u in unsolved})
        },
    }


def write_result(name: str, payload: dict) -> Path:
    RESULT_DIR.mkdir(parents=True, exist_ok=True)
    path = RESULT_DIR / f"{name}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path
