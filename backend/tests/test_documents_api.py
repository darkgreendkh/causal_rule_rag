from pathlib import Path

from fastapi.testclient import TestClient

from app.ingestion import DocumentService
from app.main import create_app
from app.models import ChunkView, DocumentRecord, DocumentStatus


class InMemoryStore:
    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.chunks = {}

    def health(self) -> bool:
        return True

    def close(self) -> None:
        return None

    def create_document(self, document: DocumentRecord) -> None:
        self.documents[document.id] = document

    def find_document_by_sha256(self, sha256: str) -> DocumentRecord | None:
        return next((doc for doc in self.documents.values() if doc.sha256 == sha256), None)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self.documents.get(document_id)

    def list_documents(self) -> list[DocumentRecord]:
        return list(self.documents.values())

    def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        *,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        error: str | None = None,
    ) -> None:
        document = self.documents[document_id]
        document.status = status
        document.error = error
        if total_chunks is not None:
            document.total_chunks = total_chunks
        if processed_chunks is not None:
            document.processed_chunks = processed_chunks

    def save_chunks(self, document_id: str, chunks: list) -> None:
        self.chunks[document_id] = chunks

    def save_triples(self, document_id: str, chunk_id: str, triples: list) -> None:
        return None

    def list_chunks(self, document_id: str) -> list[ChunkView]:
        return [ChunkView.model_validate(chunk) for chunk in self.chunks.get(document_id, [])]

    def cleanup_derived(self, document_id: str) -> None:
        self.chunks.pop(document_id, None)

    def delete_document(self, document_id: str) -> DocumentRecord | None:
        self.cleanup_derived(document_id)
        return self.documents.pop(document_id, None)


class TinyEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[0.1, 0.2] for _ in texts]


class EmptyExtractor:
    def extract(self, text: str) -> list:
        return []


def test_document_api_uploads_lists_chunks_rejects_duplicate_and_deletes(
    tmp_path: Path,
) -> None:
    store = InMemoryStore()
    service = DocumentService(store, TinyEmbedder(), EmptyExtractor(), tmp_path)
    app = create_app(store=store, document_service=service)

    with TestClient(app) as client:
        upload = client.post(
            "/api/documents",
            files={"file": ("条例.md", "第一条 内容\n\n第二条 内容", "text/markdown")},
        )
        assert upload.status_code == 202
        assert upload.json()["status"] == "PENDING"
        document_id = upload.json()["id"]

        documents = client.get("/api/documents")
        assert documents.status_code == 200
        assert documents.json()[0]["status"] == "COMPLETED"

        chunks = client.get(f"/api/documents/{document_id}/chunks")
        assert chunks.status_code == 200
        assert [chunk["article_no"] for chunk in chunks.json()] == ["第一条", "第二条"]

        duplicate = client.post(
            "/api/documents",
            files={"file": ("重复.txt", "第一条 内容\n\n第二条 内容", "text/plain")},
        )
        assert duplicate.status_code == 409

        deleted = client.delete(f"/api/documents/{document_id}")
        assert deleted.status_code == 204
        assert client.get("/api/documents").json() == []


def test_document_api_rejects_unsupported_extension(tmp_path: Path) -> None:
    store = InMemoryStore()
    service = DocumentService(store, TinyEmbedder(), EmptyExtractor(), tmp_path)
    app = create_app(store=store, document_service=service)

    with TestClient(app) as client:
        response = client.post(
            "/api/documents",
            files={"file": ("条例.pdf", b"content", "application/pdf")},
        )

    assert response.status_code == 422
