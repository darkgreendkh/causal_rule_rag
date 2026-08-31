from datetime import UTC, datetime

from neo4j.time import DateTime as Neo4jDateTime

from app.database import _document_from_records
from app.models import ChunkView


def test_document_from_records_converts_neo4j_datetime() -> None:
    created_at = datetime(2026, 8, 31, 12, 30, tzinfo=UTC)
    records = [
        {
            "d": {
                "id": "document-1",
                "filename": "law.md",
                "file_path": "/tmp/law.md",
                "sha256": "abc123",
                "status": "PENDING",
                "total_chunks": 0,
                "processed_chunks": 0,
                "error": None,
                "created_at": Neo4jDateTime.from_native(created_at),
            }
        }
    ]

    document = _document_from_records(records)

    assert document is not None
    assert document.created_at == created_at


def test_chunk_view_defaults_missing_optional_neo4j_properties() -> None:
    chunk = ChunkView.model_validate(
        {
            "id": "document-1:0",
            "document_id": "document-1",
            "index": 0,
            "text": "第一条 测试内容",
        }
    )

    assert chunk.heading is None
    assert chunk.article_no is None
