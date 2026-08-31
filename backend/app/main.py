import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from neo4j.exceptions import Neo4jError

from app.api.documents import create_documents_router
from app.api.graph import create_graph_router
from app.api.qa import create_qa_router
from app.config import Settings
from app.database import Neo4jStore
from app.embedding import SentenceTransformerEmbedder
from app.extraction import GraphExtractor
from app.ingestion import DocumentService
from app.llm import OpenAIChatModel, UnavailableChatModel
from app.qa import QAService

LOGGER = logging.getLogger(__name__)


def create_app(
    store: Any | None = None,
    settings: Settings | None = None,
    document_service: DocumentService | None = None,
    qa_service: QAService | None = None,
) -> FastAPI:
    app_settings = settings or Settings()
    app_store = store or Neo4jStore(app_settings)
    if document_service is None or qa_service is None:
        chat_model = (
            OpenAIChatModel(
                app_settings.llm_model,
                base_url=app_settings.llm_base_url,
                api_key=app_settings.llm_api_key,
            )
            if app_settings.llm_configured
            else UnavailableChatModel()
        )
        embedder = SentenceTransformerEmbedder(app_settings.embedding_model)
        if document_service is None:
            document_service = DocumentService(
                app_store,
                embedder,
                GraphExtractor(chat_model),
                app_settings.uploads_dir,
            )
        if qa_service is None:
            qa_service = QAService(app_store, embedder, chat_model)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        initialize = getattr(app_store, "initialize", None)
        if initialize:
            try:
                initialize()
            except (Neo4jError, OSError) as error:
                application.state.initialization_error = str(error)
                LOGGER.warning("Neo4j initialization failed: %s", error)
        yield
        close = getattr(app_store, "close", None)
        if close:
            close()

    application = FastAPI(title="Causal Rule RAG", lifespan=lifespan)
    application.state.settings = app_settings
    application.state.store = app_store
    application.state.document_service = document_service
    application.state.qa_service = qa_service
    application.state.initialization_error = None
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/api/health")
    def health() -> dict[str, object]:
        neo4j_ready = app_store.health() and not application.state.initialization_error
        return {
            "status": "ready" if neo4j_ready else "degraded",
            "neo4j": neo4j_ready,
            "embedding_model": app_settings.embedding_model,
            "llm_configured": app_settings.llm_configured,
        }

    application.include_router(create_documents_router(document_service, app_store))
    application.include_router(create_graph_router(app_store))
    application.include_router(create_qa_router(qa_service))
    return application


app = create_app()
