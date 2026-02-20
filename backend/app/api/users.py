"""관리자용 유저 관리 API."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.app.dependencies import get_user_service, verify_admin
from backend.app.services.user_service import UserService

router = APIRouter()


class CreateUserRequest(BaseModel):
    username: str
    display_name: str = ""
    password: str
    role: str = "user"


class ResetPasswordRequest(BaseModel):
    new_password: str


@router.get("/api/admin/users")
async def list_users(
    _admin=Depends(verify_admin),
    user_service: UserService = Depends(get_user_service),
):
    """유저 목록을 조회합니다."""
    users = user_service.list_users()
    return {"users": users}


@router.post("/api/admin/users")
async def create_user(
    request: CreateUserRequest,
    _admin=Depends(verify_admin),
    user_service: UserService = Depends(get_user_service),
):
    """새 유저를 생성합니다."""
    existing = user_service.get_user_by_username(request.username)
    if existing:
        raise HTTPException(status_code=400, detail="이미 존재하는 아이디입니다.")
    user = user_service.create_user(
        request.username, request.display_name, request.password, request.role
    )
    return {
        "success": True,
        "user": {
            "id": user["id"],
            "username": user["username"],
            "display_name": user["display_name"],
            "role": user["role"],
        },
    }


@router.put("/api/admin/users/{user_id}/password")
async def reset_password(
    user_id: int,
    request: ResetPasswordRequest,
    _admin=Depends(verify_admin),
    user_service: UserService = Depends(get_user_service),
):
    """유저 비밀번호를 리셋합니다."""
    ok = user_service.reset_password(user_id, request.new_password)
    if not ok:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    return {"success": True}


@router.delete("/api/admin/users/{user_id}")
async def delete_user(
    user_id: int,
    _admin=Depends(verify_admin),
    user_service: UserService = Depends(get_user_service),
):
    """유저를 삭제합니다."""
    user = user_service.get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=404, detail="유저를 찾을 수 없습니다.")
    if user["username"] == "admin":
        raise HTTPException(status_code=400, detail="기본 관리자 계정은 삭제할 수 없습니다.")
    user_service.delete_user(user_id)
    return {"success": True}
