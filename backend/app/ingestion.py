import hashlib
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from app.chunking import chunk_document
from app.models import ChunkRecord, DocumentRecord, DocumentStatus, Triple


class DocumentStore(Protocol):
    def create_document(self, document: DocumentRecord) -> None: ...

    def find_document_by_sha256(self, sha256: str) -> DocumentRecord | None: ...

    def get_document(self, document_id: str) -> DocumentRecord | None: ...

    def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        *,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        error: str | None = None,
    ) -> None: ...

    def save_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None: ...

    def save_triples(self, document_id: str, chunk_id: str, triples: list[Triple]) -> None: ...

    def cleanup_derived(self, document_id: str) -> None: ...

    def delete_document(self, document_id: str) -> DocumentRecord | None: ...


class Embedder(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


class Extractor(Protocol):
    def extract(self, text: str) -> list[Triple]: ...


class InvalidDocumentError(ValueError):
    pass


class DuplicateDocumentError(ValueError):
    pass


class DocumentService:
    def __init__(
        self,
        store: DocumentStore,
        embedder: Embedder,
        extractor: Extractor,
        uploads_dir: Path,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._extractor = extractor
        self._uploads_dir = uploads_dir

    def create_upload(self, filename: str, content: bytes) -> DocumentRecord:
        safe_name = Path(filename).name
        suffix = Path(safe_name).suffix.lower()
        if suffix not in {".txt", ".md"}:
            raise InvalidDocumentError("仅支持 .txt 和 .md 文件")
        if not content:
            raise InvalidDocumentError("文件不能为空")
        try:
            decoded = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise InvalidDocumentError("文件必须使用 UTF-8 编码") from error
        if not decoded.strip():
            raise InvalidDocumentError("文件不能为空")

        sha256 = hashlib.sha256(content).hexdigest()
        if self._store.find_document_by_sha256(sha256):
            raise DuplicateDocumentError("相同内容的文档已存在")

        document_id = str(uuid4())
        self._uploads_dir.mkdir(parents=True, exist_ok=True)
        file_path = self._uploads_dir / f"{document_id}{suffix}"
        file_path.write_bytes(content)
        document = DocumentRecord(
            id=document_id,
            filename=safe_name,
            file_path=str(file_path),
            sha256=sha256,
        )
        self._store.create_document(document)
        return document

    def process(self, document_id: str) -> None:
        document = self._store.get_document(document_id)
        if not document:
            return

        try:
            self._store.update_document_status(document_id, DocumentStatus.PARSING)
            text = Path(document.file_path).read_text(encoding="utf-8")
            parsed_chunks = chunk_document(text)
            if not parsed_chunks:
                raise InvalidDocumentError("文档没有可处理的文本")

            self._store.update_document_status(
                document_id,
                DocumentStatus.EMBEDDING,
                total_chunks=len(parsed_chunks),
                processed_chunks=0,
            )
            embeddings = self._embedder.embed([chunk.text for chunk in parsed_chunks])
            chunks = [
                ChunkRecord(
                    id=f"{document_id}:{chunk.index}",
                    document_id=document_id,
                    index=chunk.index,
                    text=chunk.text,
                    heading=chunk.heading,
                    article_no=chunk.article_no,
                    embedding=embedding,
                )
                for chunk, embedding in zip(parsed_chunks, embeddings, strict=True)
            ]
            self._store.save_chunks(document_id, chunks)

            self._store.update_document_status(
                document_id,
                DocumentStatus.EXTRACTING_GRAPH,
                total_chunks=len(chunks),
                processed_chunks=0,
            )
            for processed, chunk in enumerate(chunks, start=1):
                triples = self._extractor.extract(chunk.text)
                self._store.save_triples(document_id, chunk.id, triples)
                self._store.update_document_status(
                    document_id,
                    DocumentStatus.EXTRACTING_GRAPH,
                    total_chunks=len(chunks),
                    processed_chunks=processed,
                )

            self._store.update_document_status(
                document_id,
                DocumentStatus.COMPLETED,
                total_chunks=len(chunks),
                processed_chunks=len(chunks),
            )
        except Exception as error:  # noqa: BLE001 - background task must persist failures
            self._store.cleanup_derived(document_id)
            self._store.update_document_status(
                document_id,
                DocumentStatus.FAILED,
                processed_chunks=0,
                error=str(error),
            )

    def delete(self, document_id: str) -> bool:
        document = self._store.delete_document(document_id)
        if not document:
            return False
        Path(document.file_path).unlink(missing_ok=True)
        return True
