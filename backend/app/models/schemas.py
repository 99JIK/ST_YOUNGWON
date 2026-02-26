from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel


# === Chat ===


class ChatMessage(BaseModel):
    role: str  # "user" | "assistant"
    content: str


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    history: list[ChatMessage] = []


class SourceReference(BaseModel):
    document: str
    article: str = ""
    page: int = 0
    relevance_score: float = 0.0


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceReference] = []
    session_id: str = ""


# === Documents ===


class DocumentInfo(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    total_chunks: int
    status: str  # "indexed", "processing", "error"
    file_size: int = 0


class DocumentListResponse(BaseModel):
    documents: list[DocumentInfo]
    total_count: int


class DocumentUploadResponse(BaseModel):
    id: str
    filename: str
    total_chunks: int
    status: str
    message: str


# === Synology NAS ===


class BaseDirectory(BaseModel):
    """관리자가 등록한 NAS 기본 디렉토리."""
    id: str = ""
    path: str  # 예: "/인사팀"
    label: str  # 표시 이름
    description: str = ""
    created_at: str = ""


class BaseDirectoryRequest(BaseModel):
    """기본 디렉토리 추가 요청."""
    path: str
    label: str
    description: str = ""


class NASItem(BaseModel):
    """NAS 파일/폴더 항목."""
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified_time: str = ""
    extension: str = ""


class NASDirectoryListing(BaseModel):
    """디렉토리 내용 조회 응답."""
    current_path: str
    parent_path: Optional[str] = None
    breadcrumbs: list[dict] = []
    items: list[NASItem] = []
    total: int = 0
    offset: int = 0


class NASSearchResponse(BaseModel):
    """NAS 파일 검색 응답."""
    query: str
    results: list[NASItem] = []
    total_count: int = 0


# === Admin ===


class AdminLoginRequest(BaseModel):
    password: str


class AdminLoginResponse(BaseModel):
    success: bool
    token: str = ""
    message: str = ""


# === Health ===


class HealthResponse(BaseModel):
    status: str
    document_count: int = 0
    total_chunks: int = 0
    llm_provider: str = ""
