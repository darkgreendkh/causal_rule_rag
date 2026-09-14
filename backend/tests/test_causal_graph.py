import math
from copy import deepcopy

import pytest

from app.causal_graph import assign_communities, build_graph, path_candidates, rpc_score, scs_score
from app.research_profiles import get_profile


def test_scores_are_recomputable_and_reject_conflicting_scopes():
    assert rpc_score(1, 0.5, 0) == 0.5
    assert scs_score(0.8, 1, 1) == pytest.approx(0.9)
    assert scs_score(1, 1, 1, compatible=False) == 0


def test_must_link_groups_stay_together_after_community_assignment():
    nodes = [{"id": str(i), "label": str(i), "layer": "micro"} for i in range(5)]
    edges = [
        {"source": "0", "target": "1", "type": "REQUIRES", "rpc": 1},
        {"source": "1", "target": "2", "type": "PRODUCES", "rpc": 1},
        {"source": "2", "target": "3", "type": "RELATED", "rpc": 0.2},
        {"source": "3", "target": "4", "type": "RELATED", "rpc": 0.2},
    ]
    for edge in edges:
        edge["status"] = "active"
    groups = assign_communities(nodes, edges, get_profile("full"))
    assert nodes[0]["community_id"] == nodes[1]["community_id"] == nodes[2]["community_id"]
    assert groups


def test_paths_respect_direction_and_scoring_and_candidate_limit():
    nodes = [{"id": x, "label": x, "layer": "micro"} for x in "abcd"]
    edges = [
        {"id": "ab", "source": "a", "target": "b", "type": "REQUIRES", "rpc": 1, "evidence": []},
        {"id": "bc", "source": "b", "target": "c", "type": "PRODUCES", "rpc": 1, "evidence": []},
        {"id": "bd", "source": "b", "target": "d", "type": "PRODUCES", "rpc": 1, "evidence": []},
    ]
    result = path_candidates(nodes, edges, {x: 1.0 for x in "abcd"}, ["a"], get_profile("full"))
    assert any(p["node_ids"] == ["a", "b", "c"] for p in result)
    assert not any(p["node_ids"] == ["c", "b", "a"] for p in result)
    assert all(math.isfinite(p["score"]) and 0 <= p["entropy"] <= 1 for p in result)
    profile = get_profile("full")
    profile["max_candidates"] = 1
    assert len(path_candidates(nodes, edges, {x: 1.0 for x in "abcd"}, ["a"], profile)) == 1


def graph_corpus():
    evidence = [{"unit_id": "u1", "quote": "年满十六周岁并提供申请表"}]
    corpus = {
        "documents": [{"id": "d1", "filename": "政策"}],
        "units": [
            {
                "id": "u1",
                "document_id": "d1",
                "title": "政策",
                "article": "第一条",
                "text": evidence[0]["quote"],
                "region": "湖北",
                "valid_from": "2020-01-01",
                "valid_to": "2025-12-31",
                "validity_known": True,
            }
        ],
        "matters": [
            {
                "id": "m1",
                "name": "参保",
                "source_unit_ids": ["u1"],
                "fields": [
                    {"id": "age", "label": "年龄", "type": "number", "role": "applicant"},
                    {"id": "form", "label": "申请表", "type": "boolean", "role": "applicant"},
                    {"id": "materials", "label": "申请材料", "type": "set", "role": "applicant"},
                    {
                        "id": "submitted",
                        "label": "已提交",
                        "type": "boolean",
                        "role": "applicant",
                        "mutable": True,
                    },
                ],
            }
        ],
        "rules": [
            {
                "id": "r1",
                "matter_id": "m1",
                "label": "资格",
                "condition": {
                    "all": [
                        {"op": "gte", "left": {"field": "age"}, "right": {"value": 16}},
                        {"op": "eq", "left": {"field": "form"}, "right": {"value": True}},
                    ]
                },
                "action_id": "a1",
                "evidence": evidence,
                "status": "active",
                "scope": {
                    "region": "湖北",
                    "valid_from": "2020-01-01",
                    "valid_to": "2025-12-31",
                    "validity_known": True,
                },
            }
        ],
        "actions": [
            {
                "id": "a1",
                "matter_id": "m1",
                "label": "提交申请",
                "preconditions": {"value": True},
                "effects": {"submitted": True},
                "evidence": evidence,
                "kind": "user",
            }
        ],
    }
    return corpus


def test_graph_preserves_each_and_condition_and_evidence():
    corpus = graph_corpus()
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 0.9})
    requires = [e for e in graph["edges"] if e["type"] == "REQUIRES"]
    assert len(requires) >= 2
    assert all(e["evidence"] for e in requires)
    assert any(e["type"] == "PRODUCES" for e in graph["edges"])
    without = build_graph(corpus, get_profile("without_micro"))
    assert all(n["layer"] == "macro" for n in without["nodes"])


def test_rpc_reports_actual_scope_and_expression_components():
    corpus = graph_corpus()
    baseline = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    rule = next(n for n in baseline["nodes"] if n["id"] == "r1")
    assert rule["rpc_components"] == {"coverage": 1, "continuity": 1, "temporal": 1}
    corpus["rules"][0]["condition"] = {"field": "undeclared"}
    invalid = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    assert not any(n["id"] == "r1" for n in invalid["nodes"])
    ablated = build_graph(corpus, get_profile("without_rpc"), {("u1", "r1"): 1})
    rule = next(n for n in ablated["nodes"] if n["id"] == "r1")
    assert rule["rpc_components"]["continuity"] == 0


@pytest.mark.parametrize(
    "scope",
    [
        {"region": "北京", "valid_from": "2020-01-01", "valid_to": "2025-12-31"},
        {"region": "湖北", "valid_from": "2030-01-01", "valid_to": "2035-12-31"},
    ],
)
def test_conflicting_scope_never_fuses_even_without_scs(scope):
    corpus = graph_corpus()
    corpus["rules"][0]["scope"] = scope
    profile = get_profile("without_scs")
    profile["rpc"] = False
    graph = build_graph(corpus, profile, {("u1", "r1"): 1})
    assert not any(e["source"] == "u1" and e["target"] == "r1" for e in graph["edges"])


def test_missing_semantic_similarity_does_not_invent_a_perfect_match():
    corpus = graph_corpus()
    full = build_graph(corpus, get_profile("full"))
    assert not any(e["type"] == "REALIZES" and e["target"] == "r1" for e in full["edges"])
    ablated = build_graph(corpus, get_profile("without_scs"))
    cross = next(e for e in ablated["edges"] if e["source"] == "u1" and e["target"] == "r1")
    assert cross["scs_components"]["semantic"] == 0
    assert cross["semantic_weight"] == 0


def test_historical_unknown_current_validity_is_not_a_structural_conflict():
    corpus = graph_corpus()
    corpus["units"][0]["validity_known"] = False
    corpus["rules"][0]["scope"]["validity_known"] = False
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    assert any(e["source"] == "u1" and e["target"] == "r1" for e in graph["edges"])


def test_action_preconditions_and_not_have_directed_evidence_edges():
    corpus = graph_corpus()
    corpus["rules"].append(
        dict(
            corpus["rules"][0],
            id="global",
            action_id=None,
            condition=corpus["rules"][0]["condition"]["all"][0],
        )
    )
    corpus["actions"].append(
        dict(
            corpus["actions"][0],
            id="a2",
            preconditions={"all": [{"completed": "a1"}, {"not": {"field": "form"}}]},
        )
    )
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    conditions = [n for n in graph["nodes"] if n.get("owner_id") == "a2"]
    preceding = next(n for n in conditions if n.get("condition") == {"completed": "a1"})
    assert any(
        e["source"] == "a1" and e["target"] == preceding["id"] and e["type"] == "PRECEDES"
        for e in graph["edges"]
    )
    assert any(
        e["target"] == "a2" and e["type"] == "EXCEPTS" and e["evidence"] for e in graph["edges"]
    )
    assert any(n["layer"] == "macro" and n["type"] == "PERSON_ROLE" for n in graph["nodes"])
    assert any(n["layer"] == "macro" and n["type"] == "MATERIAL" for n in graph["nodes"])
    assert any(n["layer"] == "macro" and n["type"] == "ACTION" for n in graph["nodes"])


def test_cyclic_action_predecessors_are_not_strong_causal_constraints():
    corpus = graph_corpus()
    corpus["actions"][0]["preconditions"] = {"completed": "a2"}
    corpus["actions"].append(dict(corpus["actions"][0], id="a2", preconditions={"completed": "a1"}))
    graph = build_graph(corpus, get_profile("without_rpc"), {("u1", "r1"): 1})
    causal = [e for e in graph["edges"] if e["type"] in {"PRECEDES", "PRODUCES"}]
    assert causal
    assert all(not e["compatible"] for e in causal)
    assert all(e["rpc_components"]["temporal"] == 0 for e in causal)


def test_disabled_rules_do_not_create_must_link_groups():
    nodes = [{"id": str(i), "label": str(i), "layer": "micro"} for i in range(2)]
    edges = [
        {
            "source": "0",
            "target": "1",
            "type": "REQUIRES",
            "rpc": 1,
            "status": "disabled",
            "compatible": True,
        }
    ]
    profile = get_profile("full")
    profile["resolution"] = 10
    groups = assign_communities(nodes, edges, profile)
    assert all(not g["unsplittable"] for g in groups)
    assert nodes[0]["community_id"] != nodes[1]["community_id"]


def test_hierarchy_keeps_must_links_and_reports_real_parent_membership():
    nodes = [{"id": str(i), "label": str(i), "layer": "micro"} for i in range(10)]
    edges = [
        {"source": str(i), "target": str(j), "type": "RELATED", "rpc": 0.1}
        for i in range(10)
        for j in range(i + 1, 10)
    ]
    edges.append(
        {
            "source": "0",
            "target": "1",
            "type": "REQUIRES",
            "rpc": 1,
            "status": "active",
            "compatible": True,
        }
    )
    profile = get_profile("full")
    profile["resolution"] = 0.1
    groups = assign_communities(nodes, edges, profile)
    assert nodes[0]["community_ids"] == nodes[1]["community_ids"]
    for group in groups:
        if group["parent_id"]:
            parent = next(g for g in groups if g["id"] == group["parent_id"])
            assert set(group["node_ids"]) <= set(parent["node_ids"])


def test_graph_build_does_not_mutate_the_corpus():
    corpus = graph_corpus()
    original = deepcopy(corpus)
    build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    assert corpus == original


def test_candidate_without_expression_is_retained_as_nonexecutable_knowledge():
    corpus = graph_corpus()
    corpus["rules"][0].update(condition=None, status="candidate")
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    rule = next(n for n in graph["nodes"] if n["id"] == "r1")
    assert rule["knowledge_gaps"]
    assert not rule["required_condition_ids"]
    assert not any(
        e["source"] == "r1" and e["type"] in {"REQUIRES", "PRECEDES", "PRODUCES"}
        for e in graph["edges"]
    )


def test_rule_continuity_checks_linked_action_effect_fields():
    corpus = graph_corpus()
    corpus["actions"][0]["effects"] = {"undeclared": True}
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    assert not any(n["id"] == "r1" for n in graph["nodes"])
    assert not any(e["type"] == "PRODUCES" for e in graph["edges"])


def test_negated_completion_is_not_a_positive_precedence_cycle():
    corpus = graph_corpus()
    corpus["actions"][0]["preconditions"] = {"not": {"completed": "a1"}}
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    action = next(n for n in graph["nodes"] if n["id"] == "a1")
    assert action["rpc_components"]["temporal"] == 1
    assert not any(e["source"] == "a1" and e["type"] == "PRECEDES" for e in graph["edges"])


def test_effect_to_condition_link_requires_actual_value_entailment():
    corpus = graph_corpus()
    corpus["rules"].append(
        dict(
            corpus["rules"][0],
            id="global",
            action_id=None,
            condition=corpus["rules"][0]["condition"]["all"][0],
        )
    )
    corpus["actions"].append(
        dict(corpus["actions"][0], id="a2", preconditions={"field": "submitted"})
    )
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    condition = next(n for n in graph["nodes"] if n.get("owner_id") == "a2")
    state = next(
        n for n in graph["nodes"] if n["type"] == "STATE" and n.get("field_id") == "submitted"
    )
    assert any(
        e["source"] == state["id"] and e["target"] == condition["id"] for e in graph["edges"]
    )
    corpus["actions"][0]["effects"]["submitted"] = False
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    state = next(n for n in graph["nodes"] if n["type"] == "STATE" and n.get("value") is False)
    assert not any(
        e["source"] == state["id"] and e["target"] == condition["id"] for e in graph["edges"]
    )


def test_inactive_rule_does_not_invent_a_cycle_for_active_actions():
    corpus = graph_corpus()
    corpus["rules"].append(
        dict(corpus["rules"][0], id="old", status="disabled", condition={"completed": "a1"})
    )
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    rule = next(n for n in graph["nodes"] if n["id"] == "r1")
    assert rule["rpc_components"]["temporal"] == 1


def test_active_rule_conflicts_prevent_action_must_links():
    corpus = graph_corpus()
    corpus["rules"][0]["scope"]["region"] = "北京"
    graph = build_graph(corpus, get_profile("without_rpc"), {("u1", "r1"): 1})
    action = next(n for n in graph["nodes"] if n["id"] == "a1")
    assert not action["compatible"]
    assert all(not e["compatible"] for e in graph["edges"] if e["type"] == "PRODUCES")


def test_path_score_ablations_change_only_the_intended_scoring_term():
    nodes = [{"id": x, "label": x} for x in "abc"]
    edges = [{"id": x, "source": "a", "target": x, "type": "REQUIRES", "rpc": 0.8} for x in "bc"]
    scores = {"a": 0.3, "b": 0.9, "c": 0.1}
    full = {p["id"]: p for p in path_candidates(nodes, edges, scores, ["a"], get_profile("full"))}
    for profile, component, weight in (
        ("without_rpc", "rpc", 0.4),
        ("without_semantic", "semantic_score", 0.4),
        ("without_entropy", "entropy", 0.2),
    ):
        paths = path_candidates(nodes, edges, scores, ["a"], get_profile(profile))
        for path in paths:
            term = 1 - path[component] if component == "entropy" else path[component]
            assert full[path["id"]]["score"] - path["score"] == pytest.approx(weight * term)


def test_disabling_action_rule_invalidates_action_execution_edges():
    corpus = graph_corpus()
    corpus["rules"].append(dict(corpus["rules"][0], id="global", action_id=None))
    corpus["rules"][0]["status"] = "disabled"
    graph = build_graph(corpus, get_profile("full"), {("u1", "global"): 1})
    action = next(n for n in graph["nodes"] if n["id"] == "a1")
    assert action["status"] != "active"
    assert not any(e["source"] == "a1" and e["type"] == "PRODUCES" for e in graph["edges"])


def test_shared_roles_have_unique_edge_ids():
    graph = build_graph(graph_corpus(), get_profile("full"), {("u1", "r1"): 1})
    edge_ids = [e["id"] for e in graph["edges"]]
    assert len(edge_ids) == len(set(edge_ids))


def test_different_regulations_may_have_different_document_numbers():
    corpus = graph_corpus()
    corpus["units"][0].update(title="配套实施细则", version="细则文号")
    corpus["rules"][0]["scope"].update(title="上位管理办法", version="办法文号")
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    rule = next(n for n in graph["nodes"] if n["id"] == "r1")
    assert rule["rpc_components"]["temporal"] == 1


def test_same_regulation_conflicting_versions_do_not_fuse():
    corpus = graph_corpus()
    corpus["units"][0]["version"] = "旧文号"
    corpus["rules"][0]["scope"].update(title=corpus["units"][0]["title"], version="新文号")
    graph = build_graph(corpus, get_profile("without_rpc"), {("u1", "r1"): 1})
    assert not any(e["source"] == "u1" and e["target"] == "r1" for e in graph["edges"])


def test_missing_regulation_identity_does_not_invent_version_conflict():
    corpus = graph_corpus()
    corpus["units"][0]["version"] = "来源文号"
    corpus["rules"][0]["scope"]["version"] = "规则文号"
    graph = build_graph(corpus, get_profile("full"), {("u1", "r1"): 1})
    rule = next(n for n in graph["nodes"] if n["id"] == "r1")
    assert rule["version_check"] == "unknown"


def test_unknown_profile_is_rejected():
    with pytest.raises(ValueError):
        get_profile("not-a-method")
