from types import SimpleNamespace

import pytest

from app.llm import OpenAIChatModel, UnavailableChatModel


class FakeCompletions:
    def create(self, **request: object) -> SimpleNamespace:
        if request["temperature"] != 0:
            raise AssertionError("temperature must be zero")
        messages = request["messages"]
        if messages != [
            {"role": "system", "content": "system"},
            {"role": "user", "content": "user"},
        ]:
            raise AssertionError("unexpected messages")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="回答"))]
        )


class FakeOpenAI:
    def __init__(self) -> None:
        self.chat = SimpleNamespace(completions=FakeCompletions())


def test_openai_chat_model_returns_first_message_content() -> None:
    model = OpenAIChatModel("model-name", client=FakeOpenAI())

    assert model.complete("system", "user") == "回答"


def test_unavailable_chat_model_reports_missing_configuration() -> None:
    with pytest.raises(RuntimeError, match="LLM 配置不完整"):
        UnavailableChatModel().complete("system", "user")
