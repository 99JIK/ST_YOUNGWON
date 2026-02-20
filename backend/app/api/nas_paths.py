from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile

from backend.app.config import settings
from backend.app.dependencies import get_nas_path_service, verify_admin
from backend.app.models.schemas import (
    NASFileListResponse,
    NASPathEntry,
    NASPathSearchResult,
)
from backend.app.services.nas_path_service import NASPathService

router = APIRouter()


@router.get("/api/nas/search", response_model=NASPathSearchResult)
async def search_nas_paths(
    q: str = Query(..., description="검색어"),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 파일 경로를 검색합니다."""
    results = nas_service.search_paths(q)
    return NASPathSearchResult(entries=results, total_count=len(results))


@router.get("/api/nas/paths", response_model=list[NASPathEntry])
async def list_nas_paths(
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """모든 NAS 경로 목록을 반환합니다."""
    return nas_service.list_paths()


@router.post("/api/nas/paths", response_model=NASPathEntry)
async def add_nas_path(
    entry: NASPathEntry,
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 경로를 추가합니다."""
    return nas_service.add_path(entry)


@router.put("/api/nas/paths/{path_id}", response_model=NASPathEntry)
async def update_nas_path(
    path_id: str,
    entry: NASPathEntry,
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 경로를 수정합니다."""
    result = nas_service.update_path(path_id, entry)
    if not result:
        raise HTTPException(status_code=404, detail="경로를 찾을 수 없습니다.")
    return result


@router.delete("/api/nas/paths/{path_id}")
async def delete_nas_path(
    path_id: str,
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 경로를 삭제합니다."""
    success = nas_service.delete_path(path_id)
    if not success:
        raise HTTPException(status_code=404, detail="경로를 찾을 수 없습니다.")
    return {"message": "경로가 삭제되었습니다.", "id": path_id}


# === NAS 파일 관리 ===


@router.post("/api/nas/files/upload")
async def upload_nas_file(
    file: UploadFile = File(...),
    category: str = Form(default=""),
    task_id: str = Form(default=""),
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 파일을 업로드합니다. 읽기 가능한 파일은 자동으로 벡터DB에 인덱싱됩니다."""
    filename = file.filename or "unknown"

    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기는 {settings.max_upload_size_mb}MB 이하여야 합니다.",
        )

    try:
        result = await asyncio.to_thread(
            nas_service.upload_file, filename, content, category, task_id
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 처리 실패: {e}")


@router.get("/api/nas/files", response_model=NASFileListResponse)
async def list_nas_files(
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """업로드된 NAS 파일 목록을 반환합니다."""
    files = nas_service.list_files()
    return NASFileListResponse(files=files, total_count=len(files))


@router.delete("/api/nas/files/{file_id}")
async def delete_nas_file(
    file_id: str,
    _admin: bool = Depends(verify_admin),
    nas_service: NASPathService = Depends(get_nas_path_service),
):
    """NAS 파일을 삭제합니다."""
    success = nas_service.delete_file(file_id)
    if not success:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return {"message": "파일이 삭제되었습니다.", "id": file_id}
