import re

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError
from neo4j.time import DateTime as Neo4jDateTime

from app.config import Settings
from app.models import (
    ChunkRecord,
    ChunkView,
    DocumentRecord,
    DocumentStatus,
    GraphEdge,
    GraphNode,
    GraphPath,
    GraphResponse,
    Source,
    SourceChannel,
    Triple,
)

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
        self._driver.execute_query("CALL db.awaitIndexes(30)")
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
        return [_document_from_node(record["d"]) for record in records]

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

    def vector_search(self, embedding: list[float], limit: int) -> list[Source]:
        records, _, _ = self._driver.execute_query(
            """CALL db.index.vector.queryNodes(
                 'chunk_embedding', $candidate_count, $embedding
               ) YIELD node AS chunk, score
               MATCH (document:Document {status: 'COMPLETED'})-[:HAS_CHUNK]->(chunk)
               RETURN chunk.id AS chunk_id,
                      document.id AS document_id,
                      document.filename AS filename,
                      chunk.index AS chunk_index,
                      chunk.text AS text,
                      chunk.heading AS heading,
                      chunk.article_no AS article_no,
                      score
               ORDER BY score DESC
               LIMIT $limit""",
            embedding=embedding,
            candidate_count=max(limit * 4, limit),
            limit=limit,
        )
        return [
            Source(
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
                filename=record["filename"],
                chunk_index=record["chunk_index"],
                text=record["text"],
                heading=record["heading"],
                article_no=record["article_no"],
                score=record["score"],
                channel=SourceChannel.VECTOR,
            )
            for record in records
        ]

    def graph_expand(
        self, seeds: list[Source], limit: int
    ) -> tuple[list[Source], list[GraphPath]]:
        if not seeds:
            return [], []
        seed_rows = [
            {"chunk_id": source.chunk_id, "score": source.score or 0.0} for source in seeds
        ]
        seed_ids = [source.chunk_id for source in seeds]
        records, _, _ = self._driver.execute_query(
            """UNWIND $seeds AS seed
               MATCH (seed_chunk:Chunk {id: seed.chunk_id})-[:MENTIONS]->(seed_entity:Entity)
               MATCH (seed_entity)-[relation:RELATES_TO]-(related:Entity)
               MATCH (candidate:Chunk)-[:MENTIONS]->(related)
               MATCH (document:Document {status: 'COMPLETED'})-[:HAS_CHUNK]->(candidate)
               WHERE NOT candidate.id IN $seed_ids
               WITH candidate,
                    document,
                    count(DISTINCT relation) AS path_count,
                    max(seed.score) AS score,
                    collect(DISTINCT {
                      subject: startNode(relation).name,
                      predicate: relation.predicate,
                      object: endNode(relation).name,
                      source_chunk_id: relation.source_chunk_id
                    }) AS paths
               ORDER BY path_count DESC, score DESC, candidate.index
               LIMIT $limit
               RETURN candidate.id AS chunk_id,
                      document.id AS document_id,
                      document.filename AS filename,
                      candidate.index AS chunk_index,
                      candidate.text AS text,
                      candidate.heading AS heading,
                      candidate.article_no AS article_no,
                      score,
                      paths""",
            seeds=seed_rows,
            seed_ids=seed_ids,
            limit=limit,
        )
        sources = [
            Source(
                chunk_id=record["chunk_id"],
                document_id=record["document_id"],
                filename=record["filename"],
                chunk_index=record["chunk_index"],
                text=record["text"],
                heading=record["heading"],
                article_no=record["article_no"],
                score=record["score"],
                channel=SourceChannel.GRAPH,
            )
            for record in records
        ]
        paths: list[GraphPath] = []
        seen_paths: set[tuple[str, str, str, str]] = set()
        for record in records:
            for path in record["paths"]:
                key = (
                    path["subject"],
                    path["predicate"],
                    path["object"],
                    path["source_chunk_id"],
                )
                if key in seen_paths:
                    continue
                seen_paths.add(key)
                paths.append(GraphPath(**path))
        return sources, paths

    def get_graph(self, document_id: str | None, limit: int) -> GraphResponse:
        records, _, _ = self._driver.execute_query(
            """MATCH (document:Document {status: 'COMPLETED'})-[:HAS_CHUNK]
                     ->(chunk:Chunk)-[:MENTIONS]->(entity:Entity)
               WHERE $document_id IS NULL OR document.id = $document_id
               RETURN entity, collect(DISTINCT chunk.id) AS source_chunk_ids
               ORDER BY entity.name
               LIMIT $fetch_limit""",
            document_id=document_id,
            fetch_limit=limit + 1,
        )
        truncated = len(records) > limit
        visible_records = records[:limit]
        nodes = [
            GraphNode(
                id=record["entity"]["key"],
                label=record["entity"]["name"],
                type=record["entity"]["type"],
                source_chunk_ids=record["source_chunk_ids"],
            )
            for record in visible_records
        ]
        entity_keys = [node.id for node in nodes]
        if not entity_keys:
            return GraphResponse(nodes=[], edges=[], truncated=truncated)

        edge_records, _, _ = self._driver.execute_query(
            """MATCH (subject:Entity)-[relation:RELATES_TO]->(object:Entity)
               WHERE subject.key IN $entity_keys
                 AND object.key IN $entity_keys
                 AND ($document_prefix IS NULL
                   OR relation.source_chunk_id STARTS WITH $document_prefix)
               RETURN subject.key AS source,
                      object.key AS target,
                      relation.predicate AS predicate,
                      relation.source_chunk_id AS source_chunk_id""",
            entity_keys=entity_keys,
            document_prefix=f"{document_id}:" if document_id else None,
        )
        edges = [
            GraphEdge(
                id=(
                    f"{record['source']}|{record['predicate']}|"
                    f"{record['target']}|{record['source_chunk_id']}"
                ),
                source=record["source"],
                target=record["target"],
                predicate=record["predicate"],
                source_chunk_id=record["source_chunk_id"],
            )
            for record in edge_records
        ]
        return GraphResponse(nodes=nodes, edges=edges, truncated=truncated)

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
               WHERE NOT EXISTS { MATCH (:Chunk)-[:MENTIONS]->(e) }
                 AND NOT EXISTS { MATCH (e)-[:RELATES_TO]-() }
               DELETE e"""
        )

    def close(self) -> None:
        self._driver.close()


def _document_from_records(records: list) -> DocumentRecord | None:
    if not records:
        return None
    return _document_from_node(records[0]["d"])


def _document_from_node(node: object) -> DocumentRecord:
    values = dict(node)
    if isinstance(values.get("created_at"), Neo4jDateTime):
        values["created_at"] = values["created_at"].to_native()
    return DocumentRecord.model_validate(values)


def _clean_entity_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip()
