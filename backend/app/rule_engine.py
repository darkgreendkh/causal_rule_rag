"""A bounded, JSON-only expression language with strong Kleene truth values."""

import math
import operator
import re
from datetime import date
from functools import reduce

COMPARISONS = {
    "eq": operator.eq,
    "ne": operator.ne,
    "gt": operator.gt,
    "gte": operator.ge,
    "lt": operator.lt,
    "lte": operator.le,
}
ARITHMETIC = {"add", "sub", "mul", "div", "min", "max"}
UNKNOWN = object()


def _number(value):
    return type(value) in (int, float) and math.isfinite(value)


def validate_expression(expression: dict, field_ids: set[str] | None) -> list[str]:
    errors = []
    count = 0

    def visit(node, depth=0):
        nonlocal count
        count += 1
        if depth > 64 or count > 2048:
            errors.append("表达式超过深度或节点限制")
            return
        if not isinstance(node, dict):
            errors.append("表达式必须是对象")
            return
        keys = set(node)
        if keys == {"value"}:
            value = node["value"]
            values = value if isinstance(value, list) else [value]
            if not all(v is None or type(v) in (str, bool) or _number(v) for v in values):
                errors.append("常量只能是有限数值、布尔、字符串、null或其数组")
        elif keys in ({"field"}, {"completed"}):
            key = next(iter(keys))
            value = node[key]
            if not isinstance(value, str) or not value:
                errors.append(f"{key}必须是非空字符串")
            elif key == "field" and field_ids is not None and value not in field_ids:
                errors.append(f"未声明字段：{value}")
        elif keys in ({"all"}, {"any"}):
            children = node[next(iter(keys))]
            if not isinstance(children, list) or not children:
                errors.append("布尔组合必须是非空表达式数组")
            else:
                for child in children:
                    visit(child, depth + 1)
        elif keys == {"not"}:
            visit(node["not"], depth + 1)
        elif keys == {"op", "left", "right"} and node["op"] in (*COMPARISONS, "in", "contains"):
            visit(node["left"], depth + 1)
            visit(node["right"], depth + 1)
        elif keys == {"op", "args"} and isinstance(node["op"], str) and node["op"] in ARITHMETIC:
            args = node["args"]
            if (
                not isinstance(args, list)
                or not args
                or (node["op"] in {"sub", "div"} and len(args) != 2)
            ):
                errors.append("算术参数数量错误")
            else:
                for child in args:
                    visit(child, depth + 1)
        else:
            errors.append("不支持的表达式结构或操作符")

    visit(expression)
    return list(dict.fromkeys(errors))


def evaluate(expression: dict, facts: dict, completed: list[str] | None = None) -> dict:
    errors = validate_expression(expression, None)
    if errors:
        return {"status": "unknown", "missing_fields": [], "reasons": errors}

    def read(node):
        if "value" in node:
            return node["value"], set(), []
        if "field" in node:
            key = node["field"]
            if key not in facts or facts[key] is None:
                return UNKNOWN, {key}, [f"缺少字段：{key}"]
            return facts[key], set(), []
        if "completed" in node:
            return node["completed"] in (completed or []), set(), []
        if "not" in node:
            value, missing, reasons = truth(node["not"])
            return (not value if value is not UNKNOWN else UNKNOWN), missing, reasons
        if "all" in node or "any" in node:
            key = "all" if "all" in node else "any"
            results = [truth(child) for child in node[key]]
            decisive = key != "all"
            if any(value is decisive for value, _, _ in results):
                return decisive, set(), []
            if any(value is UNKNOWN for value, _, _ in results):
                return (
                    UNKNOWN,
                    set().union(*(r[1] for r in results)),
                    [reason for result in results for reason in result[2]],
                )
            return not decisive, set(), []
        op = node["op"]
        results = [
            read(child)
            for child in (node["args"] if op in ARITHMETIC else [node["left"], node["right"]])
        ]
        values = [r[0] for r in results]
        missing = set().union(*(r[1] for r in results))
        reasons = [reason for result in results for reason in result[2]]
        if any(value is UNKNOWN or value is None for value in values):
            return UNKNOWN, missing, reasons or ["值未知"]
        try:
            if op in ARITHMETIC:
                if not all(_number(value) for value in values):
                    raise ValueError("算术操作需要有限数值")
                if op == "add":
                    value = sum(values)
                elif op == "mul":
                    value = reduce(operator.mul, values, 1)
                elif op == "sub":
                    value = values[0] - values[1]
                elif op == "div":
                    value = values[0] / values[1]
                else:
                    value = (min if op == "min" else max)(values)
                if not _number(value):
                    raise ValueError("算术结果不是有限数值")
            else:
                left, right = values
                if op in {"in", "contains"}:
                    item, collection = (left, right) if op == "in" else (right, left)
                    if not isinstance(collection, (list, str)) or (
                        isinstance(collection, str) and not isinstance(item, str)
                    ):
                        raise ValueError("包含操作的类型不匹配")
                    value = (
                        item in collection
                        if isinstance(collection, str)
                        else any(
                            (type(item) is type(member) or (_number(item) and _number(member)))
                            and item == member
                            for member in collection
                        )
                    )
                else:
                    if not (type(left) is type(right) or (_number(left) and _number(right))):
                        raise ValueError("比较值的类型不匹配")
                    if (
                        isinstance(left, str)
                        and isinstance(right, str)
                        and (
                            re.fullmatch(r"\d{4}-\d{2}-\d{2}", left)
                            or re.fullmatch(r"\d{4}-\d{2}-\d{2}", right)
                        )
                    ):
                        left, right = date.fromisoformat(left), date.fromisoformat(right)
                    value = COMPARISONS[op](left, right)
            return value, missing, reasons
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            return UNKNOWN, missing, [f"无法求值：{exc}"]

    def truth(node):
        value, missing, reasons = read(node)
        if value is not UNKNOWN and type(value) is not bool:
            return UNKNOWN, missing, ["条件必须产生布尔值"]
        return value, missing, reasons

    value, missing, reasons = truth(expression)
    status = "unknown" if value is UNKNOWN else "satisfied" if value else "violated"
    return {
        "status": status,
        "missing_fields": sorted(missing),
        "reasons": list(dict.fromkeys(reasons)) or (["条件不满足"] if status == "violated" else []),
    }
