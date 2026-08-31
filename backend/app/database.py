import re

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError

from app.config import Settings
from app.models import ChunkRecord, ChunkView, DocumentRecord, DocumentStatus, Triple

CONSTRAINTS_AND_INDEXES = [
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT document_sha256 IF NOT EXISTS FOR (d:Document) REQUIRE d.sha256 IS UNIQUE",
    "CREATE CONSTRAINT chunk_id IF NOT EXISTS FOR (c:Chunk) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT entity_key IF NOT EXISTS FOR (e:Entity) REQUIRE e.key IS UNIQUE",
    """CREATE VECTOR INDEX chunk_embedding IF NOT EXISTS
       FOR (c:Chunk) ON (c.embedding)
       OPTIONS {indexConfig: {
         `vector.dimensions`: 1024,
         `vector.similarity_function`: 'cosine'
       }}""",
]


class Neo4jStore:
    def __init__(self, settings: Settings) -> None:
        self._driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def health(self) -> bool:
        try:
            self._driver.verify_connectivity()
        except (Neo4jError, OSError):
            return False
        return True

    def initialize(self) -> None:
        for statement in CONSTRAINTS_AND_INDEXES:
            self._driver.execute_query(statement)
        records, _, _ = self._driver.execute_query(
            """MATCH (d:Document)
               WHERE d.status IN $statuses
               RETURN d.id AS id""",
            statuses=[
                DocumentStatus.PENDING.value,
                DocumentStatus.PARSING.value,
                DocumentStatus.EMBEDDING.value,
                DocumentStatus.EXTRACTING_GRAPH.value,
            ],
        )
        for record in records:
            document_id = record["id"]
            self.cleanup_derived(document_id)
            self.update_document_status(
                document_id,
                DocumentStatus.FAILED,
                processed_chunks=0,
                error="服务重启导致任务中断",
            )

    def create_document(self, document: DocumentRecord) -> None:
        self._driver.execute_query(
            """CREATE (d:Document {
                 id: $id,
                 filename: $filename,
                 file_path: $file_path,
                 sha256: $sha256,
                 status: $status,
                 total_chunks: $total_chunks,
                 processed_chunks: $processed_chunks,
                 error: $error,
                 created_at: $created_at
               })""",
            parameters_=document.model_dump(mode="python"),
        )

    def find_document_by_sha256(self, sha256: str) -> DocumentRecord | None:
        records, _, _ = self._driver.execute_query(
            "MATCH (d:Document {sha256: $sha256}) RETURN d LIMIT 1",
            sha256=sha256,
        )
        return _document_from_records(records)

    def get_document(self, document_id: str) -> DocumentRecord | None:
        records, _, _ = self._driver.execute_query(
            "MATCH (d:Document {id: $document_id}) RETURN d LIMIT 1",
            document_id=document_id,
        )
        return _document_from_records(records)

    def list_documents(self) -> list[DocumentRecord]:
        records, _, _ = self._driver.execute_query(
            "MATCH (d:Document) RETURN d ORDER BY d.created_at DESC"
        )
        return [DocumentRecord.model_validate(dict(record["d"])) for record in records]

    def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        *,
        total_chunks: int | None = None,
        processed_chunks: int | None = None,
        error: str | None = None,
    ) -> None:
        self._driver.execute_query(
            """MATCH (d:Document {id: $document_id})
               SET d.status = $status,
                   d.total_chunks = CASE
                     WHEN $total_chunks IS NULL THEN d.total_chunks ELSE $total_chunks END,
                   d.processed_chunks = CASE
                     WHEN $processed_chunks IS NULL THEN d.processed_chunks
                     ELSE $processed_chunks END,
                   d.error = $error""",
            document_id=document_id,
            status=status.value,
            total_chunks=total_chunks,
            processed_chunks=processed_chunks,
            error=error,
        )

    def save_chunks(self, document_id: str, chunks: list[ChunkRecord]) -> None:
        self._driver.execute_query(
            """MATCH (d:Document {id: $document_id})
               UNWIND $chunks AS row
               CREATE (c:Chunk {
                 id: row.id,
                 document_id: row.document_id,
                 index: row.index,
                 text: row.text,
                 heading: row.heading,
                 article_no: row.article_no,
                 embedding: row.embedding
               })
               CREATE (d)-[:HAS_CHUNK]->(c)""",
            document_id=document_id,
            chunks=[chunk.model_dump(mode="python") for chunk in chunks],
        )

    def save_triples(self, document_id: str, chunk_id: str, triples: list[Triple]) -> None:
        if not triples:
            return
        rows = []
        for triple in triples:
            subject_name = _clean_entity_name(triple.subject)
            object_name = _clean_entity_name(triple.object)
            rows.append(
                {
                    "subject_key": f"{triple.subject_type.value}:{subject_name.casefold()}",
                    "subject_name": subject_name,
                    "subject_type": triple.subject_type.value,
                    "predicate": " ".join(triple.predicate.split()),
                    "object_key": f"{triple.object_type.value}:{object_name.casefold()}",
                    "object_name": object_name,
                    "object_type": triple.object_type.value,
                }
            )
        self._driver.execute_query(
            """MATCH (c:Chunk {id: $chunk_id})
               UNWIND $triples AS row
               MERGE (subject:Entity {key: row.subject_key})
                 ON CREATE SET subject.name = row.subject_name, subject.type = row.subject_type
               MERGE (object:Entity {key: row.object_key})
                 ON CREATE SET object.name = row.object_name, object.type = row.object_type
               MERGE (c)-[:MENTIONS]->(subject)
               MERGE (c)-[:MENTIONS]->(object)
               MERGE (subject)-[:RELATES_TO {
                 predicate: row.predicate,
                 source_chunk_id: $chunk_id
               }]->(object)""",
            document_id=document_id,
            chunk_id=chunk_id,
            triples=rows,
        )

    def list_chunks(self, document_id: str) -> list[ChunkView]:
        records, _, _ = self._driver.execute_query(
            """MATCH (:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
               RETURN c ORDER BY c.index""",
            document_id=document_id,
        )
        return [ChunkView.model_validate(dict(record["c"])) for record in records]

    def cleanup_derived(self, document_id: str) -> None:
        records, _, _ = self._driver.execute_query(
            """MATCH (:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
               RETURN collect(c.id) AS chunk_ids""",
            document_id=document_id,
        )
        chunk_ids = records[0]["chunk_ids"] if records else []
        if chunk_ids:
            self._driver.execute_query(
                """MATCH ()-[r:RELATES_TO]->()
                   WHERE r.source_chunk_id IN $chunk_ids
                   DELETE r""",
                chunk_ids=chunk_ids,
            )
            self._driver.execute_query(
                """MATCH (:Document {id: $document_id})-[:HAS_CHUNK]->(c:Chunk)
                   DETACH DELETE c""",
                document_id=document_id,
            )
        self._delete_orphan_entities()

    def delete_document(self, document_id: str) -> DocumentRecord | None:
        document = self.get_document(document_id)
        if not document:
            return None
        self.cleanup_derived(document_id)
        self._driver.execute_query(
            "MATCH (d:Document {id: $document_id}) DETACH DELETE d",
            document_id=document_id,
        )
        self._delete_orphan_entities()
        return document

    def _delete_orphan_entities(self) -> None:
        self._driver.execute_query(
            """MATCH (e:Entity)
               WHERE NOT (:Chunk)-[:MENTIONS]->(e) AND NOT (e)-[:RELATES_TO]-()
               DELETE e"""
        )

    def close(self) -> None:
        self._driver.close()


def _document_from_records(records: list) -> DocumentRecord | None:
    if not records:
        return None
    return DocumentRecord.model_validate(dict(records[0]["d"]))


def _clean_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()
