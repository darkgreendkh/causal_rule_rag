from typing import Protocol

from pydantic import ValidationError

from app.models import Triple, TriplePayload

SYSTEM_PROMPT = """你是法律文本知识图谱抽取器。只输出 JSON，不要解释。
输出格式：{"triples":[{"subject":"...","subject_type":"...","predicate":"...","object":"...","object_type":"..."}]}。
实体类型只能是 LAW、ARTICLE、AGENCY、PERSON_ROLE、ORGANIZATION、LEGAL_CONCEPT、
ACTION、RIGHT、OBLIGATION、PENALTY、OTHER。没有可靠关系时返回 {"triples":[]}。
实体名应简短明确，谓词使用原文中的中文关系，禁止补充原文不存在的事实。"""


class ChatModel(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class ExtractionError(ValueError):
    pass


class GraphExtractor:
    def __init__(self, chat: ChatModel) -> None:
        self._chat = chat

    def extract(self, text: str) -> list[Triple]:
        prompt = f"请从以下文本抽取三元组：\n\n{text}"
        last_error = ""
        for attempt in range(2):
            if attempt:
                prompt = (
                    f"上一次输出无法通过校验：{last_error}\n"
                    "请严格按指定 JSON 格式重新抽取以下文本：\n\n"
                    f"{text}"
                )
            response = self._chat.complete(SYSTEM_PROMPT, prompt)
            try:
                payload = TriplePayload.model_validate_json(_strip_code_fence(response))
            except ValidationError as error:
                last_error = str(error)
                continue
            return payload.triples
        raise ExtractionError(f"大模型两次输出均无法解析：{last_error}")


def _strip_code_fence(response: str) -> str:
    content = response.strip()
    if not content.startswith("```"):
        return content
    lines = content.splitlines()
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines[1:]).strip()
