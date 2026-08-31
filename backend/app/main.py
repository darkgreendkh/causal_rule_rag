from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import Settings
from app.database import Neo4jStore


def create_app(store: Any | None = None, settings: Settings | None = None) -> FastAPI:
    app_settings = settings or Settings()
    app_store = store or Neo4jStore(app_settings)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        yield
        close = getattr(app_store, "close", None)
        if close:
            close()

    application = FastAPI(title="Causal Rule RAG", lifespan=lifespan)
    application.state.settings = app_settings
    application.state.store = app_store
    application.add_middleware(
        CORSMiddleware,
        allow_origins=app_settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.get("/api/health")
    def health() -> dict[str, object]:
        neo4j_ready = app_store.health()
        return {
            "status": "ready" if neo4j_ready else "degraded",
            "neo4j": neo4j_ready,
            "embedding_model": app_settings.embedding_model,
            "llm_configured": app_settings.llm_configured,
        }

    return application


app = create_app()
