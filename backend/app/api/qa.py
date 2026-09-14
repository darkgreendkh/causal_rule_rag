from fastapi import APIRouter, HTTPException, status

from app.models import QARequest, QAResponse, RetrievalMode
from app.qa import QAService


def create_qa_router(service: QAService, research=None) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["qa"])

    @router.post("/qa", response_model=QAResponse)
    def answer_question(request: QARequest) -> QAResponse:
        try:
            if request.mode == RetrievalMode.CAUSAL or request.dataset == "research":
                return research.answer(request.model_dump(mode="json"))
            return service.answer(request.question, request.mode, request.history)
        except ValueError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except Exception as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=str(error),
            ) from error

    return router
