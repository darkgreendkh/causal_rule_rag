import os
from pathlib import Path
from uuid import uuid4

import pytest

from app.config import Settings
from app.database import Neo4jStore
from app.models import (
    ChunkRecord,
    DocumentRecord,
    DocumentStatus,
    EntityType,
    Triple,
)


@pytest.mark.integration
def test_neo4j_store_indexes_graph_and_cleans_document(tmp_path: Path) -> None:
    uri = os.getenv("NEO4J_TEST_URI")
    if not uri:
        pytest.skip("set NEO4J_TEST_URI to run Neo4j integration tests")

    settings = Settings(
        neo4j_uri=uri,
        neo4j_user=os.getenv("NEO4J_TEST_USER", "neo4j"),
        neo4j_password=os.getenv("NEO4J_TEST_PASSWORD", "change-me"),
        uploads_dir=tmp_path,
    )
    store = Neo4jStore(settings)
    document_id = str(uuid4())
    document = DocumentRecord(
        id=document_id,
        filename="integration.md",
        file_path=str(tmp_path / "integration.md"),
        sha256=uuid4().hex,
        status=DocumentStatus.COMPLETED,
        total_chunks=1,
        processed_chunks=1,
    )
    chunk = ChunkRecord(
        id=f"{document_id}:0",
        document_id=document_id,
        index=0,
        text="数据处理者应当履行安全义务。",
        article_no="第一条",
        embedding=[0.0] * 1023 + [1.0],
    )
    triple = Triple(
        subject="数据处理者",
        subject_type=EntityType.PERSON_ROLE,
        predicate="履行",
        object="安全义务",
        object_type=EntityType.OBLIGATION,
    )

    try:
        store.initialize()
        store.create_document(document)
        store.save_chunks(document_id, [chunk])
        store.save_triples(document_id, chunk.id, [triple])

        assert [item.id for item in store.list_chunks(document_id)] == [chunk.id]
        assert store.vector_search(chunk.embedding, limit=1)[0].chunk_id == chunk.id
        graph = store.get_graph(document_id, limit=300)
        assert {node.label for node in graph.nodes} == {"数据处理者", "安全义务"}
        assert [(edge.predicate, edge.source_chunk_id) for edge in graph.edges] == [
            ("履行", chunk.id)
        ]

        deleted = store.delete_document(document_id)
        assert deleted is not None
        assert store.get_document(document_id) is None
        assert store.list_chunks(document_id) == []
    finally:
        if store.get_document(document_id):
            store.delete_document(document_id)
        store.close()
