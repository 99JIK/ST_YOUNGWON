from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File

from backend.app.config import settings
from backend.app.core.progress import get_progress
from backend.app.dependencies import get_document_service, verify_admin
from backend.app.models.schemas import DocumentListResponse, DocumentUploadResponse
from backend.app.services.document_service import DocumentService
from backend.app.utils.file_parser import is_extractable

router = APIRouter()


@router.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    task_id: str = Form(default=""),
    _admin: bool = Depends(verify_admin),
    doc_service: DocumentService = Depends(get_document_service),
):
    """문서를 업로드하고 인덱싱합니다. (PDF, DOCX, XLSX, PPTX, TXT 등)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")
    if not is_extractable(file.filename):
        raise HTTPException(
            status_code=400,
            detail="텍스트를 추출할 수 없는 파일 형식입니다. (PDF, DOCX, XLSX, PPTX, TXT, MD, CSV 등 지원)",
        )

    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기는 {settings.max_upload_size_mb}MB 이하여야 합니다.",
        )

    try:
        result = await asyncio.to_thread(
            doc_service.upload_and_index, file.filename, content, task_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"문서 처리 중 오류 발생: {str(e)}")


@router.get("/api/documents/progress/{task_id}")
async def get_upload_progress(task_id: str):
    """문서 업로드/인덱싱 진행률을 조회합니다."""
    progress = get_progress(task_id)
    if progress is None:
        return {"step": "unknown", "percent": 0, "detail": ""}
    return progress


@router.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(
    _admin: bool = Depends(verify_admin),
    doc_service: DocumentService = Depends(get_document_service),
):
    """인덱싱된 문서 목록을 반환합니다."""
    documents = doc_service.list_documents()
    return DocumentListResponse(
        documents=documents,
        total_count=len(documents),
    )


@router.delete("/api/documents/{doc_id}")
async def delete_document(
    doc_id: str,
    _admin: bool = Depends(verify_admin),
    doc_service: DocumentService = Depends(get_document_service),
):
    """문서를 삭제합니다."""
    success = doc_service.delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
    return {"message": "문서가 삭제되었습니다.", "id": doc_id}
