from typing import Protocol

from app.models import ConversationTurn, GraphPath, QAResponse, RetrievalMode, Source

SYSTEM_PROMPT = """你是法律法规问答助手。只能依据用户提供的证据回答，不得补充证据中没有的事实。
回答中的关键结论必须使用 [S1]、[S2] 形式引用证据。证据不足时只回答：
当前知识库中没有足够证据回答该问题。"""

CONTEXTUALIZE_PROMPT = """你负责把多轮法规问答中的当前问题改写为可以独立检索的问题。
结合对话历史补全指代和省略，但不要回答问题，不要增加历史中不存在的事实。
只输出改写后的问题。"""


class RetrievalStore(Protocol):
    def vector_search(self, embedding: list[float], limit: int) -> list[Source]: ...

    def graph_expand(
        self, seeds: list[Source], limit: int
    ) -> tuple[list[Source], list[GraphPath]]: ...


class QueryEmbedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class AnswerChat(Protocol):
    def complete(self, system_prompt: str, user_prompt: str) -> str: ...


class QAService:
    def __init__(
        self,
        store: RetrievalStore,
        embedder: QueryEmbedder,
        chat: AnswerChat,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._chat = chat

    def answer(
        self,
        question: str,
        mode: RetrievalMode,
        history: list[ConversationTurn] | None = None,
    ) -> QAResponse:
        conversation = history or []
        retrieval_question = self._contextualize(question, conversation)
        embedding = self._embedder.embed([retrieval_question])[0]
        vector_sources = self._store.vector_search(embedding, limit=5)
        if not vector_sources:
            return QAResponse(
                answer="当前知识库中没有足够证据回答该问题。",
                mode=mode,
                sources=[],
                graph_paths=[],
            )

        sources = list(vector_sources)
        graph_paths: list[GraphPath] = []
        if mode is RetrievalMode.HYBRID:
            graph_sources, graph_paths = self._store.graph_expand(vector_sources, limit=3)
            seen = {source.chunk_id for source in sources}
            for graph_source in graph_sources:
                if graph_source.chunk_id in seen:
                    continue
                sources.append(graph_source)
                seen.add(graph_source.chunk_id)
                if len(sources) == 8:
                    break

        evidence = "\n\n".join(
            f"[S{index}] {source.filename} / Chunk {source.chunk_index}\n{source.text}"
            for index, source in enumerate(sources, start=1)
        )
        user_prompt = f"问题：{question}\n\n证据：\n{evidence}"
        if conversation:
            user_prompt = (
                "对话历史（仅用于理解当前问题，不作为证据）：\n"
                f"{_format_history(conversation)}\n\n"
                f"当前问题：{question}\n"
                f"独立检索问题：{retrieval_question}\n\n"
                f"本轮证据：\n{evidence}"
            )
        answer = self._chat.complete(SYSTEM_PROMPT, user_prompt)
        return QAResponse(
            answer=answer,
            mode=mode,
            sources=sources,
            graph_paths=graph_paths,
        )

    def _contextualize(
        self,
        question: str,
        history: list[ConversationTurn],
    ) -> str:
        if not history:
            return question
        rewritten = self._chat.complete(
            CONTEXTUALIZE_PROMPT,
            f"对话历史：\n{_format_history(history)}\n\n当前问题：{question}",
        ).strip()
        if not rewritten:
            raise RuntimeError("大模型未能生成独立检索问题")
        return rewritten


def _format_history(history: list[ConversationTurn]) -> str:
    return "\n\n".join(
        f"用户：{turn.question}\n助手：{turn.answer}" for turn in history
    )
