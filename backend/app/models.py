from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, StringConstraints


class EntityType(StrEnum):
    LAW = "LAW"
    ARTICLE = "ARTICLE"
    AGENCY = "AGENCY"
    PERSON_ROLE = "PERSON_ROLE"
    ORGANIZATION = "ORGANIZATION"
    LEGAL_CONCEPT = "LEGAL_CONCEPT"
    ACTION = "ACTION"
    RIGHT = "RIGHT"
    OBLIGATION = "OBLIGATION"
    PENALTY = "PENALTY"
    OTHER = "OTHER"


class DocumentStatus(StrEnum):
    PENDING = "PENDING"
    PARSING = "PARSING"
    EMBEDDING = "EMBEDDING"
    EXTRACTING_GRAPH = "EXTRACTING_GRAPH"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class RetrievalMode(StrEnum):
    VECTOR = "vector"
    HYBRID = "hybrid"


class SourceChannel(StrEnum):
    VECTOR = "vector"
    GRAPH = "graph"


class DocumentRecord(BaseModel):
    id: str
    filename: str
    file_path: str
    sha256: str
    status: DocumentStatus = DocumentStatus.PENDING
    total_chunks: int = 0
    processed_chunks: int = 0
    error: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ChunkRecord(BaseModel):
    id: str
    document_id: str
    index: int
    text: str
    heading: str | None = None
    article_no: str | None = None
    embedding: list[float]


class DocumentSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    filename: str
    sha256: str
    status: DocumentStatus
    total_chunks: int
    processed_chunks: int
    error: str | None
    created_at: datetime


class ChunkView(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str
    index: int
    text: str
    heading: str | None = None
    article_no: str | None = None


class Source(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    chunk_index: int
    text: str
    heading: str | None = None
    article_no: str | None = None
    score: float | None = None
    channel: SourceChannel


class GraphPath(BaseModel):
    subject: str
    predicate: str
    object: str
    source_chunk_id: str


class QAResponse(BaseModel):
    answer: str
    mode: RetrievalMode
    sources: list[Source]
    graph_paths: list[GraphPath]


class ConversationTurn(BaseModel):
    question: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
    ]
    answer: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)
    ]


class QARequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
    mode: RetrievalMode
    history: list[ConversationTurn] = Field(default_factory=list, max_length=3)


class GraphNode(BaseModel):
    id: str
    label: str
    type: str
    source_chunk_ids: list[str]


class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    predicate: str
    source_chunk_id: str


class GraphResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    truncated: bool


class Triple(BaseModel):
    subject: str
    subject_type: EntityType
    predicate: str
    object: str
    object_type: EntityType


class TriplePayload(BaseModel):
    triples: list[Triple]
