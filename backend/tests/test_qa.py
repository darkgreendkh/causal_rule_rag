from app.models import GraphPath, RetrievalMode, Source, SourceChannel
from app.qa import QAService


class QueryEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.3, 0.4]]


class AnswerChat:
    def __init__(self) -> None:
        self.user_prompt = ""

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.user_prompt = user_prompt
        return "根据证据，测试义务成立。[S1]"


class NeverCalledChat:
    def complete(self, system_prompt: str, user_prompt: str) -> str:
        raise AssertionError("chat model must not be called without evidence")


def source(index: int, channel: SourceChannel = SourceChannel.VECTOR) -> Source:
    return Source(
        chunk_id=f"doc:{index}",
        document_id="doc",
        filename="条例.md",
        chunk_index=index,
        text=f"第{index}条 测试内容",
        score=0.9 - index * 0.01,
        channel=channel,
    )


class RetrievalStore:
    def vector_search(self, embedding: list[float], limit: int) -> list[Source]:
        return [source(index) for index in range(5)]

    def graph_expand(
        self, seeds: list[Source], limit: int
    ) -> tuple[list[Source], list[GraphPath]]:
        graph_sources = [
            source(4, SourceChannel.GRAPH),
            source(5, SourceChannel.GRAPH),
            source(6, SourceChannel.GRAPH),
            source(7, SourceChannel.GRAPH),
        ]
        paths = [
            GraphPath(
                subject="数据处理者",
                predicate="履行",
                object="安全义务",
                source_chunk_id="doc:5",
            )
        ]
        return graph_sources, paths


class EmptyRetrievalStore:
    def vector_search(self, embedding: list[float], limit: int) -> list[Source]:
        return []

    def graph_expand(
        self, seeds: list[Source], limit: int
    ) -> tuple[list[Source], list[GraphPath]]:
        raise AssertionError("graph expansion must not run without vector seeds")


def test_vector_mode_builds_cited_answer_from_five_sources() -> None:
    chat = AnswerChat()
    service = QAService(RetrievalStore(), QueryEmbedder(), chat)

    answer = service.answer("测试义务是什么？", RetrievalMode.VECTOR)

    assert answer.answer == "根据证据，测试义务成立。[S1]"
    assert len(answer.sources) == 5
    assert answer.graph_paths == []
    assert "[S1] 条例.md / Chunk 0" in chat.user_prompt


def test_hybrid_mode_adds_three_unique_graph_sources_and_paths() -> None:
    service = QAService(RetrievalStore(), QueryEmbedder(), AnswerChat())

    answer = service.answer("测试义务是什么？", RetrievalMode.HYBRID)

    assert len(answer.sources) == 8
    assert [item.chunk_id for item in answer.sources] == [
        "doc:0",
        "doc:1",
        "doc:2",
        "doc:3",
        "doc:4",
        "doc:5",
        "doc:6",
        "doc:7",
    ]
    assert len(answer.graph_paths) == 1


def test_answer_refuses_without_retrieved_evidence() -> None:
    service = QAService(EmptyRetrievalStore(), QueryEmbedder(), NeverCalledChat())

    answer = service.answer("不存在的问题", RetrievalMode.HYBRID)

    assert answer.answer == "当前知识库中没有足够证据回答该问题。"
    assert answer.sources == []
    assert answer.graph_paths == []
