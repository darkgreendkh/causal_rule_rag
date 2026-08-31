from typing import Any

from fastapi import APIRouter, Query

from app.models import GraphResponse


def create_graph_router(store: Any) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["graph"])

    @router.get("/graph", response_model=GraphResponse)
    def get_graph(
        document_id: str | None = None,
        limit: int = Query(default=300, ge=1, le=300),
    ) -> GraphResponse:
        return store.get_graph(document_id, limit)

    return router
