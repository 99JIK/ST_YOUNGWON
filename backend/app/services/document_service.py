from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.core.progress import clear_progress, update_progress
from backend.app.core.vectorstore import REGULATIONS_COLLECTION, VectorStore
from backend.app.models.schemas import DocumentInfo, DocumentUploadResponse
from backend.app.utils.file_parser import extract_text
from backend.app.utils.text_chunker import (
    ARTICLE_PATTERN,
    chunk_general_text,
    chunk_regulation_text,
)

logger = logging.getLogger(__name__)

# 문서 메타데이터 저장 파일
METADATA_FILE = "documents_metadata.json"


class DocumentService:
    """문서 업로드, 텍스트 추출, 벡터 인덱싱을 관리합니다."""

    def __init__(self, vectorstore: Optional[VectorStore] = None):
        self._vectorstore = vectorstore or VectorStore()
        self._documents_dir = settings.documents_dir
        self._extracted_dir = settings.extracted_dir
        self._documents_dir.mkdir(parents=True, exist_ok=True)
        self._extracted_dir.mkdir(parents=True, exist_ok=True)

    def _metadata_path(self) -> Path:
        return self._documents_dir / METADATA_FILE

    def _load_metadata(self) -> dict:
        path = self._metadata_path()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_metadata(self, metadata: dict) -> None:
        path = self._metadata_path()
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upload_and_index(
        self, filename: str, file_content: bytes, task_id: str = ""
    ) -> DocumentUploadResponse:
        """문서를 업로드하고 텍스트를 추출하여 벡터 저장소에 인덱싱합니다."""
        doc_id = str(uuid.uuid4())[:8]
        progress_key = task_id or doc_id

        def _progress(step: str, percent: int, detail: str = "") -> None:
            update_progress(progress_key, step, percent, detail)

        _progress("saving", 5, "파일 저장 중...")

        # 1. 파일 저장
        file_path = self._documents_dir / filename
        file_path.write_bytes(file_content)

        try:
            # 2. 텍스트 추출
            _progress("extracting", 10, "텍스트 추출 중...")
            full_text = extract_text(file_path, file_content)

            # 3. 추출 텍스트 저장
            txt_path = self._extracted_dir / f"{file_path.stem}.txt"
            txt_path.write_text(full_text, encoding="utf-8")

            # 4. 청킹
            _progress("chunking", 25, "문서 청킹 중...")
            is_regulation = len(ARTICLE_PATTERN.findall(full_text)) >= 3
            chunker = chunk_regulation_text if is_regulation else chunk_general_text
            chunks = chunker(
                full_text,
                source_file=filename,
                max_chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
            )

            # 5. 벡터 저장소에 인덱싱 (임베딩이 가장 오래 걸림)
            documents = [c.content for c in chunks]
            metadatas = [c.metadata for c in chunks]
            ids = [f"{doc_id}_{c.chunk_id}" for c in chunks]

            def _on_embed(current: int, total: int) -> None:
                pct = 30 + int(60 * current / max(total, 1))
                _progress("embedding", pct, f"임베딩 생성 중... ({current}/{total})")

            _progress("embedding", 30, f"임베딩 생성 중... (0/{len(chunks)})")
            self._vectorstore.add_documents(
                collection_name=REGULATIONS_COLLECTION,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                on_embed_progress=_on_embed,
            )

            # 6. 메타데이터 저장
            _progress("finalizing", 95, "메타데이터 저장 중...")
            metadata = self._load_metadata()
            metadata[doc_id] = {
                "id": doc_id,
                "filename": filename,
                "uploaded_at": datetime.now().isoformat(),
                "total_chunks": len(chunks),
                "status": "indexed",
                "file_size": len(file_content),
            }
            self._save_metadata(metadata)

            _progress("done", 100, "완료")
            logger.info(
                f"문서 인덱싱 완료: {filename} ({len(chunks)}개 청크)"
            )

            return DocumentUploadResponse(
                id=doc_id,
                filename=filename,
                total_chunks=len(chunks),
                status="indexed",
                message=f"문서가 성공적으로 업로드되고 인덱싱되었습니다. ({len(chunks)}개 청크)",
            )

        except Exception as e:
            logger.error(f"문서 처리 실패: {filename} - {e}")
            _progress("error", 100, f"오류: {e}")
            metadata = self._load_metadata()
            metadata[doc_id] = {
                "id": doc_id,
                "filename": filename,
                "uploaded_at": datetime.now().isoformat(),
                "total_chunks": 0,
                "status": "error",
                "file_size": len(file_content),
                "error": str(e),
            }
            self._save_metadata(metadata)
            raise
        finally:
            # 프론트엔드가 최종 상태를 읽을 수 있도록 약간 지연 후 삭제
            import threading

            def _delayed_clear() -> None:
                import time
                time.sleep(3)
                clear_progress(progress_key)

            threading.Thread(target=_delayed_clear, daemon=True).start()

    def list_documents(self) -> list[DocumentInfo]:
        """인덱싱된 모든 문서 목록을 반환합니다."""
        metadata = self._load_metadata()
        return [
            DocumentInfo(**doc_data)
            for doc_data in metadata.values()
        ]

    def delete_document(self, doc_id: str) -> bool:
        """문서와 관련 데이터를 삭제합니다."""
        metadata = self._load_metadata()

        if doc_id not in metadata:
            return False

        doc_info = metadata[doc_id]
        filename = doc_info["filename"]

        # 벡터 저장소에서 삭제
        self._vectorstore.delete_by_source(REGULATIONS_COLLECTION, filename)

        # 원본 파일 삭제
        doc_path = self._documents_dir / filename
        if doc_path.exists():
            doc_path.unlink()

        # 텍스트 파일 삭제
        txt_path = self._extracted_dir / f"{Path(filename).stem}.txt"
        if txt_path.exists():
            txt_path.unlink()

        # 메타데이터에서 제거
        del metadata[doc_id]
        self._save_metadata(metadata)

        logger.info(f"문서 삭제 완료: {filename}")
        return True

    def get_document_count(self) -> int:
        """인덱싱된 문서 수를 반환합니다."""
        return len(self._load_metadata())

    def get_total_chunks(self) -> int:
        """전체 청크 수를 반환합니다."""
        return self._vectorstore.get_collection_count(REGULATIONS_COLLECTION)
