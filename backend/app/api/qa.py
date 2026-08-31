from fastapi import APIRouter, HTTPException, status

from app.models import QARequest, QAResponse
from app.qa import QAService


def create_qa_router(service: QAService) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["qa"])

    @router.post("/qa", response_model=QAResponse)
    def answer_question(request: QARequest) -> QAResponse:
        try:
            return service.answer(request.question, request.mode)
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error

    return router
