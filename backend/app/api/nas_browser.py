from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
from fastapi.responses import Response

from backend.app.dependencies import get_synology_service, verify_admin
from backend.app.models.schemas import (
    BaseDirectory,
    BaseDirectoryRequest,
    NASDirectoryListing,
    NASItem,
    NASSearchResponse,
)
from backend.app.services.synology_service import (
    SynologyAPIError,
    SynologyAuthError,
    SynologyService,
)

router = APIRouter()


# === 기본 디렉토리 관리 (관리자) ===


@router.get("/api/nas/base-dirs", response_model=list[BaseDirectory])
async def list_base_dirs(
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """등록된 기본 디렉토리 목록을 반환합니다."""
    dirs = svc.list_base_dirs()
    return [BaseDirectory(**d) for d in dirs]


@router.post("/api/nas/base-dirs", response_model=BaseDirectory)
async def add_base_dir(
    req: BaseDirectoryRequest,
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """기본 디렉토리를 추가합니다. NAS에 실제 존재하는지 검증합니다."""
    try:
        entry = await svc.add_base_dir(req.path, req.label, req.description)
        return BaseDirectory(**entry)
    except SynologyAuthError as e:
        raise HTTPException(status_code=502, detail=f"NAS 인증 실패: {e}")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/nas/base-dirs/{dir_id}")
async def remove_base_dir(
    dir_id: str,
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """기본 디렉토리를 제거합니다."""
    success = svc.remove_base_dir(dir_id)
    if not success:
        raise HTTPException(status_code=404, detail="디렉토리를 찾을 수 없습니다.")
    return {"message": "디렉토리가 제거되었습니다.", "id": dir_id}


@router.post("/api/nas/base-dirs/validate")
async def validate_path(
    req: BaseDirectoryRequest,
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 경로 존재 여부를 확인합니다."""
    try:
        exists = await svc.validate_path(req.path)
        return {"path": req.path, "exists": exists}
    except SynologyAuthError as e:
        raise HTTPException(status_code=502, detail=f"NAS 인증 실패: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# === NAS 탐색 (관리자 전용) ===


@router.get("/api/nas/browse", response_model=NASDirectoryListing)
async def browse_directory(
    path: str = Query(..., description="디렉토리 경로"),
    offset: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    sort_by: str = Query("name", description="정렬 기준 (name, size, mtime)"),
    sort_direction: str = Query("asc", description="정렬 방향 (asc, desc)"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 디렉토리 내용을 조회합니다. (관리자 전용)"""
    try:
        result = await svc.list_directory(path, offset, limit, sort_by, sort_direction)
        breadcrumbs = _build_breadcrumbs(result["current_path"])

        return NASDirectoryListing(
            current_path=result["current_path"],
            parent_path=result["parent_path"],
            breadcrumbs=breadcrumbs,
            items=[NASItem(**item) for item in result["items"]],
            total=result["total"],
            offset=result["offset"],
        )
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/nas/search", response_model=NASSearchResponse)
async def search_files(
    q: str = Query(..., min_length=1, description="검색어"),
    path: str = Query("", description="검색 시작 경로 (비어있으면 전체)"),
    extension: str = Query("", description="확장자 필터"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 파일을 검색합니다. (관리자 전용)"""
    try:
        results = await svc.search_files(q, path, extension)
        return NASSearchResponse(
            query=q,
            results=[NASItem(**r) for r in results],
            total_count=len(results),
        )
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/nas/download")
async def download_file(
    path: str = Query(..., description="파일 경로"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 파일을 다운로드합니다. (관리자 전용)"""
    try:
        content, filename = await svc.download_file(path)
        return Response(
            content=content,
            media_type="application/octet-stream",
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/api/nas/status")
async def nas_status(
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 연결 상태를 확인합니다. (관리자 전용)"""
    result = await svc.check_connection()
    base_dirs = svc.list_base_dirs()
    return {
        **result,
        "base_dir_count": len(base_dirs),
    }


# === 파일 관리 (관리자 전용) ===


@router.post("/api/nas/folder")
async def create_folder(
    folder_path: str = Form(..., description="부모 디렉토리 경로"),
    name: str = Form(..., description="새 폴더 이름"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS에 새 폴더를 생성합니다."""
    try:
        result = await svc.create_folder(folder_path, name)
        return {"success": True, **result}
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/nas/upload")
async def upload_file(
    path: str = Form(..., description="업로드할 디렉토리 경로"),
    overwrite: bool = Form(False, description="덮어쓰기 여부"),
    file: UploadFile = File(...),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS에 파일을 업로드합니다."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="파일명이 없습니다.")

    content = await file.read()
    if len(content) > 500 * 1024 * 1024:  # 500MB 제한
        raise HTTPException(status_code=400, detail="파일 크기는 500MB 이하여야 합니다.")

    try:
        result = await svc.upload_file(path, file.filename, content, overwrite)
        return {"success": True, **result}
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/api/nas/rename")
async def rename_item(
    path: str = Form(..., description="대상 경로"),
    new_name: str = Form(..., description="새 이름"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 파일/폴더 이름을 변경합니다."""
    try:
        result = await svc.rename_item(path, new_name)
        return {"success": True, **result}
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/api/nas/delete")
async def delete_item(
    path: str = Query(..., description="삭제할 경로"),
    _admin: dict = Depends(verify_admin),
    svc: SynologyService = Depends(get_synology_service),
):
    """NAS 파일/폴더를 삭제합니다."""
    try:
        await svc.delete_item(path)
        return {"success": True, "message": "삭제되었습니다."}
    except SynologyAuthError:
        raise HTTPException(status_code=502, detail="NAS 인증이 만료되었습니다.")
    except SynologyAPIError as e:
        raise HTTPException(status_code=400, detail=str(e))


# === 헬퍼 ===


def _build_breadcrumbs(path: str) -> list[dict]:
    """경로에서 breadcrumbs를 생성합니다."""
    parts = path.strip("/").split("/")
    breadcrumbs = []
    current = ""
    for part in parts:
        current += f"/{part}"
        breadcrumbs.append({"name": part, "path": current})
    return breadcrumbs
