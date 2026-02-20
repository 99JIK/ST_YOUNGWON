from __future__ import annotations

from fastapi import Cookie, HTTPException, Request
from jose import JWTError, jwt

from backend.app.config import settings
from backend.app.core.vectorstore import VectorStore
from backend.app.services.chat_service import ChatService
from backend.app.services.document_service import DocumentService
from backend.app.services.filesystem_service import FileSystemService
from backend.app.services.nas_path_service import NASPathService
from backend.app.services.user_service import UserService

# 싱글톤 인스턴스
_vectorstore: VectorStore | None = None
_chat_service: ChatService | None = None
_document_service: DocumentService | None = None
_nas_path_service: NASPathService | None = None
_filesystem_service: FileSystemService | None = None
_user_service: UserService | None = None


def get_vectorstore() -> VectorStore:
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = VectorStore()
    return _vectorstore


def get_chat_service() -> ChatService:
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService(vectorstore=get_vectorstore())
    return _chat_service


def get_document_service() -> DocumentService:
    global _document_service
    if _document_service is None:
        _document_service = DocumentService(vectorstore=get_vectorstore())
    return _document_service


def get_nas_path_service() -> NASPathService:
    global _nas_path_service
    if _nas_path_service is None:
        _nas_path_service = NASPathService(vectorstore=get_vectorstore())
    return _nas_path_service


def get_filesystem_service() -> FileSystemService:
    global _filesystem_service
    if _filesystem_service is None:
        _filesystem_service = FileSystemService(
            doc_service=get_document_service(),
            nas_service=get_nas_path_service(),
        )
    return _filesystem_service


def get_user_service() -> UserService:
    global _user_service
    if _user_service is None:
        _user_service = UserService()
    return _user_service


# === 인증 ===


def create_token(user: dict) -> str:
    """유저 JWT 토큰을 생성합니다."""
    return jwt.encode(
        {
            "user_id": user["id"],
            "username": user["username"],
            "role": user["role"],
        },
        settings.secret_key,
        algorithm="HS256",
    )


async def get_current_user(
    request: Request,
    auth_token: str | None = Cookie(default=None),
) -> dict:
    """현재 인증된 유저를 반환합니다."""
    auth_header = request.headers.get("Authorization", "")
    token = None

    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    elif auth_token:
        token = auth_token

    if not token:
        raise HTTPException(status_code=401, detail="인증이 필요합니다.")

    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload  # {user_id, username, role}
    except JWTError:
        raise HTTPException(status_code=401, detail="유효하지 않은 인증 토큰입니다.")


async def verify_admin(
    request: Request,
    auth_token: str | None = Cookie(default=None),
) -> dict:
    """관리자 인증을 확인합니다."""
    user = await get_current_user(request, auth_token)
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 없습니다.")
    return user
