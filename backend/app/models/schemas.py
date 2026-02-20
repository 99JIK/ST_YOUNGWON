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


# === NAS Paths ===


class NASPathEntry(BaseModel):
    id: str = ""
    name: str
    path: str
    category: str = ""
    description: str = ""
    tags: list[str] = []


class NASPathSearchResult(BaseModel):
    entries: list[NASPathEntry]
    total_count: int


class NASFileInfo(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    total_chunks: int
    status: str  # "indexed", "stored", "processing", "error"
    file_size: int = 0
    category: str = ""


class NASFileUploadResponse(BaseModel):
    id: str
    filename: str
    total_chunks: int
    status: str
    message: str


class NASFileListResponse(BaseModel):
    files: list[NASFileInfo]
    total_count: int


# === File Browser ===


class FolderItem(BaseModel):
    """파일 브라우저 항목 (파일 또는 폴더)."""
    id: str
    name: str
    type: str  # "file" | "folder"
    folder_path: str  # 부모 경로, "/" 또는 "/인사팀/규정"
    file_type: str = ""  # "document" | "nas_file" | ""
    file_size: int = 0
    status: str = ""
    uploaded_at: str = ""
    total_chunks: int = 0
    category: str = ""


class FolderListResponse(BaseModel):
    """폴더 내용 조회 응답."""
    current_path: str
    parent_path: Optional[str]
    breadcrumbs: list[dict]
    folders: list[FolderItem]
    files: list[FolderItem]


class CreateFolderRequest(BaseModel):
    name: str
    parent_path: str = "/"


class MoveItemRequest(BaseModel):
    item_id: str
    item_type: str  # "file" | "folder"
    source_type: str = ""  # "document" | "nas_file" | "folder"
    target_path: str


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
