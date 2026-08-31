from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Response, UploadFile, status

from app.ingestion import DocumentService, DuplicateDocumentError, InvalidDocumentError
from app.models import ChunkView, DocumentSummary


def create_documents_router(service: DocumentService, store: Any) -> APIRouter:
    router = APIRouter(prefix="/api", tags=["documents"])

    @router.post(
        "/documents",
        response_model=DocumentSummary,
        status_code=status.HTTP_202_ACCEPTED,
    )
    async def upload_document(file: UploadFile, background_tasks: BackgroundTasks) -> DocumentSummary:
        try:
            document = service.create_upload(file.filename or "", await file.read())
        except DuplicateDocumentError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
        except InvalidDocumentError as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=str(error),
            ) from error
        background_tasks.add_task(service.process, document.id)
        return DocumentSummary.model_validate(document)

    @router.get("/documents", response_model=list[DocumentSummary])
    def list_documents() -> list[DocumentSummary]:
        return [DocumentSummary.model_validate(document) for document in store.list_documents()]

    @router.get("/documents/{document_id}/chunks", response_model=list[ChunkView])
    def list_chunks(document_id: str) -> list[ChunkView]:
        if not store.get_document(document_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        return store.list_chunks(document_id)

    @router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_document(document_id: str) -> Response:
        if not service.delete(document_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文档不存在")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router
