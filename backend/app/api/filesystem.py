from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse

from backend.app.config import settings
from backend.app.core.progress import get_progress
from backend.app.dependencies import get_current_user, get_filesystem_service, verify_admin
from backend.app.models.schemas import (
    CreateFolderRequest,
    FolderItem,
    FolderListResponse,
)
from backend.app.services.filesystem_service import FileSystemService

router = APIRouter()


@router.get("/api/files/browse", response_model=FolderListResponse)
async def browse_files(
    path: str = Query(default="/"),
    _user: dict = Depends(get_current_user),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """실제 디렉토리 내용을 조회합니다. (인증된 모든 유저)"""
    return fs_service.browse(path)


@router.post("/api/files/folders", response_model=FolderItem)
async def create_folder(
    request: CreateFolderRequest,
    _admin: dict = Depends(verify_admin),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """실제 디렉토리를 생성합니다. (관리자 전용)"""
    try:
        return fs_service.create_folder(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/files/folders")
async def delete_folder(
    path: str = Query(default="/"),
    name: str = Query(...),
    _admin: dict = Depends(verify_admin),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """빈 폴더를 삭제합니다. (관리자 전용)"""
    success = fs_service.delete_folder(path, name)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="폴더를 삭제할 수 없습니다. 폴더가 비어있는지 확인하세요.",
        )
    return {"message": "폴더가 삭제되었습니다."}


@router.delete("/api/files/file")
async def delete_file(
    path: str = Query(default="/"),
    filename: str = Query(...),
    _admin: dict = Depends(verify_admin),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """파일을 삭제합니다. (관리자 전용)"""
    success = fs_service.delete_file(path, filename)
    if not success:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return {"message": "파일이 삭제되었습니다."}


@router.get("/api/files/download")
async def download_file(
    path: str = Query(default="/"),
    filename: str = Query(...),
    _user: dict = Depends(get_current_user),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """파일을 다운로드합니다. (인증된 모든 유저)"""
    file_path = fs_service.get_file_path(path, filename)
    if file_path is None:
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    return FileResponse(
        path=str(file_path),
        filename=filename,
        media_type="application/octet-stream",
    )


@router.post("/api/files/upload")
async def upload_to_folder(
    file: UploadFile = File(...),
    folder_path: str = Form(default="/"),
    file_type: str = Form(default="document"),
    category: str = Form(default=""),
    task_id: str = Form(default=""),
    _admin: dict = Depends(verify_admin),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """특정 폴더에 파일을 업로드합니다. (관리자 전용)"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")

    content = await file.read()
    max_size = settings.max_upload_size_mb * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=400,
            detail=f"파일 크기는 {settings.max_upload_size_mb}MB 이하여야 합니다.",
        )

    try:
        result = await asyncio.to_thread(
            fs_service.upload_to_folder,
            file.filename,
            content,
            folder_path,
            file_type,
            category,
            task_id,
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"파일 처리 중 오류 발생: {e}")


@router.post("/api/files/sync")
async def sync_files(
    _admin: dict = Depends(verify_admin),
    fs_service: FileSystemService = Depends(get_filesystem_service),
):
    """data/files/ 디렉토리를 스캔하여 벡터DB와 동기화합니다. (관리자 전용)

    새로 추가된 파일은 자동 인덱싱, 삭제된 파일은 인덱스에서 제거합니다.
    """
    try:
        task_id = f"sync_{__import__('time').time_ns()}"
        result = await asyncio.to_thread(fs_service.sync_files, task_id)
        return {
            "success": True,
            "message": f"동기화 완료: {result['indexed']}개 인덱싱, {result['removed']}개 제거",
            **result,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"동기화 중 오류 발생: {e}")


@router.get("/api/files/progress/{task_id}")
async def get_upload_progress(task_id: str):
    """업로드 진행률을 조회합니다."""
    progress = get_progress(task_id)
    if progress is None:
        return {"step": "unknown", "percent": 0, "detail": ""}
    return progress
