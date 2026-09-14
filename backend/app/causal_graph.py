"""Source-grounded dual-layer graph and bounded directed evidence search."""

import hashlib
import json
import math
import random
from collections import defaultdict
from datetime import date

import igraph as ig

from app.rule_engine import evaluate, validate_expression

CAUSAL_TYPES = {"REQUIRES", "PRODUCES", "PRECEDES", "EXCEPTS"}


def rpc_score(coverage: float, continuity: float, temporal: float) -> float:
    return sum(max(0.0, min(1.0, x)) for x in (coverage, continuity, temporal)) / 3


def scs_score(
    semantic: float, support: float, compatible_type: float, *, compatible: bool = True
) -> float:
    if not compatible:
        return 0.0
    return sum(
        w * max(0.0, min(1.0, x))
        for w, x in zip((0.5, 0.3, 0.2), (semantic, support, compatible_type), strict=True)
    )


def _id(*parts: str) -> str:
    return hashlib.sha256("|".join(parts).encode()).hexdigest()[:20]


def _leaves(expression: dict) -> list[dict]:
    if not isinstance(expression, dict):
        return []
    if "all" in expression:
        return [leaf for child in expression["all"] for leaf in _leaves(child)]
    # An OR or NOT is a single logical unit; drawing all children as AND is incorrect.
    return [expression]


def _expression_label(expression: dict, fields: dict) -> str:
    text = json.dumps(expression, ensure_ascii=False, separators=(",", ":"))
    for key, label in fields.items():
        text = text.replace(f'"{key}"', f'"{label}"')
    return text


def _references(expression: dict, key: str) -> set[str]:
    found = set()
    if not isinstance(expression, dict):
        return found
    if key in expression and isinstance(expression[key], str):
        found.add(expression[key])
    for value in expression.values():
        if isinstance(value, dict):
            found.update(_references(value, key))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    found.update(_references(item, key))
    return found


def _scope_compatible(left: dict, right: dict) -> bool:
    """Historical intervals may overlap even when current validity is unverified."""
    regions = {s.get("region") for s in (left, right)} - {None, "", "全国"}
    if len(regions) > 1 and regions != {"湖北", "武汉"}:
        return False
    if left.get("version") and right.get("version") and left["version"] != right["version"]:
        return False
    starts, ends = [], []
    try:
        for scope in (left, right):
            if scope.get("valid_from"):
                starts.append(date.fromisoformat(scope["valid_from"]))
            if scope.get("valid_to"):
                ends.append(date.fromisoformat(scope["valid_to"]))
    except (TypeError, ValueError):
        return False
    return not starts or not ends or max(starts) <= min(ends)


def build_graph(corpus: dict, profile: dict, similarities: dict | None = None) -> dict:
    nodes, edges = {}, []
    edge_map = {}
    units = {u["id"]: u for u in corpus["units"]}
    matters = {m["id"]: m for m in corpus["matters"]}
    similarities = similarities or {}
    actions = {a["id"]: a for a in corpus["actions"]}
    dependencies = {
        aid: {
            leaf["completed"] for leaf in _leaves(a.get("preconditions", {})) if "completed" in leaf
        }
        for aid, a in actions.items()
    }
    for rule in corpus["rules"]:
        if rule.get("action_id") in dependencies and rule["status"] == "active":
            dependencies[rule["action_id"]].update(
                leaf["completed"] for leaf in _leaves(rule["condition"]) if "completed" in leaf
            )
    action_order = list(actions)
    action_index = {key: i for i, key in enumerate(action_order)}
    dependency_graph = ig.Graph(
        n=len(actions),
        directed=True,
        edges=[
            (action_index[before], action_index[after])
            for after, required in dependencies.items()
            for before in required
            if before in actions
        ],
    )
    cyclic = {
        action_order[i]
        for component in dependency_graph.connected_components(mode="strong")
        for i in component
        if len(component) > 1 or action_order[i] in dependencies[action_order[i]]
    }

    def grounded(items):
        return [
            e
            for e in items
            if e["unit_id"] in units
            and e.get("quote")
            and e["quote"] in units[e["unit_id"]]["text"]
        ]

    def components(owner, expression, scope, evidence, action_id=None):
        mid = owner["matter_id"]
        fields = {f["id"] for f in matters.get(mid, {}).get("fields", [])}
        references = _references(expression, "completed")
        continuous = not validate_expression(expression, fields) and mid in matters
        continuous &= all(ref in actions and actions[ref]["matter_id"] == mid for ref in references)
        if action_id is not None:
            continuous &= action_id in actions and actions[action_id]["matter_id"] == mid
            if action_id in actions:
                linked = actions[action_id]
                continuous &= not validate_expression(linked.get("preconditions"), fields)
                continuous &= all(field in fields for field in linked["effects"])
        if "effects" in owner:
            continuous &= all(field in fields for field in owner["effects"])
        scopes = [scope] + [units[e["unit_id"]] for e in evidence]
        if "effects" in owner:
            scopes.extend(
                r.get("scope", {})
                for r in corpus["rules"]
                if r["status"] == "active"
                and r["matter_id"] == mid
                and r.get("action_id") in (None, owner["id"])
            )
        for reference in references:
            if reference in actions:
                scopes.extend(units[e["unit_id"]] for e in grounded(actions[reference]["evidence"]))
        compatible = all(_scope_compatible(a, b) for i, a in enumerate(scopes) for b in scopes[i:])
        compatible &= action_id not in cyclic and not (references & cyclic)
        coverage = len(evidence) / max(1, len(owner.get("evidence", [])))
        parts = {
            "coverage": coverage,
            "continuity": float(continuous),
            "temporal": float(compatible),
        }
        return parts, compatible

    def node(key, label, kind, layer, matter_id="", evidence=None):
        if key not in nodes:
            nodes[key] = {
                "id": key,
                "label": label,
                "type": kind,
                "layer": layer,
                "matter_id": matter_id,
                "source_chunk_ids": [],
                "evidence": [],
            }
        for item in evidence or []:
            if item not in nodes[key]["evidence"]:
                nodes[key]["evidence"].append(item)
            if item["unit_id"] not in nodes[key]["source_chunk_ids"]:
                nodes[key]["source_chunk_ids"].append(item["unit_id"])

    def edge(source, target, kind, evidence, rule_id="", rpc=0.0, scs=0.0, **metadata):
        if kind in CAUSAL_TYPES and profile["rpc"] and rpc < profile["rpc_threshold"]:
            return
        if kind in CAUSAL_TYPES and any(
            status in {"disabled", "rejected"}
            for status in (
                metadata.get("status"),
                nodes[source].get("status"),
                nodes[target].get("status"),
            )
        ):
            return
        edge_id = _id(source, target, kind, rule_id)
        if edge_id in edge_map:
            stored = edge_map[edge_id]["evidence"]
            stored.extend(item for item in evidence if item not in stored)
            return
        edges.append(
            {
                "id": edge_id,
                "source": source,
                "target": target,
                "type": kind,
                "predicate": kind,
                "layer": "cross"
                if nodes[source]["layer"] != nodes[target]["layer"]
                else nodes[source]["layer"],
                "source_chunk_id": evidence[0]["unit_id"] if evidence else "",
                "evidence": list(evidence),
                "rule_ids": [rule_id] if rule_id else [],
                "rpc": rpc,
                "scs": scs,
                **metadata,
            }
        )
        edge_map[edge_id] = edges[-1]

    def add_conditions(owner_id, expression, mid, evidence, metadata, rule_ids):
        fields = {f["id"]: f["label"] for f in matters[mid]["fields"]}
        nodes[owner_id]["condition"] = expression
        nodes[owner_id]["required_condition_ids"] = []
        for i, condition in enumerate(_leaves(expression)):
            cid = _id(owner_id, "condition", str(i))
            node(cid, _expression_label(condition, fields), "CONDITION", "micro", mid, evidence)
            nodes[cid].update(
                condition=condition,
                rule_ids=rule_ids,
                owner_id=owner_id,
                status=metadata["status"],
                scope=nodes[owner_id].get("scope", {}),
            )
            nodes[owner_id]["required_condition_ids"].append(cid)
            kind = "EXCEPTS" if "not" in condition else "REQUIRES"
            edge(cid, owner_id, kind, evidence, rule_ids[0] if rule_ids else "", **metadata)
            # OR/NOT references remain inside the expression; they are not mandatory predecessors.
            if "completed" in condition and condition["completed"] in nodes:
                edge(
                    condition["completed"],
                    cid,
                    "PRECEDES",
                    evidence,
                    rule_ids[0] if rule_ids else "",
                    **metadata,
                )

    for document in corpus["documents"]:
        node(document["id"], document["filename"], "LAW", "macro")
    for unit in units.values():
        evidence = [
            {
                "unit_id": unit["id"],
                "quote": unit["text"],
                "source_path": unit.get("source_path", ""),
                "title": unit["title"],
                "article": unit["article"],
            }
        ]
        node(
            unit["id"], f"{unit['title']} {unit['article']}", "ARTICLE", "macro", evidence=evidence
        )
        nodes[unit["id"]]["scope"] = {
            key: unit.get(key) for key in ("region", "valid_from", "valid_to", "version")
        }
        edge(unit["document_id"], unit["id"], "CONTAINS", evidence, structural_weight=1.0)
    for matter in matters.values():
        node(matter["id"], matter["name"], "MATTER", "macro", matter["id"])
        for uid in matter["source_unit_ids"]:
            if uid in nodes:
                edge(
                    matter["id"], uid, "GROUNDED_IN", nodes[uid]["evidence"], structural_weight=1.0
                )
        evidence = [
            e for uid in matter["source_unit_ids"] if uid in nodes for e in nodes[uid]["evidence"]
        ]
        for field in matter["fields"]:
            role_id = _id(matter["id"], "role", field["role"])
            node(
                role_id,
                {"applicant": "申请人", "external": "外部核验方", "policy": "政策参数"}[
                    field["role"]
                ],
                "PERSON_ROLE" if field["role"] != "policy" else "CONCEPT",
                "macro",
                matter["id"],
                evidence,
            )
            fid = _id(matter["id"], "field", field["id"])
            node(
                fid,
                field["label"],
                "MATERIAL" if field["type"] in {"set", "text"} else "CONCEPT",
                "macro",
                matter["id"],
                evidence,
            )
            nodes[fid].update(field_id=field["id"], field_type=field["type"])
            edge(matter["id"], role_id, "INVOLVES", evidence, structural_weight=1.0)
            edge(role_id, fid, "PROVIDES", evidence, structural_weight=1.0)

    action_metadata = {}
    for action in corpus["actions"]:
        mid, aid = action["matter_id"], action["id"]
        if mid not in matters:
            continue
        evidence = grounded(action["evidence"])
        scope = action.get("scope") or (
            {
                key: units[evidence[0]["unit_id"]].get(key)
                for key in ("region", "valid_from", "valid_to", "version")
            }
            if evidence
            else {}
        )
        parts, compatible = components(
            action, action.get("preconditions", {}), scope, evidence, aid
        )
        supporting = [
            r
            for r in corpus["rules"]
            if r["matter_id"] == mid and r.get("action_id") in (None, aid)
        ]
        statuses = {r["status"] for r in supporting}
        specific = [r for r in supporting if r.get("action_id") == aid]
        unsupported = specific and not any(r["status"] == "active" for r in specific)
        status = (
            "disabled"
            if "disabled" in statuses or unsupported
            else "candidate"
            if "candidate" in statuses
            else "active"
            if "active" in statuses
            else "disabled"
        )
        metadata = {
            "rpc": rpc_score(**parts),
            "rpc_components": parts,
            "compatible": compatible,
            "status": status,
        }
        action_metadata[aid] = metadata
        node(aid, action["label"], "ACTION", "micro", mid, evidence)
        nodes[aid].update(scope=scope, **metadata)
        macro_id = _id(aid, "macro")
        node(macro_id, action["label"], "ACTION", "macro", mid, evidence)
        edge(mid, macro_id, "HANDLES", evidence, structural_weight=1.0)
        # These are two views of the identical catalog action, not a semantic guess.
        edge(
            macro_id,
            aid,
            "REALIZES",
            evidence,
            scs=1.0,
            structural_weight=1.0,
            scs_components={"identity": 1.0},
            **metadata,
        )
        for field, value in action["effects"].items():
            key = _id(aid, field, json.dumps(value, sort_keys=True, ensure_ascii=False))
            node(key, f"{field}={value}", "STATE", "micro", mid, evidence)
            nodes[key].update(field_id=field, value=value, scope=scope, status=status)
            edge(aid, key, "PRODUCES", evidence, **metadata)
    for aid, metadata in action_metadata.items():
        action = actions[aid]
        rule_ids = [
            r["id"]
            for r in corpus["rules"]
            if r.get("action_id") == aid and r["status"] == "active"
        ]
        add_conditions(
            aid,
            action.get("preconditions", {}),
            action["matter_id"],
            grounded(action["evidence"]),
            metadata,
            rule_ids,
        )

    for rule in corpus["rules"]:
        evidence = grounded(rule["evidence"])
        parts, compatible = components(
            rule, rule["condition"], rule.get("scope", {}), evidence, rule.get("action_id")
        )
        rpc = rpc_score(**parts)
        missing_condition = rule.get("condition") is None
        if not evidence or (
            not missing_condition and profile["rpc"] and rpc < profile["rpc_threshold"]
        ):
            continue
        rid, mid = rule["id"], rule["matter_id"]
        if mid not in matters:
            continue
        metadata = {
            "rpc": rpc,
            "rpc_components": parts,
            "compatible": compatible,
            "status": rule["status"],
        }
        node(rid, rule["label"], "RULE", "micro", mid, evidence)
        nodes[rid].update(rule_ids=[rid], scope=rule.get("scope", {}), **metadata)
        if missing_condition:
            nodes[rid].update(
                condition=None, required_condition_ids=[], knowledge_gaps=["候选规则尚无可执行条件"]
            )
        else:
            add_conditions(rid, rule["condition"], mid, evidence, metadata, [rid])
        if not missing_condition and rule.get("action_id") in nodes:
            edge(rid, rule["action_id"], "REQUIRES", evidence, rid, **metadata)
        for e in evidence:
            semantic = max(0.0, min(1.0, similarities.get((e["unit_id"], rid), 0.0)))
            scs_parts = {"semantic": semantic, "support": parts["coverage"], "compatible_type": 1.0}
            scope_ok = _scope_compatible(units[e["unit_id"]], rule.get("scope", {}))
            scs = scs_score(**scs_parts, compatible=scope_ok)
            if scope_ok and (not profile["scs"] or scs >= profile["scs_threshold"]):
                edge(
                    e["unit_id"],
                    rid,
                    "REALIZES",
                    [e],
                    rid,
                    scs=scs,
                    semantic_weight=semantic,
                    scs_components=scs_parts,
                    **metadata,
                )

    # A produced value supports a later condition only when the DSL proves it, not by label similarity.
    for condition in list(nodes.values()):
        if condition["type"] != "CONDITION" or not _references(condition["condition"], "field"):
            continue
        for aid, metadata in action_metadata.items():
            action = actions[aid]
            if action["matter_id"] != condition["matter_id"] or condition["owner_id"] == aid:
                continue
            if evaluate(condition["condition"], action["effects"], [aid])["status"] != "satisfied":
                continue
            for field in _references(condition["condition"], "field") & action["effects"].keys():
                state_id = _id(
                    aid,
                    field,
                    json.dumps(action["effects"][field], sort_keys=True, ensure_ascii=False),
                )
                owner = nodes[condition["owner_id"]]
                compatible = metadata["compatible"] and _scope_compatible(
                    nodes[state_id].get("scope", {}), condition.get("scope", {})
                )
                evidence = grounded(action["evidence"]) + condition["evidence"]
                combined = dict(
                    metadata,
                    compatible=compatible,
                    status="active"
                    if metadata["status"] == owner["status"] == "active"
                    else "candidate",
                    rpc=min(metadata["rpc"], owner["rpc"]),
                )
                edge(
                    state_id,
                    condition["id"],
                    "REQUIRES",
                    evidence,
                    condition["rule_ids"][0] if condition["rule_ids"] else "",
                    **combined,
                )

    nodes = {key: value for key, value in nodes.items() if profile[value["layer"]]}
    edges = [e for e in edges if e["source"] in nodes and e["target"] in nodes]
    node_list = list(nodes.values())
    communities = assign_communities(node_list, edges, profile)
    return {"nodes": node_list, "edges": edges, "communities": communities}


def assign_communities(nodes: list[dict], edges: list[dict], profile: dict) -> list[dict]:
    if not nodes:
        return []
    parent = {n["id"]: n["id"] for n in nodes}
    node_map = {n["id"]: n for n in nodes}
    merged = {n["id"]: [n["id"]] for n in nodes}
    for n in nodes:
        n["community_ids"] = []

    def find(key):
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for edge in edges:
        if (
            profile["causal_constraints"]
            and edge.get("type") in CAUSAL_TYPES
            and edge.get("status") == "active"
            and edge.get("compatible", True)
            and node_map[edge["source"]].get("status", "active") == "active"
            and node_map[edge["target"]].get("status", "active") == "active"
            and edge.get("rpc", 0) >= profile["strong_threshold"]
        ):
            left, right = find(edge["source"]), find(edge["target"])
            if left != right and all(
                _scope_compatible(node_map[a].get("scope", {}), node_map[b].get("scope", {}))
                for a in merged[left]
                for b in merged[right]
            ):
                parent[right] = left
                merged[left].extend(merged.pop(right))
    groups = defaultdict(list)
    for n in nodes:
        groups[find(n["id"])].append(n["id"])
    roots = sorted(groups)
    index = {key: i for i, key in enumerate(roots)}
    weights = defaultdict(float)
    for edge in edges:
        a, b = index[find(edge["source"])], index[find(edge["target"])]
        weight = edge.get("semantic_weight", edge.get("structural_weight", edge.get("rpc", 0)))
        if weight > 0:
            # Preserve internal mass as self loops after contraction.
            weights[tuple(sorted((a, b)))] += weight
    graph = ig.Graph(n=len(roots), edges=list(weights), directed=False)
    ig.set_random_number_generator(random.Random(profile["seed"]))
    partition = graph.community_leiden(
        objective_function="modularity",
        weights=list(weights.values()),
        resolution=profile["resolution"],
        n_iterations=-1,
    )
    result = []

    def record(vertices, level, prefix, parent_id=None):
        members = [uid for i in vertices for uid in groups[roots[i]]]
        cid = f"c{level}:" + _id(*sorted(members))
        result.append(
            {
                "id": cid,
                "label": f"{prefix}（{len(members)}节点）",
                "level": level,
                "node_count": len(members),
                "parent_id": parent_id,
                "node_ids": sorted(members),
                "unsplittable": len(vertices) == 1 and len(members) > 1,
            }
        )
        for uid in members:
            node_map[uid]["community_id"] = cid
            node_map[uid].setdefault("community_ids", []).append(cid)
        if level >= profile["community_levels"] or len(vertices) < 4:
            return
        sub = graph.induced_subgraph(vertices)
        sub_weights = [
            weights[tuple(sorted((vertices[e.source], vertices[e.target])))] for e in sub.es
        ]
        child = sub.community_leiden(
            objective_function="CPM", weights=sub_weights, resolution=0.5 * level, n_iterations=-1
        )
        if len(child) <= 1:
            return
        for j, members in enumerate(child):
            record([vertices[i] for i in members], level + 1, f"{prefix}.{j + 1}", cid)

    for i, vertices in enumerate(partition):
        record(list(vertices), 1, f"社区{i + 1}")
    return result


def path_candidates(
    nodes: list[dict], edges: list[dict], scores: dict[str, float], seeds: list[str], profile: dict
) -> list[dict]:
    node_map = {n["id"]: n for n in nodes}
    outgoing = defaultdict(list)
    for edge in edges:
        outgoing[edge["source"]].append(edge)
    paths = []
    stack = [(seed, [seed], [], []) for seed in reversed(seeds) if seed in node_map]
    while stack and len(paths) < profile["max_candidates"]:
        current, ids, chain, entropies = stack.pop()
        available = [e for e in outgoing[current] if e["target"] not in ids]
        if chain:
            semantic = sum(scores.get(uid, 0) for uid in ids) / len(ids)
            rpc = sum(e.get("rpc", 1) for e in chain) / len(chain)
            entropy = sum(entropies) / max(1, len(entropies))
            score = 0.4 * semantic if profile["semantic"] else 0
            score += 0.4 * rpc if profile["rpc"] else 0
            score += 0.2 * (1 - entropy) if profile["entropy"] else 0
            evidence = {
                json.dumps(e, sort_keys=True, ensure_ascii=False): e
                for edge in chain
                for e in edge.get("evidence", [])
            }
            paths.append(
                {
                    "id": _id(*[e["id"] for e in chain]),
                    "node_ids": ids,
                    "edge_ids": [e["id"] for e in chain],
                    "labels": [node_map[uid]["label"] for uid in ids],
                    "score": score,
                    "semantic_score": semantic,
                    "rpc": rpc,
                    "entropy": entropy,
                    "evidence": list(evidence.values()),
                    "rule_ids": sorted({r for e in chain for r in e.get("rule_ids", [])}),
                }
            )
        if len(chain) >= profile["max_hops"] or not available:
            continue
        ordered = sorted(available, key=lambda e: (-scores.get(e["target"], 0), e["id"]))
        exps = [math.exp(scores.get(e["target"], 0)) for e in ordered]
        total = sum(exps)
        entropy = (
            -sum((x / total) * math.log(x / total) for x in exps) / math.log(len(exps))
            if len(exps) > 1
            else 0.0
        )
        for edge in reversed(ordered):
            stack.append(
                (edge["target"], ids + [edge["target"]], chain + [edge], entropies + [entropy])
            )
    return sorted(paths, key=lambda p: (-p["score"], len(p["edge_ids"]), p["id"]))
