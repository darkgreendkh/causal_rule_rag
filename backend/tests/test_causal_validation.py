from copy import deepcopy

import pytest
from test_workflow import fixture

from app.causal_validation import validate_path


def case():
    corpus, request = fixture()
    request.pop("steps")
    nodes = [{"id": a["id"], "type": "ACTION", "matter_id": "m"} for a in corpus["actions"]]
    nodes += [{"id": r["id"], "type": "RULE", "matter_id": "m"} for r in corpus["rules"]]
    return corpus, request, nodes


def path(*ids):
    return {"node_ids": list(ids), "rule_ids": [], "evidence": []}


def test_path_replays_prepare_then_submit_without_mutating_inputs():
    corpus, request, nodes = case()
    original = deepcopy((corpus, request, nodes))
    result = validate_path(corpus, request, path("prepare", "submit"), nodes)
    assert result["status"] == "satisfied"
    assert result["state"]["ready"] is True
    assert result["state"]["sent"] is True
    assert result["completed_steps"] == ["prepare", "submit"]
    assert result["first_blocked_node"] is None
    assert (corpus, request, nodes) == original


def test_missing_prefix_is_unknown_but_known_age_failure_remains_violated():
    corpus, request, nodes = case()
    result = validate_path(corpus, request, path("submit"), nodes)
    assert result["status"] == "unknown"
    assert result["first_blocked_node"] == "submit"
    assert result["state"]["sent"] is False
    assert any("prepare" in gap for gap in result["knowledge_gaps"])
    request["facts"]["age"] = 17
    assert validate_path(corpus, request, path("submit"), nodes)["status"] == "violated"


def test_known_history_is_preserved_as_completed_information():
    corpus, request, nodes = case()
    request["completed_steps"] = ["prepare"]
    result = validate_path(corpus, request, path("submit"), nodes)
    assert result["status"] == "satisfied"
    assert result["completed_steps"] == ["prepare", "submit"]
    assert request["completed_steps"] == ["prepare"]


def test_unknown_external_action_stops_effects_and_marks_suffix_unverified():
    corpus, request, nodes = case()
    corpus["actions"].append(
        dict(
            corpus["actions"][0],
            id="finish",
            preconditions={"completed": "approve"},
            effects={"ready": False},
        )
    )
    nodes.append({"id": "finish", "type": "ACTION", "matter_id": "m"})
    result = validate_path(corpus, request, path("prepare", "submit", "approve", "finish"), nodes)
    assert result["status"] == "unknown"
    assert result["first_blocked_node"] == "approve"
    assert "approved" not in result["state"]
    assert result["state"]["ready"] is True
    assert result["completed_steps"] == ["prepare", "submit"]
    assert any(
        c["node_id"] == "finish" and c["status"] == "unknown" and c.get("deferred")
        for c in result["checks"]
    )


def test_rule_nodes_use_current_state_and_return_all_and_evidence():
    corpus, request, nodes = case()
    evidence = [{"unit_id": "form", "quote": "填表"}, {"unit_id": "other", "quote": "附材料"}]
    corpus["rules"].append(
        dict(
            corpus["rules"][0],
            id="ready_rule",
            action_id="submit",
            condition={"all": [{"field": "ready"}, {"completed": "prepare"}]},
            evidence=evidence,
        )
    )
    nodes.append({"id": "ready_rule", "type": "RULE", "matter_id": "m"})
    result = validate_path(corpus, request, path("prepare", "ready_rule", "submit"), nodes)
    assert result["status"] == "satisfied"
    assert {e["unit_id"] for e in result["required_evidence"]} == {"u", "form", "other"}
    assert any(
        c["node_id"] == "ready_rule" and c["status"] == "satisfied" for c in result["checks"]
    )


@pytest.mark.parametrize(
    "condition,status",
    [
        ({"all": [{"completed": "prepare"}, {"value": False}]}, "violated"),
        ({"any": [{"completed": "prepare"}, {"value": True}]}, "satisfied"),
        ({"not": {"completed": "prepare"}}, "unknown"),
    ],
)
def test_unknown_prefix_uses_three_valued_logic(condition, status):
    corpus, request, nodes = case()
    corpus["actions"][1]["preconditions"] = condition
    assert validate_path(corpus, request, path("submit"), nodes)["status"] == status


def test_typed_facts_policy_protection_and_external_confirmation_are_reused():
    corpus, request, nodes = case()
    request["facts"].update(age="21", minimum=0)
    result = validate_path(corpus, request, path("prepare", "submit"), nodes)
    assert result["status"] == "unknown"
    assert result["state"]["minimum"] == 18
    request["facts"].update(age=21, approved=True)
    result = validate_path(corpus, request, path("prepare", "submit", "approve"), nodes)
    assert result["status"] == "satisfied"
    assert result["state"]["approved"] is True


def test_condition_leaf_checks_whole_owner_rule():
    corpus, request, nodes = case()
    corpus["rules"][0]["condition"] = {"all": [corpus["rules"][0]["condition"], {"field": "ready"}]}
    nodes.append(
        {
            "id": "age_leaf",
            "type": "CONDITION",
            "matter_id": "m",
            "owner_id": "adult",
            "condition": {"op": "gte", "left": {"field": "age"}, "right": {"value": 18}},
        }
    )
    assert validate_path(corpus, request, path("age_leaf"), nodes)["status"] == "unknown"


def test_macro_action_is_structural_and_does_not_block_micro_replay():
    corpus, request, nodes = case()
    nodes.append({"id": "macro_prepare", "type": "ACTION", "layer": "macro", "matter_id": "m"})
    result = validate_path(corpus, request, path("macro_prepare", "prepare", "submit"), nodes)
    assert result["status"] == "satisfied"
    assert result["completed_steps"] == ["prepare", "submit"]


def test_known_history_does_not_reapply_effects_when_retrieved_again():
    corpus, request, nodes = case()
    request["completed_steps"] = ["prepare"]
    request["facts"]["ready"] = False
    result = validate_path(corpus, request, path("prepare", "submit"), nodes)
    assert result["status"] == "satisfied"
    assert result["state"]["ready"] is False


def test_rule_only_reference_infers_matter_without_request_matter():
    corpus, request, nodes = case()
    request.pop("matter_id")
    result = validate_path(corpus, request, dict(path(), rule_ids=["adult"]), nodes)
    assert result["status"] == "satisfied"
    assert result["state"]["minimum"] == 18
