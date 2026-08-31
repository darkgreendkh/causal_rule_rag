from collections.abc import Iterator

import pytest

from app.extraction import ExtractionError, GraphExtractor
from app.models import EntityType


class StubChatModel:
    def __init__(self, responses: list[str]) -> None:
        self._responses: Iterator[str] = iter(responses)
        self.prompts: list[str] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.prompts.append(user_prompt)
        return next(self._responses)


def test_extractor_retries_invalid_json_once() -> None:
    chat = StubChatModel(
        [
            "not-json",
            (
                '{"triples":[{"subject":"数据处理者","subject_type":"PERSON_ROLE",'
                '"predicate":"应当履行","object":"数据安全义务",'
                '"object_type":"OBLIGATION"}]}'
            ),
        ]
    )

    triples = GraphExtractor(chat).extract("数据处理者应当履行数据安全义务。")

    assert len(triples) == 1
    assert triples[0].subject == "数据处理者"
    assert triples[0].object_type is EntityType.OBLIGATION
    assert len(chat.prompts) == 2
    assert "上一次输出无法通过校验" in chat.prompts[1]


def test_extractor_raises_after_second_invalid_response() -> None:
    chat = StubChatModel(["not-json", '{"triples":"wrong"}'])

    with pytest.raises(ExtractionError, match="两次输出均无法解析"):
        GraphExtractor(chat).extract("测试文本")


def test_extractor_accepts_json_code_fence() -> None:
    chat = StubChatModel(["```json\n{\"triples\": []}\n```"])

    assert GraphExtractor(chat).extract("没有三元组") == []
