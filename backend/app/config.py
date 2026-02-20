from __future__ import annotations

import os
from pathlib import Path

from pydantic_settings import BaseSettings

# 프로젝트 루트 자동 감지
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def _resolve_data_path(env_var: str, default_subpath: str) -> Path:
    """환경변수가 있으면 사용, 없으면 프로젝트 루트 기준 경로."""
    env_val = os.getenv(env_var)
    if env_val:
        p = Path(env_val)
        return p if p.is_absolute() else _PROJECT_ROOT / p
    return _PROJECT_ROOT / default_subpath


class Settings(BaseSettings):
    # App
    app_name: str = "ST영원 스마트 오피스"
    app_version: str = "1.0.0"
    debug: bool = False

    # Paths (로컬 개발: 프로젝트 루트/data, Docker: /app/data)
    base_dir: Path = _PROJECT_ROOT
    data_dir: Path = _resolve_data_path("DATA_DIR", "data")
    documents_dir: Path = _resolve_data_path("DOCUMENTS_DIR", "data/documents")
    extracted_dir: Path = _resolve_data_path("EXTRACTED_DIR", "data/extracted")
    chromadb_dir: Path = _resolve_data_path("CHROMADB_DIR", "data/chromadb")
    nas_files_dir: Path = _resolve_data_path("NAS_FILES_DIR", "data/nas_files")
    files_dir: Path = _resolve_data_path("FILES_DIR", "data/files")
    nas_paths_file: Path = _resolve_data_path(
        "NAS_PATHS_FILE", "data/nas_paths/path_index.json"
    )

    # LLM
    llm_provider: str = "ollama"  # openai, claude, gemini, ollama
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-3-5-haiku-20241022"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "gemma3:4b"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 1024

    # Embeddings
    embedding_provider: str = "ollama"  # openai, ollama
    embedding_model: str = "text-embedding-3-small"
    ollama_embedding_model: str = "nomic-embed-text"

    # Upload
    max_upload_size_mb: int = 200

    # RAG
    chunk_size: int = 800
    chunk_overlap: int = 100
    retrieval_top_k: int = 5
    similarity_threshold: float = 0.3

    # Admin
    admin_password: str = "admin1234"
    secret_key: str = "change-this-secret-key-in-production"

    # NAS
    nas_server_name: str = "NAS_SERVER"

    # Logging
    log_level: str = "INFO"

    model_config = {
        "env_file": str(_PROJECT_ROOT / ".env"),
        "env_file_encoding": "utf-8",
    }


_env_file = _PROJECT_ROOT / ".env"
settings = Settings(_env_file=str(_env_file) if _env_file.exists() else None)
