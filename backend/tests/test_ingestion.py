from pathlib import Path

import pytest

from app.ingestion import (
    DocumentService,
    DuplicateDocumentError,
    InvalidDocumentError,
)
from app.models import DocumentRecord, DocumentStatus, EntityType, Triple


class FakeStore:
    def __init__(self) -> None:
        self.documents: dict[str, DocumentRecord] = {}
        self.statuses: list[DocumentStatus] = []
        self.saved_chunks = []
        self.saved_triples: list[tuple[str, list[Triple]]] = []
        self.cleanup_called = False

    def create_document(self, document: DocumentRecord) -> None:
        self.documents[document.id] = document

    def find_document_by_sha256(self, sha256: str) -> DocumentRecord | None:
        return next((doc for doc in self.documents.values() if doc.sha256 == sha256), None)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        return self.documents.get(document_id)

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
        if total_chunks is not None:
            document.total_chunks = total_chunks
        if processed_chunks is not None:
            document.processed_chunks = processed_chunks
        document.error = error
        self.statuses.append(status)

    def save_chunks(self, document_id: str, chunks: list) -> None:
        self.saved_chunks = chunks

    def save_triples(self, document_id: str, chunk_id: str, triples: list[Triple]) -> None:
        self.saved_triples.append((chunk_id, triples))

    def cleanup_derived(self, document_id: str) -> None:
        self.cleanup_called = True
        self.saved_chunks = []
        self.saved_triples = []

    def delete_document(self, document_id: str) -> DocumentRecord | None:
        self.cleanup_derived(document_id)
        return self.documents.pop(document_id, None)


class FakeEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[float(index), 1.0] for index, _ in enumerate(texts)]


class FakeExtractor:
    def extract(self, text: str) -> list[Triple]:
        return [
            Triple(
                subject="数据处理者",
                subject_type=EntityType.PERSON_ROLE,
                predicate="遵守",
                object="本条例",
                object_type=EntityType.LAW,
            )
        ]


class FailingExtractor:
    def extract(self, text: str) -> list[Triple]:
        raise ValueError("模型输出无效")


def test_create_upload_saves_pending_utf8_document(tmp_path: Path) -> None:
    store = FakeStore()
    service = DocumentService(store, FakeEmbedder(), FakeExtractor(), tmp_path)

    document = service.create_upload("条例.md", "第一条 测试内容".encode())

    assert document.filename == "条例.md"
    assert document.status is DocumentStatus.PENDING
    assert Path(document.file_path).read_text(encoding="utf-8") == "第一条 测试内容"
    assert store.documents[document.id].sha256 == document.sha256


@pytest.mark.parametrize(
    ("filename", "content"),
    [("条例.pdf", b"content"), ("条例.md", b""), ("条例.txt", b"\xff")],
)
def test_create_upload_rejects_unsupported_empty_or_non_utf8_file(
    tmp_path: Path, filename: str, content: bytes
) -> None:
    service = DocumentService(FakeStore(), FakeEmbedder(), FakeExtractor(), tmp_path)

    with pytest.raises(InvalidDocumentError):
        service.create_upload(filename, content)


def test_create_upload_rejects_duplicate_content(tmp_path: Path) -> None:
    store = FakeStore()
    service = DocumentService(store, FakeEmbedder(), FakeExtractor(), tmp_path)
    service.create_upload("条例.md", "同一内容".encode())

    with pytest.raises(DuplicateDocumentError):
        service.create_upload("另一个名字.txt", "同一内容".encode())


def test_process_advances_status_and_persists_chunks_and_triples(tmp_path: Path) -> None:
    store = FakeStore()
    service = DocumentService(store, FakeEmbedder(), FakeExtractor(), tmp_path)
    document = service.create_upload("条例.md", "第一条 内容\n\n第二条 内容".encode())

    service.process(document.id)

    assert store.documents[document.id].status is DocumentStatus.COMPLETED
    assert store.documents[document.id].total_chunks == 2
    assert store.documents[document.id].processed_chunks == 2
    assert len(store.saved_chunks) == 2
    assert store.saved_chunks[0].embedding == [0.0, 1.0]
    assert len(store.saved_triples) == 2
    assert store.statuses[:3] == [
        DocumentStatus.PARSING,
        DocumentStatus.EMBEDDING,
        DocumentStatus.EXTRACTING_GRAPH,
    ]
    assert store.statuses[-1] is DocumentStatus.COMPLETED


def test_process_cleans_derived_data_and_marks_failure(tmp_path: Path) -> None:
    store = FakeStore()
    service = DocumentService(store, FakeEmbedder(), FailingExtractor(), tmp_path)
    document = service.create_upload("条例.md", "第一条 内容".encode())

    service.process(document.id)

    failed = store.documents[document.id]
    assert failed.status is DocumentStatus.FAILED
    assert failed.error == "模型输出无效"
    assert store.cleanup_called is True
    assert Path(document.file_path).exists()


def test_delete_document_removes_raw_file_and_store_record(tmp_path: Path) -> None:
    store = FakeStore()
    service = DocumentService(store, FakeEmbedder(), FakeExtractor(), tmp_path)
    document = service.create_upload("条例.md", "第一条 内容".encode())

    deleted = service.delete(document.id)

    assert deleted is True
    assert document.id not in store.documents
    assert not Path(document.file_path).exists()
