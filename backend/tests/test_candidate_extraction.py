import json

from app.candidate_extraction import extract_candidate_rules


class Model:
    def __init__(self, payload):
        self.payload = payload

    def complete(self, system, prompt):
        return json.dumps(self.payload, ensure_ascii=False)


def test_candidate_is_never_active_and_requires_literal_source():
    unit = {
        "id": "u",
        "title": "测试法",
        "article": "一",
        "text": "申请人年满十八周岁。",
        "source_path": "fixture.txt",
        "region": "全国",
        "valid_from": None,
        "valid_to": None,
        "validity_known": False,
    }
    matter = {
        "id": "m",
        "name": "申请",
        "fields": [{"id": "age", "type": "number"}],
        "action_ids": [],
    }
    result = extract_candidate_rules(
        unit,
        matter,
        Model(
            {
                "rules": [
                    {
                        "label": "年龄",
                        "condition": {
                            "op": "gte",
                            "left": {"field": "age"},
                            "right": {"value": 18},
                        },
                        "action_id": None,
                        "quotes": ["申请人年满十八周岁。"],
                    },
                    {
                        "label": "伪造",
                        "condition": {"python": "return True"},
                        "action_id": None,
                        "quotes": ["无需任何条件"],
                    },
                ]
            }
        ),
    )
    assert all(r["status"] == "candidate" for r in result)
    assert not result[0]["validation_errors"]
    assert result[1]["validation_errors"]
    assert result[0]["review_source"] == "unreviewed_model_candidate"
    assert result[0]["evidence"][0]["unit_id"] == "u"


def test_unparseable_model_output_is_explicit():
    class Broken:
        def complete(self, *args):
            return "not JSON"

    import pytest

    with pytest.raises(ValueError, match="JSON"):
        extract_candidate_rules({"text": "原文"}, {"fields": [], "action_ids": []}, Broken())
