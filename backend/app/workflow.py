"""Deterministic replay and minimum unit edit cost repair of proposed actions."""

import json
from copy import deepcopy
from datetime import date
from heapq import heappop, heappush
from itertools import count

from app.rule_engine import evaluate, validate_expression


def _status(results):
    statuses = [r["status"] for r in results]
    return (
        "violated"
        if "violated" in statuses
        else "unknown"
        if "unknown" in statuses
        else "satisfied"
    )


def _scope(scope, request):
    region = request.get("region")
    scope_region = scope.get("region")
    if not region or not scope_region:
        return "缺少规则或申请地域"
    if (
        scope_region != "全国"
        and region != scope_region
        and not (scope_region == "湖北" and region == "武汉")
    ):
        return f"规则地域{scope_region}不能支持申请地域{region}"
    if not scope.get("validity_known"):
        return "规则有效期尚未核实"
    try:
        as_of = date.fromisoformat(request.get("as_of") or "")
        start = date.fromisoformat(scope["valid_from"]) if scope.get("valid_from") else None
        end = date.fromisoformat(scope["valid_to"]) if scope.get("valid_to") else None
    except (TypeError, ValueError):
        return "缺少或无效的业务日期/规则有效期"
    if (start and as_of < start) or (end and as_of > end):
        return "业务日期不在规则已知有效期内"
    return None


class _Context:
    def __init__(self, corpus, request, *, unknown_completed=False):
        self.request = request
        self.unknown_completed = unknown_completed
        self.matter = next((m for m in corpus["matters"] if m["id"] == request["matter_id"]), None)
        if self.matter is None:
            raise ValueError("事项不存在")
        self.fields = {f["id"]: f for f in self.matter["fields"]}
        self.actions = {
            a["id"]: a for a in corpus["actions"] if a["matter_id"] == self.matter["id"]
        }
        self.rules = [r for r in corpus["rules"] if r["matter_id"] == self.matter["id"]]
        self.facts = {
            key: deepcopy(value)
            for key, value in request.get("facts", {}).items()
            if key in self.fields and self.fields[key]["role"] != "policy"
        }
        self.facts.update(deepcopy(self.matter.get("policy_parameters", {})))
        self.input_gaps = []
        for key, value in list(self.facts.items()):
            if value is not None and (
                key not in self.fields or not self.valid_value(self.fields[key], value)
            ):
                self.input_gaps.append(f"字段{key}类型或取值无效")
                self.facts[key] = None

    @staticmethod
    def valid_value(field, value):
        kind = field["type"]
        if kind == "boolean":
            return type(value) is bool
        if kind == "number":
            from math import isfinite

            return type(value) is int or (type(value) is float and isfinite(value))
        if kind == "date":
            try:
                return isinstance(value, str) and date.fromisoformat(value).isoformat() == value
            except ValueError:
                return False
        if kind == "set":
            return isinstance(value, list) and all(isinstance(v, str) for v in value)
        return isinstance(value, str) and (kind != "enum" or value in field.get("options", []))

    def condition(self, expression, state, completed):
        errors = validate_expression(expression, set(self.fields))
        pending = [expression] if not errors else []
        while pending:
            node = pending.pop()
            if "completed" in node and node["completed"] not in self.actions:
                errors.append(f"前置动作定义缺失：{node['completed']}")
            for value in node.values():
                if isinstance(value, dict):
                    pending.append(value)
                elif isinstance(value, list):
                    pending.extend(item for item in value if isinstance(item, dict))
        if errors:
            return {"status": "unknown", "missing_fields": [], "reasons": errors}
        return evaluate(expression, state, completed, unknown_completed=self.unknown_completed)

    def rules_for(self, action_id, state, completed, include_condition_checks=False):
        relevant = [
            r
            for r in self.rules
            if r.get("action_id") in (None, action_id)
            or (include_condition_checks and r.get("purpose") == "condition_check")
        ]
        checks, gaps = [], list(self.input_gaps)
        active = [r for r in relevant if r["status"] == "active"]
        if not any(r["status"] == "active" for r in self.rules):
            gaps.append("该事项或动作没有已启用的可执行规则")
        specific = [
            r for r in relevant if action_id is not None and r.get("action_id") == action_id
        ]
        unsupported = specific and not any(r["status"] == "active" for r in specific)
        if any(r["status"] == "disabled" for r in relevant) or unsupported:
            gaps.append("动作必要规则已停用或缺少已启用的动作专属规则")
            checks.append(
                {
                    "rule_id": None,
                    "label": "规则覆盖",
                    "status": "unknown",
                    "missing_fields": [],
                    "reasons": [gaps[-1]],
                    "evidence": [],
                }
            )
        pending = [r for r in relevant if r["status"] == "candidate"]
        if pending:
            gaps.append("相关候选规则尚未审核启用")
            checks.append(
                {
                    "rule_id": None,
                    "label": "规则审核",
                    "status": "unknown",
                    "missing_fields": [],
                    "reasons": [gaps[-1]],
                    "evidence": [],
                }
            )
        for rule in active:
            gap = _scope(rule.get("scope", {}), self.request)
            if gap:
                gaps.append(f"{rule['label']}：{gap}")
                result = {"status": "unknown", "missing_fields": [], "reasons": [gap]}
            else:
                result = self.condition(rule["condition"], state, completed)
            if result["status"] == "unknown":
                gaps.extend(result["reasons"])
            checks.append(
                dict(
                    result,
                    rule_id=rule["id"],
                    label=rule["label"],
                    evidence=rule.get("evidence", []),
                )
            )
        if gaps and not checks:
            checks.append(
                {
                    "rule_id": None,
                    "label": "知识完整性",
                    "status": "unknown",
                    "missing_fields": [],
                    "reasons": gaps,
                    "evidence": [],
                }
            )
        return checks, gaps

    def attempt(self, action_id, state, completed):
        checks, gaps = self.rules_for(action_id, state, completed)
        action = self.actions.get(action_id)
        if action is None:
            checks.append(
                {
                    "rule_id": None,
                    "label": action_id,
                    "status": "violated",
                    "missing_fields": [],
                    "reasons": ["动作不属于该事项"],
                    "evidence": [],
                }
            )
            return "violated", checks, gaps, state, "action"
        result = self.condition(action["preconditions"], state, completed)
        if result["status"] == "unknown":
            gaps.extend(result["reasons"])
        checks.append(
            dict(result, rule_id=None, label=action["label"], evidence=action.get("evidence", []))
        )
        kind = "precondition"
        for field_id, value in action.get("effects", {}).items():
            field = self.fields.get(field_id)
            error, missing, effect_status = None, [], "violated"
            if not field or not self.valid_value(field, value):
                error = f"动作效果字段{field_id}未声明或值无效"
            elif action["kind"] == "external":
                if field["role"] != "external":
                    error = "外部动作只能确认外部事实"
                elif self.facts.get(field_id) != value or type(
                    self.facts.get(field_id)
                ) is not type(value):
                    error, missing, effect_status = (
                        f"缺少外部已确认事实：{field_id}",
                        [field_id],
                        "unknown",
                    )
                    gaps.append(error)
                    kind = "external"
            elif field["role"] != "applicant" or not field.get("mutable", False):
                error = f"不能通过模拟改写不可变字段：{field_id}"
                kind = "immutable"
            if error:
                checks.append(
                    {
                        "rule_id": None,
                        "label": action["label"],
                        "status": effect_status,
                        "missing_fields": missing,
                        "reasons": [error],
                        "evidence": action.get("evidence", []),
                    }
                )
        if action["kind"] == "external" and not action.get("effects"):
            gaps.append("外部动作缺少可核对的确认事实")
            checks.append(
                {
                    "rule_id": None,
                    "label": action["label"],
                    "status": "unknown",
                    "missing_fields": [],
                    "reasons": [gaps[-1]],
                    "evidence": action.get("evidence", []),
                }
            )
        status = _status(checks)
        updated = deepcopy(state)
        if status == "satisfied":
            updated.update(deepcopy(action.get("effects", {})))
        return status, checks, gaps, updated, kind

    def goal(self, state, completed):
        goal_id = self.request.get("goal")
        if not goal_id:
            return {"status": "satisfied", "missing_fields": [], "reasons": []}
        goal = next((g for g in self.matter.get("goals", []) if g["id"] == goal_id), None)
        if goal is None:
            return {"status": "unknown", "missing_fields": [], "reasons": ["目标未在事项中定义"]}
        return self.condition(goal["condition"], state, completed)


def check_workflow(corpus: dict, request: dict) -> dict:
    return _check_workflow(corpus, request, include_condition_checks=True)


def _check_workflow(corpus: dict, request: dict, *, include_condition_checks=False) -> dict:
    context = _Context(corpus, request)
    state, completed = deepcopy(context.facts), []
    checks, gaps = context.rules_for(None, state, completed)
    gaps.extend(context.matter.get("gaps", []))
    first_error = None
    if _status(checks) != "satisfied":
        first_error = {
            "index": -1,
            "action_id": None,
            "kind": "rule",
            "message": "前置规则未满足或缺少资料",
        }
    if first_error is None:
        for history, sequence in (
            (True, request.get("completed_steps", [])),
            (False, request.get("steps", [])),
        ):
            for index, action_id in enumerate(sequence):
                status, step_checks, step_gaps, updated, kind = context.attempt(
                    action_id, state, completed
                )
                checks.extend(step_checks)
                gaps.extend(step_gaps)
                if status != "satisfied":
                    first_error = {
                        "index": index,
                        "action_id": action_id,
                        "kind": "history" if history else kind,
                        "message": "；".join(
                            reason
                            for c in step_checks
                            if c["status"] != "satisfied"
                            for reason in c["reasons"]
                        ),
                    }
                    break
                state = updated
                completed.append(action_id)
            if first_error:
                break
    goal = context.goal(state, completed)
    if first_error is None and include_condition_checks and not request.get("steps"):
        condition_checks, condition_gaps = context.rules_for(
            None, state, completed, include_condition_checks=True
        )
        checks.extend(condition_checks)
        gaps.extend(condition_gaps)
        if _status(condition_checks) != "satisfied":
            first_error = {
                "index": -1,
                "action_id": None,
                "kind": "rule",
                "message": "事实核查条件未满足或缺少资料",
            }
    status = _status(checks + ([goal] if first_error is None else []))
    if first_error is None and goal["status"] != "satisfied":
        first_error = {
            "index": len(request.get("steps", [])),
            "action_id": None,
            "kind": "goal",
            "message": "目标尚未满足",
        }
    if goal["status"] == "unknown":
        gaps.extend(goal["reasons"])
    return {
        "status": status,
        "checks": checks,
        "first_error": first_error,
        "missing_fields": sorted({f for c in checks + [goal] for f in c["missing_fields"]}),
        "knowledge_gaps": list(dict.fromkeys(gaps)),
        "state": state,
        "completed_steps": completed,
        "goal_satisfied": True
        if goal["status"] == "satisfied"
        else False
        if goal["status"] == "violated"
        else None,
    }


def repair_workflow(corpus: dict, request: dict, max_states: int = 5000) -> dict:
    if max_states < 1:
        raise ValueError("max_states必须大于0")
    original = list(request.get("steps", []))
    checked = check_workflow(corpus, request)

    def result(status, steps=original, edits=None, cost=None, explored=0, final=checked):
        return {
            "status": status,
            "steps": steps,
            "edits": edits or [],
            "cost": cost,
            "checked": final,
            "explored_states": explored,
            "truncated": status == "truncated",
        }

    if checked["status"] == "satisfied":
        return result("already_valid", cost=0)
    base_request = dict(request, steps=[], goal=None)
    base = _check_workflow(corpus, base_request)
    if base["status"] != "satisfied":
        return result("unknown" if base["status"] == "unknown" else "unreachable")
    context = _Context(corpus, request)
    serial = count()
    queue, best = [], {}

    def push(cost, position, state, completed, steps, edits):
        # Position is part of identity: equal facts can have different unconsumed suffixes.
        key = (
            position,
            json.dumps(state, sort_keys=True, ensure_ascii=False),
            tuple(sorted(set(completed))),
        )
        if cost < best.get(key, float("inf")):
            best[key] = cost
            heappush(queue, (cost, next(serial), key, state, completed, steps, edits))

    push(0, 0, base["state"], base["completed_steps"], [], [])
    explored, unknown_seen = 0, False
    while queue:
        cost, _, key, state, completed, steps, edits = heappop(queue)
        if best[key] != cost:
            continue
        if explored >= max_states:
            return result("truncated", explored=explored)
        explored += 1
        position = key[0]
        if position == len(original):
            goal = context.goal(state, completed)
            if goal["status"] == "satisfied":
                final = check_workflow(corpus, dict(request, steps=steps))
                if final["status"] == "satisfied":
                    return result("repaired", steps, edits, cost, explored, final)
                unknown_seen |= final["status"] == "unknown"
            unknown_seen |= goal["status"] == "unknown"
        if position < len(original):
            push(
                cost + 1,
                position + 1,
                state,
                completed,
                steps,
                edits + [{"op": "delete", "index": position, "action_id": original[position]}],
            )
        for action_id in context.actions:
            status, _, _, updated, _ = context.attempt(action_id, state, completed)
            unknown_seen |= status == "unknown"
            if status != "satisfied":
                continue
            following = completed + [action_id]
            if position < len(original):
                keep = original[position] == action_id
                edit = (
                    []
                    if keep
                    else [
                        {
                            "op": "replace",
                            "index": position,
                            "from_action_id": original[position],
                            "action_id": action_id,
                        }
                    ]
                )
                push(
                    cost + (not keep),
                    position + 1,
                    updated,
                    following,
                    steps + [action_id],
                    edits + edit,
                )
            push(
                cost + 1,
                position,
                updated,
                following,
                steps + [action_id],
                edits + [{"op": "insert", "index": position, "action_id": action_id}],
            )
    return result("unknown" if unknown_seen else "unreachable", explored=explored)


def next_steps(corpus: dict, request: dict) -> dict:
    checked = _check_workflow(corpus, dict(request, goal=None))
    if checked["status"] != "satisfied":
        return {"status": checked["status"], "candidates": [], "state": checked["state"]}
    context = _Context(corpus, request)
    candidates = []
    for action in context.actions.values():
        status, checks, _, updated, _ = context.attempt(
            action["id"], checked["state"], checked["completed_steps"]
        )
        candidates.append(
            {
                "action_id": action["id"],
                "label": action["label"],
                "status": status,
                "missing_fields": sorted({f for c in checks for f in c["missing_fields"]}),
                "evidence": action.get("evidence", []),
                "preview_state": updated if status == "satisfied" else None,
            }
        )
    return {"status": "satisfied", "candidates": candidates, "state": checked["state"]}
