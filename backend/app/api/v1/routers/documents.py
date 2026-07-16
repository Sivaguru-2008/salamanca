from __future__ import annotations

import uuid
from pathlib import Path

from fastapi import APIRouter, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.deps import CurrentUser, DbSession, SettingsDep
from app.api.v1.schemas.ai import DocumentSearchResponse
from app.api.v1.schemas.common import PROBLEM_RESPONSES
from app.api.v1.schemas.financial import FinancialDocumentRead
from app.core.errors import NotFoundError
from app.domain.documents.service import DocumentsService

router = APIRouter(prefix="/documents", tags=["documents"], responses=PROBLEM_RESPONSES)


@router.post(
    "/upload",
    response_model=FinancialDocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document (stored, text-extracted, and chunked for retrieval)",
)
async def upload_document(
    file: UploadFile,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
) -> FinancialDocumentRead:
    document = await DocumentsService(db, settings).upload(user.id, file)
    return FinancialDocumentRead.model_validate(document)


@router.get(
    "/{doc_id}/search",
    response_model=DocumentSearchResponse,
    summary="Similarity-search the chunks of an uploaded document",
)
async def search_document(
    doc_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
    query: str = Query(..., min_length=1, max_length=500),
    limit: int = Query(default=5, ge=1, le=20),
) -> DocumentSearchResponse:
    result = await DocumentsService(db, settings).search(user.id, doc_id, query, limit)
    return DocumentSearchResponse(**result)


@router.get("/{doc_id}/download", summary="Download the original uploaded file")
async def download_document(
    doc_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
) -> FileResponse:
    document = await DocumentsService(db, settings).get_owned(user.id, doc_id)
    path = Path(document.file_path)
    if not path.is_file():
        raise NotFoundError("Stored file is missing on the server.")
    return FileResponse(path, filename=document.name)


@router.delete(
    "/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an uploaded document (metadata and stored file)",
)
async def delete_document(
    doc_id: uuid.UUID,
    user: CurrentUser,
    db: DbSession,
    settings: SettingsDep,
) -> None:
    await DocumentsService(db, settings).delete(user.id, doc_id)
