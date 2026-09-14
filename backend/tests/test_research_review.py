"""Independent service review regressions; no model or external database calls."""

import json
from copy import deepcopy
from pathlib import Path

import pytest
from test_research_service import Chat, Embedder, MemoryRepository, corpus

from app.corpus import _read_policy
from app.policy_catalog import make_catalog
from app.research import ResearchService
from app.workflow import check_workflow, repair_workflow


class RecordingChat(Chat):
    def complete(self, system, prompt):
        self.prompt = prompt
        return super().complete(system, prompt)


def action_service(tmp_path, profile="full"):
    source = corpus()
    source["matters"][0]["fields"].append(
        {"id": "ready", "label": "材料核验", "type": "boolean", "role": "applicant"}
    )
    source["actions"][0]["preconditions"] = {"field": "ready"}
    service = ResearchService(
        MemoryRepository(),
        Embedder(),
        RecordingChat(),
        tmp_path,
        tmp_path / "cache",
        builder=lambda _: deepcopy(source),
    )
    service.build(profile)
    # A single directed action/result component isolates filtering from seed ranking.
    snapshot = service.snapshot(profile)
    graph = snapshot["graph"]
    edge = next(e for e in graph["edges"] if e["source"] == "a" and e["type"] == "PRODUCES")
    graph["nodes"] = [n for n in graph["nodes"] if n["id"] in {"a", edge["target"]}]
    graph["edges"] = [edge]
    return service


def question(**facts):
    return {
        "question": "能否提交",
        "mode": "causal",
        "matter_id": "m",
        "region": "武汉",
        "as_of": "2024-01-01",
        "facts": {"age": 20, "form": True, **facts},
    }


def test_full_filters_violated_action_even_when_path_has_no_rule_ids(tmp_path):
    service = action_service(tmp_path)
    result = service.answer(question(ready=False))
    assert any(c["rule_id"] == "a" and c["status"] == "violated" for c in result["rule_checks"])
    assert not result["causal_paths"]


def test_unknown_action_path_is_explicitly_marked_unknown(tmp_path):
    service = action_service(tmp_path)
    result = service.answer(question())
    assert result["causal_paths"]
    assert all(p.get("rule_status") == "unknown" for p in result["causal_paths"])
    assert any("ready" in gap for gap in result["knowledge_gaps"])


@pytest.mark.parametrize("initial_profile", ["full", "without_rpc"])
def test_rebuilding_changed_sources_invalidates_other_profiles(tmp_path, initial_profile):
    source = corpus()
    service = ResearchService(
        MemoryRepository(),
        Embedder(),
        Chat(),
        tmp_path,
        tmp_path / "cache",
        builder=lambda _: deepcopy(source),
    )
    service.build(initial_profile)
    service.build("without_scs")
    source["documents"][0]["sha256"] = "changed-source-digest"
    service.build("full")
    with pytest.raises(ValueError, match="构建|失效|变"):
        service.snapshot("without_scs")


def test_without_evidence_chain_preserves_rule_checks_and_missing_fact_guidance(tmp_path):
    service = action_service(tmp_path, "without_evidence_chain")
    service.answer(dict(question(), profile="without_evidence_chain"))
    prompt = json.loads(service.chat.prompt.split("\n原文证据：", 1)[0])
    assert prompt["constraints"].get("rule_checks")
    assert prompt["constraints"].get("knowledge_gaps")
    assert not prompt["constraints"].get("paths")


def controlled_path_service(tmp_path, monkeypatch, source, node_id="a"):
    service = ResearchService(
        MemoryRepository(),
        Embedder(),
        RecordingChat(),
        tmp_path,
        tmp_path / "cache",
        builder=lambda _: deepcopy(source),
    )
    service.build("full")
    monkeypatch.setattr(
        "app.research.path_candidates",
        lambda *args: [
            {
                "id": "controlled",
                "node_ids": [node_id],
                "rule_ids": [],
                "evidence": [],
            }
        ],
    )
    return service


@pytest.mark.parametrize("source_count", [8, 9])
def test_complete_evidence_packet_respects_budget(tmp_path, monkeypatch, source_count):
    source = corpus()
    for index in range(1, source_count):
        uid = f"u{index}"
        source["units"].append(dict(source["units"][0], id=uid))
        source["rules"][0]["evidence"].append(dict(source["rules"][0]["evidence"][0], unit_id=uid))
        source["matters"][0]["source_unit_ids"].append(uid)
    service = controlled_path_service(tmp_path, monkeypatch, source)
    result = service.answer(question())
    prompt = json.loads(service.chat.prompt.split("\n原文证据：", 1)[0])
    if source_count == 8:
        assert result["causal_paths"][0]["evidence_complete"]
        assert len(result["sources"]) == 8
        assert prompt["constraints"]["rule_checks"]
        return
    assert not result["causal_paths"]
    assert len(result["sources"]) == 8
    assert result["rule_checks"]  # Retain the rejected candidate for diagnosis.
    assert all(not check.get("used_for_answer", True) for check in result["rule_checks"])
    assert not prompt["constraints"]["rule_checks"]


def test_missing_required_source_cannot_be_evidence_complete(tmp_path, monkeypatch):
    source = corpus()
    source["rules"][0]["evidence"].append(
        dict(source["rules"][0]["evidence"][0], unit_id="removed")
    )
    service = controlled_path_service(tmp_path, monkeypatch, source)
    result = service.answer(question())
    assert not result["causal_paths"]
    assert any("来源" in gap and "缺失" in gap for gap in result["knowledge_gaps"])


def test_and_leaf_returns_full_owner_condition_ids(tmp_path, monkeypatch):
    service = controlled_path_service(tmp_path, monkeypatch, corpus())
    graph = service.snapshot()["graph"]
    owner = next(node for node in graph["nodes"] if node["id"] == "r")
    leaf = next(node for node in graph["nodes"] if node.get("owner_id") == "r")
    monkeypatch.setattr(
        "app.research.path_candidates",
        lambda *args: [
            {
                "id": "leaf",
                "node_ids": [leaf["id"]],
                "rule_ids": [],
                "evidence": [],
            }
        ],
    )
    result = service.answer(question())
    assert result["causal_paths"][0]["required_condition_ids"] == sorted(
        owner["required_condition_ids"]
    )


def test_violated_checks_need_supported_evidence_before_generation(tmp_path, monkeypatch):
    service = controlled_path_service(tmp_path, monkeypatch, corpus())
    result = service.answer(question(age=17))
    assert not result["causal_paths"]
    assert result["sources"][0]["chunk_id"] == "u"
    prompt = json.loads(service.chat.prompt.split("\n原文证据：", 1)[0])
    assert any(check["status"] == "violated" for check in prompt["constraints"]["rule_checks"])


def test_disabled_rule_cannot_advance_retrieved_action(tmp_path, monkeypatch):
    service = controlled_path_service(tmp_path, monkeypatch, corpus())
    service.review(["r"], "disable")
    result = service.answer(question())
    assert result["causal_paths"][0]["rule_status"] == "unknown"
    assert not result["causal_paths"][0]["simulated_completed_steps"]
    assert any("停用" in gap for gap in result["knowledge_gaps"])


def test_misquoted_required_source_cannot_support_generation(tmp_path, monkeypatch):
    source = corpus()
    source["rules"][0]["evidence"].append(
        dict(source["rules"][0]["evidence"][0], quote="不在原文的必要条件")
    )
    service = controlled_path_service(tmp_path, monkeypatch, source)
    result = service.answer(question())
    assert not result["causal_paths"]
    prompt = json.loads(service.chat.prompt.split("\n原文证据：", 1)[0])
    assert not prompt["constraints"]["rule_checks"]


@pytest.mark.parametrize("mode", ["causal", "vector", "hybrid"])
def test_generation_cannot_return_rules_invalidated_during_model_call(tmp_path, monkeypatch, mode):
    service = controlled_path_service(tmp_path, monkeypatch, corpus())

    class InvalidatingChat(Chat):
        def complete(self, system, prompt):
            service.review(["r"], "disable")
            return "根据旧规则可以提交"

    service.chat = InvalidatingChat()
    with pytest.raises(ValueError, match="知识库.*变更|过时"):
        service.answer(dict(question(), mode=mode))


@pytest.fixture(scope="module")
def actual_catalog():
    data = Path(__file__).resolve().parents[2] / "data"
    units = [
        unit
        for directory in ("guojia_shebao", "wuhan_shebao")
        for path in (data / directory).rglob("*.txt")
        for unit in _read_policy(path, data)[1]
    ]
    matters, rules, actions, _ = make_catalog(units)
    return {"matters": matters, "rules": rules, "actions": actions}


def test_real_pension_submission_still_enforces_minimum_age(actual_catalog):
    matter = next(m for m in actual_catalog["matters"] if m["id"] == "resident_pension_enroll")
    fields = {f["id"]: f for f in matter["fields"]}
    request = {
        "matter_id": matter["id"],
        "region": "武汉",
        "as_of": "2024-01-01",
        "steps": ["resident_pension_enroll_apply"],
        "facts": {
            "age": 15,
            "student": False,
            "public_employee": False,
            "employee_pension_covered": False,
            "pension_at_household": True,
            "registration_identity_valid": True,
            "resident_pension_enroll_apply_documents": fields[
                "resident_pension_enroll_apply_documents"
            ]["options"],
        },
    }
    assert check_workflow(actual_catalog, request)["status"] == "violated"
    request["facts"]["age"] = 16
    assert check_workflow(actual_catalog, request)["status"] == "satisfied"


def test_real_injury_preparation_and_minimal_material_repair(actual_catalog):
    matter = next(m for m in actual_catalog["matters"] if m["id"] == "injury_recognition")
    fields = {f["id"]: f for f in matter["fields"]}
    request = {
        "matter_id": matter["id"],
        "region": "武汉",
        "as_of": "2024-01-01",
        "steps": ["injury_recognition_prepare"],
        "facts": {
            "injury_recognition_prepare_documents": fields["injury_recognition_prepare_documents"][
                "options"
            ],
        },
    }
    assert check_workflow(actual_catalog, request)["status"] == "satisfied"
    request.update(steps=["injury_recognition_apply"], goal="injury_recognition_apply")
    request["facts"].update(
        injury_applicant="单位",
        injury_days=20,
        extension_confirmed=False,
        employment_proof=True,
        diagnosis_proof=True,
        injury_jurisdiction=True,
        injury_application_form=False,
    )
    result = repair_workflow(actual_catalog, request)
    assert result["status"] == "repaired"
    assert result["steps"] == ["injury_recognition_prepare", "injury_recognition_apply"]
    assert result["cost"] == 1
    assert result["checked"]["status"] == "satisfied"
