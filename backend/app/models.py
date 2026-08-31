from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


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
    heading: str | None
    article_no: str | None


class Triple(BaseModel):
    subject: str
    subject_type: EntityType
    predicate: str
    object: str
    object_type: EntityType


class TriplePayload(BaseModel):
    triples: list[Triple]
