from copy import deepcopy

import pytest

from app.research import ResearchService


class MemoryRepository:
    def __init__(self):
        self.snapshots = {}
        self.events = []

    def load(self, profile):
        return deepcopy(self.snapshots.get(profile))

    def save(self, snapshot):
        self.snapshots[snapshot["profile"]["id"]] = deepcopy(snapshot)

    def invalidate(self, reason):
        self.snapshots.clear()

    def log(self, event):
        self.events.append(event)


class Embedder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class Chat:
    def complete(self, system, prompt):
        return "依据条款核对申请条件 [S1]。"


def corpus():
    evidence = {
        "unit_id": "u",
        "source_path": "fixture.txt",
        "title": "测试政策",
        "article": "第一条",
        "quote": "年满十八周岁并提交申请表。",
    }
    scope = {"region": "全国", "valid_from": "2020-01-01", "valid_to": None, "validity_known": True}
    return {
        "documents": [
            {"id": "d", "filename": "fixture.txt", "source_path": "fixture.txt", "sha256": "x"}
        ],
        "units": [
            dict(
                scope,
                id="u",
                document_id="d",
                title="测试政策",
                article="第一条",
                text=evidence["quote"],
                source_path="fixture.txt",
            )
        ],
        "matters": [
            {
                "id": "m",
                "name": "申请",
                "category": "测试",
                "fields": [
                    {"id": "age", "label": "年龄", "type": "number", "role": "applicant"},
                    {"id": "form", "label": "表格", "type": "boolean", "role": "applicant"},
                    {
                        "id": "submitted",
                        "label": "已提交",
                        "type": "boolean",
                        "role": "applicant",
                        "mutable": True,
                    },
                ],
                "source_unit_ids": ["u"],
                "rule_ids": ["r"],
                "action_ids": ["a"],
                "policy_parameters": {},
                "gaps": [],
                "goals": [],
                "capabilities": {
                    "retrievable": True,
                    "checkable": True,
                    "simulatable": True,
                    "repairable": True,
                },
            }
        ],
        "rules": [
            {
                "id": "r",
                "matter_id": "m",
                "label": "申请资格",
                "condition": {
                    "all": [
                        {"op": "gte", "left": {"field": "age"}, "right": {"value": 18}},
                        {"op": "eq", "left": {"field": "form"}, "right": {"value": True}},
                    ]
                },
                "action_id": "a",
                "scope": scope,
                "evidence": [evidence],
                "status": "active",
                "review_source": "implementation_source_review",
                "validation_errors": [],
            }
        ],
        "actions": [
            {
                "id": "a",
                "matter_id": "m",
                "label": "提交",
                "kind": "user",
                "preconditions": {"value": True},
                "effects": {"submitted": True},
                "evidence": [evidence],
            }
        ],
        "coverage": [
            {"unit_id": "u", "matter_ids": ["m"], "disposition": "mapped", "reason": "办理条件"}
        ],
        "references": [],
    }


def service(tmp_path):
    return ResearchService(
        MemoryRepository(),
        Embedder(),
        Chat(),
        tmp_path,
        tmp_path / "cache",
        builder=lambda _: corpus(),
    )


def test_build_persists_separate_profiles_and_counts(tmp_path):
    s = service(tmp_path)
    s.build("full")
    first = s.snapshot()["build_id"]
    s.build("without_micro")
    assert s.snapshot()["build_id"] == first
    assert all(n["layer"] == "macro" for n in s.snapshot("without_micro")["graph"]["nodes"])
    assert s.summary()["counts"]["policy_documents"] == 1
    assert s.summary()["counts"]["covered_units"] == 1


def test_disable_rule_versions_graph_and_invalidates_other_profiles(tmp_path):
    s = service(tmp_path)
    s.build("full")
    s.build("without_scs")
    before = s.snapshot()["build_id"]
    response = s.review(["r"], "disable")
    assert response["build_id"] != before
    assert s.snapshot()["corpus"]["rules"][0]["status"] == "disabled"
    assert not any("r" in edge.get("rule_ids", []) for edge in s.snapshot()["graph"]["edges"])
    with pytest.raises(ValueError, match="构建"):
        s.snapshot("without_scs")


def test_causal_answer_checks_all_and_conditions_and_records_run(tmp_path):
    s = service(tmp_path)
    s.build("full")
    result = s.answer(
        {
            "question": "如何申请",
            "mode": "causal",
            "matter_id": "m",
            "region": "武汉",
            "as_of": "2024-01-01",
            "facts": {"age": 20},
        }
    )
    assert any(c["status"] == "unknown" for c in result["rule_checks"])
    assert any("form" in gap for gap in result["knowledge_gaps"])
    assert result["sources"]
    assert s.repository.events[-1]["build_id"] == s.snapshot()["build_id"]
    assert s.repository.events[-1]["kind"] == "qa"


def test_review_rejects_missing_evidence(tmp_path):
    s = service(tmp_path)
    s.build("full")
    s._snapshots["full"]["corpus"]["rules"][0]["evidence"][0]["quote"] = "伪造条件"
    result = s.review(["r"], "activate")
    assert result["results"][0]["error"]


def test_unknown_profile_and_missing_matter_are_explicit(tmp_path):
    s = service(tmp_path)
    with pytest.raises(ValueError):
        s.build("unknown")
    s.build("full")
    with pytest.raises(ValueError, match="事项"):
        s.workflow("check", {"matter_id": "missing"})


def test_removing_source_rebuilds_without_invalid_evidence_and_preserves_raw(tmp_path):
    raw = tmp_path / "fixture.txt"
    raw.write_text("original source", encoding="utf-8")
    s = service(tmp_path)
    s.build("full")
    old = s.snapshot()["build_id"]
    s.remove_document("d")
    assert raw.read_text("utf-8") == "original source"
    snapshot = s.snapshot()
    assert snapshot["build_id"] != old
    assert not snapshot["corpus"]["rules"]
    assert not snapshot["graph"]["edges"]
    assert not snapshot["corpus"]["units"]
    s.build("full")
    assert not s.snapshot()["corpus"]["documents"]


def test_review_is_bound_to_expression_and_source_revision(tmp_path):
    source = corpus()
    source["rules"][0]["status"] = "candidate"
    s = ResearchService(
        MemoryRepository(),
        Embedder(),
        Chat(),
        tmp_path,
        tmp_path / "cache",
        builder=lambda _: deepcopy(source),
    )
    s.build("full")
    s.review(["r"], "activate")
    s.build("full")
    assert s.snapshot()["corpus"]["rules"][0]["status"] == "active"
    source["rules"][0]["condition"]["all"][0]["right"]["value"] = 21
    s.build("full")
    assert s.snapshot()["corpus"]["rules"][0]["status"] == "candidate"
