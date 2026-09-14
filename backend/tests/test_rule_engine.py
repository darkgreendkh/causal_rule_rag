import pytest

from app.rule_engine import evaluate, validate_expression


@pytest.mark.parametrize(
    "expression",
    [
        {"field": "missing"},
        {"value": True, "field": "age"},
        {"op": "python", "args": []},
        {"all": []},
        {"any": "age"},
        {"not": {}},
        {"completed": 2},
        {"value": {"code": "x"}},
        {"op": "div", "args": [{"value": 1}]},
        {"op": "eq", "left": {"field": "age"}},
    ],
)
def test_rejects_unrestricted_or_malformed_expressions(expression):
    assert validate_expression(expression, {"age"})


@pytest.mark.parametrize(
    "expression,facts,status,missing",
    [
        ({"field": "ready"}, {}, "unknown", ["ready"]),
        ({"all": [{"value": False}, {"field": "ready"}]}, {}, "violated", []),
        ({"any": [{"value": True}, {"field": "ready"}]}, {}, "satisfied", []),
        ({"all": [{"value": True}, {"field": "ready"}]}, {}, "unknown", ["ready"]),
        ({"any": [{"value": False}, {"field": "ready"}]}, {}, "unknown", ["ready"]),
        ({"not": {"field": "ready"}}, {}, "unknown", ["ready"]),
        ({"not": {"field": "ready"}}, {"ready": False}, "satisfied", []),
        ({"field": "ready"}, {"ready": "false"}, "unknown", []),
    ],
)
def test_three_valued_boolean_logic(expression, facts, status, missing):
    result = evaluate(expression, facts)
    assert result["status"] == status
    assert result["missing_fields"] == missing


@pytest.mark.parametrize(
    "op,args,expected",
    [
        ("add", [3, 4], 7),
        ("sub", [7, 3], 4),
        ("mul", [3, 4], 12),
        ("div", [12, 4], 3),
        ("min", [3, 4, 2], 2),
        ("max", [3, 4, 2], 4),
    ],
)
def test_arithmetic(op, args, expected):
    expression = {
        "op": "eq",
        "left": {"op": op, "args": [{"value": x} for x in args]},
        "right": {"value": expected},
    }
    assert not validate_expression(expression, set())
    assert evaluate(expression, {})["status"] == "satisfied"


@pytest.mark.parametrize(
    "left,right,op,status",
    [
        ("2024-02-29", "2024-03-01", "lt", "satisfied"),
        ("2024-02-30", "2024-03-01", "lt", "unknown"),
        (True, 1, "eq", "unknown"),
        ("18", 18, "gte", "unknown"),
        ("武汉", ["武汉", "湖北"], "in", "satisfied"),
        (["甲", "乙"], "乙", "contains", "satisfied"),
    ],
)
def test_typed_comparison_and_dates(left, right, op, status):
    assert (
        evaluate({"op": op, "left": {"value": left}, "right": {"value": right}}, {})["status"]
        == status
    )


def test_division_by_zero_is_unknown_and_completed_uses_history():
    expr = {
        "op": "gt",
        "left": {"op": "div", "args": [{"value": 1}, {"value": 0}]},
        "right": {"value": 0},
    }
    assert evaluate(expr, {})["status"] == "unknown"
    assert evaluate({"completed": "submit"}, {}, ["submit"])["status"] == "satisfied"
    assert evaluate({"completed": "submit"}, {})["status"] == "violated"


def test_expression_nesting_is_bounded():
    expression = {"value": True}
    for _ in range(100):
        expression = {"not": expression}
    assert validate_expression(expression, set())


@pytest.mark.parametrize(
    "op,left,right,status",
    [
        ("eq", 2, 2, "satisfied"),
        ("ne", 2, 2, "violated"),
        ("gt", 3, 2, "satisfied"),
        ("gte", 2, 2, "satisfied"),
        ("lt", 2, 3, "satisfied"),
        ("lte", 3, 3, "satisfied"),
        ("eq", None, None, "unknown"),
        ("contains", "abc", "b", "satisfied"),
        ("in", True, [1], "violated"),
    ],
)
def test_comparisons_preserve_types(op, left, right, status):
    result = evaluate({"op": op, "left": {"value": left}, "right": {"value": right}}, {})
    assert result["status"] == status


def test_nonfinite_arithmetic_inputs_and_result_are_unknown():
    expression = {
        "op": "eq",
        "left": {"op": "mul", "args": [{"field": "x"}, {"value": 10}]},
        "right": {"value": 1},
    }
    assert evaluate(expression, {"x": float("inf")})["status"] == "unknown"
    assert evaluate(expression, {"x": 1e308})["status"] == "unknown"


def test_large_finite_integers_do_not_require_float_conversion():
    expression = {"op": "gt", "left": {"field": "x"}, "right": {"value": 10**400}}
    assert not validate_expression(expression, {"x"})
    assert evaluate(expression, {"x": 10**401})["status"] == "satisfied"
