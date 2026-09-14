from copy import deepcopy
from itertools import product

from app.workflow import check_workflow, next_steps, repair_workflow


def fixture():
    fields = [
        {"id": name, "label": name, "type": kind, "role": role, "mutable": mutable}
        for name, kind, role, mutable in [
            ("age", "number", "applicant", False),
            ("minimum", "number", "policy", False),
            ("ready", "boolean", "applicant", True),
            ("sent", "boolean", "applicant", True),
            ("approved", "boolean", "external", False),
        ]
    ]
    actions = [
        {"id": "prepare", "preconditions": {"value": True}, "effects": {"ready": True}},
        {"id": "submit", "preconditions": {"completed": "prepare"}, "effects": {"sent": True}},
        {
            "id": "approve",
            "kind": "external",
            "preconditions": {"completed": "submit"},
            "effects": {"approved": True},
        },
    ]
    for action in actions:
        action.update(matter_id="m", label=action["id"], evidence=[])
        action.setdefault("kind", "user")
    rule = {
        "id": "adult",
        "matter_id": "m",
        "label": "成年",
        "action_id": None,
        "status": "active",
        "condition": {"op": "gte", "left": {"field": "age"}, "right": {"field": "minimum"}},
        "scope": {
            "region": "湖北",
            "valid_from": "2020-01-01",
            "valid_to": "2030-12-31",
            "validity_known": True,
        },
        "evidence": [{"unit_id": "u", "quote": "申请人已成年"}],
    }
    matter = {
        "id": "m",
        "fields": fields,
        "policy_parameters": {"minimum": 18},
        "action_ids": [a["id"] for a in actions],
        "rule_ids": ["adult"],
        "gaps": [],
        "goals": [{"id": "sent", "label": "提交", "condition": {"field": "sent"}}],
    }
    corpus = {"matters": [matter], "actions": actions, "rules": [rule]}
    request = {
        "matter_id": "m",
        "region": "武汉",
        "as_of": "2025-01-01",
        "facts": {"age": 21, "sent": False},
        "steps": ["prepare", "submit"],
        "goal": "sent",
    }
    return corpus, request


def test_replay_applies_effects_in_order_without_mutating_inputs():
    corpus, request = fixture()
    original = deepcopy((corpus, request))
    checked = check_workflow(corpus, request)
    assert checked["status"] == "satisfied"
    assert checked["state"]["sent"] is True
    assert checked["completed_steps"] == ["prepare", "submit"]
    assert checked["checks"][0]["evidence"][0]["unit_id"] == "u"
    assert (corpus, request) == original
    request["steps"].reverse()
    checked = check_workflow(corpus, request)
    assert checked["status"] == "violated"
    assert checked["first_error"]["index"] == 0
    assert checked["state"]["sent"] is False


def test_policy_facts_cannot_be_overridden():
    corpus, request = fixture()
    request["facts"].update(age=17, minimum=0)
    checked = check_workflow(corpus, request)
    assert checked["status"] == "violated"
    assert checked["state"]["minimum"] == 18


def test_scope_and_missing_information_are_not_applicant_errors():
    corpus, request = fixture()
    del request["facts"]["age"]
    checked = check_workflow(corpus, request)
    assert checked["status"] == "unknown"
    assert "age" in checked["missing_fields"]
    request["facts"]["age"] = 21
    for change in ({"region": "北京"}, {"as_of": "2031-01-01"}, {"as_of": None}):
        checked = check_workflow(corpus, dict(request, **change))
        assert checked["status"] == "unknown"
        assert checked["knowledge_gaps"]
    corpus["rules"][0]["scope"]["validity_known"] = False
    assert check_workflow(corpus, request)["status"] == "unknown"


def test_external_approval_requires_original_confirmed_fact():
    corpus, request = fixture()
    request["steps"].append("approve")
    assert check_workflow(corpus, request)["status"] == "unknown"
    request["facts"]["approved"] = True
    assert check_workflow(corpus, request)["status"] == "satisfied"
    corpus["actions"][0]["effects"]["approved"] = True
    del request["facts"]["approved"]
    checked = check_workflow(corpus, request)
    assert checked["status"] == "violated"
    assert "approved" not in checked["state"]


def test_actions_cannot_change_immutable_applicant_facts():
    corpus, request = fixture()
    corpus["actions"][0]["effects"]["age"] = 25
    checked = check_workflow(corpus, request)
    assert checked["status"] == "violated"
    assert checked["state"]["age"] == 21


def test_history_is_replayed_and_never_repaired():
    corpus, request = fixture()
    request.update(completed_steps=["prepare"], steps=["submit"])
    result = repair_workflow(corpus, request)
    assert result["status"] == "already_valid"
    assert result["checked"]["completed_steps"] == ["prepare", "submit"]
    request.update(completed_steps=["submit"], steps=["prepare"])
    result = repair_workflow(corpus, request)
    assert result["status"] == "unreachable"
    assert result["steps"] == ["prepare"]
    assert result["edits"] == []
    assert request["completed_steps"] == ["submit"]


def test_repair_inserts_required_predecessor_and_preview_is_nonmutating():
    corpus, request = fixture()
    request["steps"] = ["submit"]
    result = repair_workflow(corpus, request)
    assert result["status"] == "repaired"
    assert result["cost"] == 1
    assert result["steps"] == ["prepare", "submit"]
    request["steps"] = []
    original = deepcopy(request)
    candidates = next_steps(corpus, request)["candidates"]
    prepare = next(c for c in candidates if c["action_id"] == "prepare")
    assert prepare["status"] == "satisfied"
    assert prepare["preview_state"]["ready"] is True
    assert request == original


def edit_distance(a, b):
    row = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        previous, row = row, [i]
        for j, y in enumerate(b, 1):
            row.append(min(previous[j] + 1, row[-1] + 1, previous[j - 1] + (x != y)))
    return row[-1]


def test_repair_matches_exhaustive_minimum_for_all_short_sequences():
    corpus, request = fixture()
    corpus["actions"] = corpus["actions"][:2]
    for length in range(4):
        for sequence in product(["prepare", "submit", "invalid"], repeat=length):
            request["steps"] = list(sequence)
            result = repair_workflow(corpus, request)
            # Every legal sequence contains prepare before its first submit; repeats are allowed.
            costs = [
                edit_distance(sequence, candidate)
                for size in range(2, 6)
                for candidate in product(["prepare", "submit"], repeat=size)
                if candidate[0] == "prepare" and "submit" in candidate
            ]
            assert result["cost"] == min(costs), sequence
            assert result["checked"]["status"] == "satisfied"


def test_repair_distinguishes_unknown_unreachable_and_truncation():
    corpus, request = fixture()
    request["steps"] = ["submit"]
    assert repair_workflow(corpus, request, max_states=1)["status"] == "truncated"
    request["facts"]["age"] = 17
    assert repair_workflow(corpus, request)["status"] == "unreachable"
    del request["facts"]["age"]
    assert repair_workflow(corpus, request)["status"] == "unknown"


def test_action_scoped_rules_apply_at_the_action_position():
    corpus, request = fixture()
    corpus["rules"][0].update(action_id="submit", condition={"completed": "prepare"})
    assert check_workflow(corpus, request)["status"] == "satisfied"
    request["steps"] = ["submit"]
    assert check_workflow(corpus, request)["first_error"]["index"] == 0


def test_candidate_action_rule_is_not_silently_ignored():
    corpus, request = fixture()
    corpus["rules"].append(
        dict(corpus["rules"][0], id="review_pending", action_id="submit", status="candidate")
    )
    assert check_workflow(corpus, request)["status"] == "unknown"


def test_invalid_fact_types_and_invalid_expression_do_not_satisfy_workflow():
    corpus, request = fixture()
    request["facts"]["age"] = "21"
    checked = check_workflow(corpus, request)
    assert checked["status"] == "unknown"
    assert "age" in checked["missing_fields"]
    request["facts"]["age"] = 21
    corpus["actions"][0]["preconditions"] = {"python": "True"}
    assert check_workflow(corpus, request)["status"] == "unknown"


def test_repair_cannot_manufacture_missing_approval_or_modify_policy():
    corpus, request = fixture()
    corpus["matters"][0]["goals"].append({"id": "approved", "condition": {"field": "approved"}})
    request["goal"] = "approved"
    result = repair_workflow(corpus, request)
    assert result["status"] == "unknown"
    assert result["cost"] is None
    assert result["edits"] == []
    corpus["actions"][0]["effects"]["minimum"] = 0
    assert check_workflow(corpus, request)["state"]["minimum"] == 18


def test_large_finite_integer_fact_does_not_crash_validation():
    corpus, request = fixture()
    request["facts"]["age"] = 10**400
    assert check_workflow(corpus, request)["status"] == "satisfied"


def test_disabled_necessary_action_rule_cannot_be_bypassed_by_global_rule():
    corpus, request = fixture()
    corpus["rules"].append(
        dict(corpus["rules"][0], id="specific", action_id="submit", status="disabled")
    )
    checked = check_workflow(corpus, request)
    assert checked["status"] == "unknown"
    assert checked["knowledge_gaps"]
    assert checked["state"]["sent"] is False


def test_rejected_candidate_does_not_block_remaining_active_action_support():
    corpus, request = fixture()
    specific = dict(corpus["rules"][0], id="specific", action_id="submit")
    corpus["rules"].extend([specific, dict(specific, id="candidate", status="rejected")])
    assert check_workflow(corpus, request)["status"] == "satisfied"
    specific["status"] = "rejected"
    assert check_workflow(corpus, request)["status"] == "unknown"


def test_condition_check_rule_allows_preparation_but_still_guards_submission():
    corpus, request = fixture()
    corpus["rules"][0].update(action_id="submit", purpose="condition_check")
    request.update(steps=["prepare"], goal=None)
    request["facts"]["age"] = 17
    assert check_workflow(corpus, request)["status"] == "satisfied"
    request["steps"].append("submit")
    assert check_workflow(corpus, request)["status"] == "violated"
    request["steps"] = []
    assert check_workflow(corpus, request)["status"] == "violated"
    candidates = next_steps(corpus, request)["candidates"]
    assert next(c for c in candidates if c["action_id"] == "prepare")["status"] == "satisfied"


def test_repair_base_does_not_apply_submission_checks_before_preparation():
    corpus, request = fixture()
    rule = corpus["rules"][0]
    rule.update(
        action_id="submit",
        purpose="condition_check",
        condition={"all": [rule["condition"], {"field": "ready"}]},
    )
    request["facts"]["ready"] = False
    request["steps"] = []
    assert check_workflow(corpus, request)["status"] == "violated"
    result = repair_workflow(corpus, request)
    assert result["status"] == "repaired"
    assert result["steps"] == ["prepare", "submit"]
    assert result["cost"] == 2


def test_repair_does_not_report_a_failed_empty_fact_check_as_repaired():
    corpus, request = fixture()
    corpus["rules"][0].update(action_id="submit", purpose="condition_check")
    request["facts"]["age"] = 17
    request.update(steps=["submit"], goal=None)
    result = repair_workflow(corpus, request)
    assert result["checked"]["status"] == "satisfied"
    assert result["steps"] == ["prepare"]


def test_deleted_predecessor_is_a_knowledge_gap_not_an_applicant_error():
    corpus, request = fixture()
    corpus["actions"] = [a for a in corpus["actions"] if a["id"] != "prepare"]
    request["steps"] = ["submit"]
    checked = check_workflow(corpus, request)
    assert checked["status"] == "unknown"
    assert any("prepare" in gap for gap in checked["knowledge_gaps"])
    assert repair_workflow(corpus, request)["status"] == "unknown"
