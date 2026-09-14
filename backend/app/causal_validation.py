"""Replay a retrieved path without treating an omitted prefix as a proven failure."""

import json
from copy import deepcopy

from app.workflow import _Context, _scope, _status


def validate_path(corpus: dict, request: dict, path: dict, nodes: list[dict]) -> dict:
    node_map = {node["id"]: node for node in nodes}
    rules = {rule["id"]: rule for rule in corpus["rules"]}
    actions = {action["id"]: action for action in corpus["actions"]}
    entities = rules | actions
    ids = path.get("node_ids", [])
    owners = [node_map.get(uid, {}).get("owner_id", uid) for uid in ids]
    matter_id = request.get("matter_id") or next(
        (
            entities[uid]["matter_id"]
            for uid in owners + path.get("rule_ids", [])
            if uid in entities
        ),
        None,
    )
    context = (
        _Context(corpus, dict(request, matter_id=matter_id), unknown_completed=True)
        if matter_id
        else None
    )
    state = deepcopy(context.facts if context else request.get("facts", {}))
    completed = list(request.get("completed_steps", []))
    checks, gaps = [], list(context.input_gaps) if context else []
    required = list(path.get("evidence", []))
    referenced = set(owners) | set(path.get("rule_ids", []))
    for uid in ids:
        node = node_map.get(uid, {})
        required.extend(node.get("evidence", []))
        referenced.update(node.get("rule_ids", []))
    for uid in list(referenced):
        if uid in actions:
            action = actions[uid]
            referenced.update(
                r["id"]
                for r in corpus["rules"]
                if r["matter_id"] == action["matter_id"] and r.get("action_id") in (None, uid)
            )
    for uid in sorted(referenced):
        if uid in entities:
            required.extend(entities[uid].get("evidence", []))

    first_blocked = None
    seen_rules = set()

    def rule_check(rule, node_id):
        if rule["matter_id"] != matter_id:
            gap = "路径跨越事项，缺少可共享状态的定义"
        elif rule["status"] != "active":
            gap = "规则尚未启用或已停用"
        else:
            gap = _scope(rule.get("scope", {}), request)
        result = (
            {"status": "unknown", "missing_fields": [], "reasons": [gap]}
            if gap
            else context.condition(rule["condition"], state, completed)
        )
        result.update(
            node_id=node_id,
            rule_id=rule["id"],
            label=rule["label"],
            evidence=rule.get("evidence", []),
        )
        seen_rules.add(rule["id"])
        return result

    def record(result):
        checks.append(result)
        if result["status"] == "unknown":
            gaps.extend(result.get("reasons", []))

    for uid in ids:
        node = node_map.get(uid, {})
        owner = node.get("owner_id", uid)
        if first_blocked is not None:
            record(
                {
                    "node_id": uid,
                    "rule_id": owner if owner in entities else None,
                    "label": node.get("label", uid),
                    "status": "unknown",
                    "missing_fields": [],
                    "reasons": [f"前缀在{first_blocked}处未通过，后缀未验证"],
                    "evidence": [],
                    "deferred": True,
                }
            )
            continue
        if owner in actions:
            action = actions[owner]
            if action["matter_id"] != matter_id:
                record(
                    {
                        "node_id": uid,
                        "rule_id": owner,
                        "label": action["label"],
                        "status": "unknown",
                        "missing_fields": [],
                        "evidence": action.get("evidence", []),
                        "reasons": ["路径跨越事项，缺少可共享状态的定义"],
                    }
                )
                first_blocked = uid
                continue
            status, results, action_gaps, updated, _ = context.attempt(owner, state, completed)
            seen_rules.update(r["rule_id"] for r in results if r.get("rule_id") in rules)
            for result in results:
                record(dict(result, node_id=uid, action_id=owner))
            gaps.extend(action_gaps)
            if status != "satisfied":
                first_blocked = uid
            elif uid == owner and owner not in completed:
                state = updated
                completed.append(owner)
        elif owner in rules:
            result = rule_check(rules[owner], uid)
            record(result)
            if result["status"] != "satisfied":
                first_blocked = uid
        elif node.get("layer") != "macro" and node.get("type") in {"RULE", "ACTION", "CONDITION"}:
            record(
                {
                    "node_id": uid,
                    "rule_id": None,
                    "label": node.get("label", uid),
                    "status": "unknown",
                    "missing_fields": [],
                    "evidence": [],
                    "reasons": ["路径节点缺少可执行定义"],
                }
            )
            first_blocked = uid

    if first_blocked is None:
        for rid in sorted(set(path.get("rule_ids", [])) - seen_rules):
            if rid in rules:
                result = rule_check(rules[rid], rid)
                record(result)
                if result["status"] != "satisfied":
                    first_blocked = rid
                    break
    if not checks:
        gaps.append("该路径仅提供结构来源，未包含可核查的规则或动作")
    if context:
        gaps.extend(context.matter.get("gaps", []))
    return {
        "status": _status(checks) if checks else "unknown",
        "checks": checks,
        "knowledge_gaps": list(dict.fromkeys(gaps)),
        "required_evidence": list(
            {json.dumps(e, sort_keys=True, ensure_ascii=False): e for e in required}.values()
        ),
        "completed_steps": completed,
        "state": state,
        "first_blocked_node": first_blocked,
    }
