from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from pydantic import BaseModel, Field


class BuildRequest(BaseModel):
    profile: str = "full"


class ReviewRequest(BaseModel):
    rule_ids: list[str] = Field(min_length=1, max_length=1000)
    action: Literal["activate", "reject", "disable"]


class ExtractRequest(BaseModel):
    matter_id: str
    unit_ids: list[str] = Field(min_length=1, max_length=5)


class CaseRequest(BaseModel):
    matter_id: str
    region: str | None = None
    as_of: str | None = None
    facts: dict = Field(default_factory=dict)
    steps: list[str] = Field(default_factory=list, max_length=100)
    completed_steps: list[str] = Field(default_factory=list, max_length=100)
    goal: str | None = None
    profile: str = "full"


def create_research_router(service):
    router = APIRouter(prefix="/api/research", tags=["research"])

    def invoke(fn, *args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error

    def corpus():
        return invoke(service.snapshot)["corpus"]

    @router.get("/status")
    def status():
        return service.status()

    @router.post("/build", status_code=202)
    def build(request: BuildRequest, background: BackgroundTasks):
        from app.research_profiles import get_profile

        invoke(get_profile, request.profile)
        if service.status()["status"] == "building":
            raise HTTPException(status_code=409, detail="知识库正在构建")
        background.add_task(service.build, request.profile)
        return dict(
            service.status(), status="building", stage="构建已排队", profile=request.profile
        )

    @router.get("/summary")
    def summary():
        return service.summary()

    @router.get("/matters")
    def matters():
        return corpus()["matters"]

    @router.get("/matters/{matter_id}")
    def matter(matter_id: str):
        found = next((m for m in corpus()["matters"] if m["id"] == matter_id), None)
        if found is None:
            raise HTTPException(status_code=404, detail="事项不存在")
        return found

    @router.get("/rules")
    def rules(matter_id: str | None = None, status: str | None = None):
        return [
            r
            for r in corpus()["rules"]
            if (not matter_id or r["matter_id"] == matter_id)
            and (not status or r["status"] == status)
        ]

    @router.post("/rules/review")
    def review(request: ReviewRequest):
        return invoke(service.review, request.rule_ids, request.action)

    @router.post("/rules/extract")
    def extract(request: ExtractRequest):
        return invoke(service.extract_candidates, request.matter_id, request.unit_ids)

    @router.get("/actions")
    def actions(matter_id: str | None = None):
        return [a for a in corpus()["actions"] if not matter_id or a["matter_id"] == matter_id]

    @router.get("/units")
    def units(document_id: str | None = None):
        return [u for u in corpus()["units"] if not document_id or u["document_id"] == document_id]

    @router.get("/source/{unit_id}")
    def source(unit_id: str):
        found = next(
            (u for u in corpus()["units"] + corpus()["references"] if u["id"] == unit_id), None
        )
        if found is None:
            raise HTTPException(status_code=404, detail="来源不存在或已经失效")
        return found

    @router.get("/coverage")
    def coverage():
        return corpus()["coverage"]

    @router.delete("/documents/{document_id}")
    def remove_document(document_id: str):
        return invoke(service.remove_document, document_id)

    @router.get("/graph")
    def graph(
        layer: Literal["macro", "micro", "fused"] = "fused",
        matter_id: str | None = None,
        community_id: str | None = None,
        limit: int = Query(default=300, ge=1, le=10000),
        profile: str = "full",
    ):
        return invoke(service.graph, layer, matter_id, community_id, limit, profile)

    @router.post("/workflow/{operation}")
    def workflow(operation: Literal["check", "repair", "next"], request: CaseRequest):
        return invoke(service.workflow, operation, request.model_dump())

    return router
