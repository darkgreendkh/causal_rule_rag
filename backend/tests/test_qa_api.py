from fastapi.testclient import TestClient

from app.main import create_app
from app.models import (
    GraphEdge,
    GraphNode,
    GraphResponse,
    QAResponse,
    RetrievalMode,
)


class APIStore:
    def health(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def list_documents(self) -> list:
        return []

    def get_document(self, document_id: str) -> None:
        return None

    def list_chunks(self, document_id: str) -> list:
        return []

    def get_graph(self, document_id: str | None, limit: int) -> GraphResponse:
        return GraphResponse(
            nodes=[
                GraphNode(
                    id="PERSON_ROLE:数据处理者",
                    label="数据处理者",
                    type="PERSON_ROLE",
                    source_chunk_ids=["doc:0"],
                )
            ],
            edges=[
                GraphEdge(
                    id="edge-1",
                    source="PERSON_ROLE:数据处理者",
                    target="OBLIGATION:安全义务",
                    predicate="履行",
                    source_chunk_id="doc:0",
                )
            ],
            truncated=False,
        )


class NoopDocumentService:
    def delete(self, document_id: str) -> bool:
        return False


class StaticQAService:
    def __init__(self) -> None:
        self.history = []

    def answer(self, question: str, mode: RetrievalMode, history: list) -> QAResponse:
        self.history = history
        return QAResponse(answer="回答 [S1]", mode=mode, sources=[], graph_paths=[])


def test_qa_api_validates_request_and_returns_selected_mode() -> None:
    qa_service = StaticQAService()
    app = create_app(
        store=APIStore(),
        document_service=NoopDocumentService(),
        qa_service=qa_service,
    )

    with TestClient(app) as client:
        response = client.post("/api/qa", json={"question": "第一条是什么？", "mode": "hybrid"})
        empty = client.post("/api/qa", json={"question": "   ", "mode": "vector"})

    assert response.status_code == 200
    assert response.json()["mode"] == "hybrid"
    assert qa_service.history == []
    assert empty.status_code == 422


def test_qa_api_accepts_at_most_three_history_turns() -> None:
    qa_service = StaticQAService()
    app = create_app(
        store=APIStore(),
        document_service=NoopDocumentService(),
        qa_service=qa_service,
    )
    turn = {"question": "上一问", "answer": "上一答 [S1]"}

    with TestClient(app) as client:
        accepted = client.post(
            "/api/qa",
            json={"question": "继续追问", "mode": "hybrid", "history": [turn] * 3},
        )
        rejected = client.post(
            "/api/qa",
            json={"question": "继续追问", "mode": "hybrid", "history": [turn] * 4},
        )

    assert accepted.status_code == 200
    assert len(qa_service.history) == 3
    assert rejected.status_code == 422


def test_graph_api_returns_cytoscape_ready_nodes_and_edges() -> None:
    app = create_app(
        store=APIStore(),
        document_service=NoopDocumentService(),
        qa_service=StaticQAService(),
    )

    with TestClient(app) as client:
        response = client.get("/api/graph?document_id=doc&limit=300")

    assert response.status_code == 200
    assert response.json()["nodes"][0]["label"] == "数据处理者"
    assert response.json()["edges"][0]["predicate"] == "履行"
