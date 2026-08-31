from typing import Protocol

from app.models import GraphPath, QAResponse, RetrievalMode, Source

SYSTEM_PROMPT = """你是法律法规问答助手。只能依据用户提供的证据回答，不得补充证据中没有的事实。
回答中的关键结论必须使用 [S1]、[S2] 形式引用证据。证据不足时只回答：
当前知识库中没有足够证据回答该问题。"""


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

    def answer(self, question: str, mode: RetrievalMode) -> QAResponse:
        embedding = self._embedder.embed([question])[0]
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
        answer = self._chat.complete(
            SYSTEM_PROMPT,
            f"问题：{question}\n\n证据：\n{evidence}",
        )
        return QAResponse(
            answer=answer,
            mode=mode,
            sources=sources,
            graph_paths=graph_paths,
        )
