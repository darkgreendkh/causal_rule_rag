from typing import Any


class OpenAIChatModel:
    def __init__(
        self,
        model_name: str,
        client: Any | None = None,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
    ) -> None:
        if client is None:
            from openai import OpenAI

            client = OpenAI(base_url=base_url, api_key=api_key)
        self._model_name = model_name
        self._client = client

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        response = self._client.chat.completions.create(
            model=self._model_name,
            temperature=0,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
        content = response.choices[0].message.content
        if not content:
            raise RuntimeError("大模型返回了空内容")
        return content


class UnavailableChatModel:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise RuntimeError("LLM 配置不完整，请设置 LLM_BASE_URL、LLM_API_KEY 和 LLM_MODEL")
