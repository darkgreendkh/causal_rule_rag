from app.models import ConversationTurn, GraphPath, RetrievalMode, Source, SourceChannel
from app.qa import QAService


class QueryEmbedder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.texts = texts
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


class ContextualAnswerChat:
    def __init__(self) -> None:
        self.requests: list[tuple[str, str]] = []

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        self.requests.append((system_prompt, user_prompt))
        if len(self.requests) == 1:
            return "数据处理者违反安全义务的法律后果"
        return "违反义务会被责令改正。[S1]"


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


def test_follow_up_question_is_rewritten_before_retrieval() -> None:
    embedder = QueryEmbedder()
    chat = ContextualAnswerChat()
    service = QAService(RetrievalStore(), embedder, chat)
    history = [
        ConversationTurn(
            question="数据处理者有哪些安全义务？",
            answer="数据处理者应当建立安全管理制度。[S1]",
        )
    ]

    answer = service.answer("违反上述义务会怎样？", RetrievalMode.HYBRID, history)

    assert answer.answer == "违反义务会被责令改正。[S1]"
    assert embedder.texts == ["数据处理者违反安全义务的法律后果"]
    assert len(chat.requests) == 2
    assert "数据处理者有哪些安全义务？" in chat.requests[0][1]
    assert "违反上述义务会怎样？" in chat.requests[0][1]
    assert "数据处理者应当建立安全管理制度。[S1]" in chat.requests[1][1]
    assert "数据处理者违反安全义务的法律后果" in chat.requests[1][1]


def test_question_without_history_skips_rewrite() -> None:
    embedder = QueryEmbedder()
    chat = AnswerChat()
    service = QAService(RetrievalStore(), embedder, chat)

    service.answer("测试义务是什么？", RetrievalMode.VECTOR)

    assert embedder.texts == ["测试义务是什么？"]
