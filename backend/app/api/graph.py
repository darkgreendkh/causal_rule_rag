from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.models import GraphResponse


def create_graph_router(store: Any, research=None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["graph"])

    @router.get("/graph")
    def get_graph(
        document_id: str | None = None,
        limit: int = Query(default=300, ge=1, le=300),
        layer: str | None = None,
        matter_id: str | None = None,
        community_id: str | None = None,
        profile: str = "full",
    ) -> dict | GraphResponse:
        if layer is not None or matter_id or community_id:
            if layer not in (None, "macro", "micro", "fused"):
                raise HTTPException(status_code=422, detail="未知图层")
            try:
                return research.graph(layer or "fused", matter_id, community_id, limit, profile)
            except ValueError as error:
                raise HTTPException(status_code=422, detail=str(error)) from error
        return store.get_graph(document_id, limit)

    return router
