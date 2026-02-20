from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.core.progress import clear_progress, update_progress
from backend.app.core.vectorstore import NAS_FILES_COLLECTION, NAS_PATHS_COLLECTION, VectorStore
from backend.app.models.schemas import NASFileInfo, NASFileUploadResponse, NASPathEntry
from backend.app.utils.file_parser import extract_text, is_extractable
from backend.app.utils.text_chunker import chunk_general_text, chunk_regulation_text

logger = logging.getLogger(__name__)

# NAS 파일 메타데이터 저장 파일
NAS_FILES_METADATA = "nas_files_metadata.json"


class NASPathService:
    """NAS 파일 경로 인덱스 및 파일 관리를 담당합니다."""

    def __init__(self, vectorstore: Optional[VectorStore] = None):
        self._vectorstore = vectorstore or VectorStore()
        self._index_path = settings.nas_paths_file
        self._files_dir = settings.nas_files_dir
        self._files_dir.mkdir(parents=True, exist_ok=True)

    # === NAS 경로 관리 ===

    def _load_index(self) -> dict:
        if self._index_path.exists():
            return json.loads(self._index_path.read_text(encoding="utf-8"))
        return {"paths": []}

    def _save_index(self, data: dict) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def add_path(self, entry: NASPathEntry) -> NASPathEntry:
        """NAS 경로를 추가합니다."""
        if not entry.id:
            entry.id = str(uuid.uuid4())[:8]

        # JSON 인덱스에 추가
        index = self._load_index()
        index["paths"].append(entry.model_dump())
        self._save_index(index)

        # 벡터 저장소에도 인덱싱 (의미 검색용)
        search_text = f"{entry.name} {entry.description} {' '.join(entry.tags)}"
        self._vectorstore.add_documents(
            collection_name=NAS_PATHS_COLLECTION,
            documents=[search_text],
            metadatas=[entry.model_dump()],
            ids=[f"nas_{entry.id}"],
        )

        logger.info(f"NAS 경로 추가: {entry.name} -> {entry.path}")
        return entry

    def list_paths(self) -> list[NASPathEntry]:
        """모든 NAS 경로를 반환합니다."""
        index = self._load_index()
        return [NASPathEntry(**p) for p in index.get("paths", [])]

    def search_paths(self, query: str) -> list[NASPathEntry]:
        """NAS 경로를 검색합니다 (벡터 검색 + 키워드 매칭)."""
        results = []

        # 벡터 검색
        vector_results = self._vectorstore.search(
            NAS_PATHS_COLLECTION, query, top_k=5
        )
        for r in vector_results:
            metadata = r.get("metadata", {})
            if metadata.get("path"):
                results.append(NASPathEntry(**metadata))

        # 키워드 매칭 (벡터 검색 보완)
        index = self._load_index()
        query_lower = query.lower()
        for path_data in index.get("paths", []):
            searchable = (
                f"{path_data.get('name', '')} "
                f"{path_data.get('description', '')} "
                f"{' '.join(path_data.get('tags', []))}"
            ).lower()

            if query_lower in searchable:
                entry = NASPathEntry(**path_data)
                if not any(r.id == entry.id for r in results):
                    results.append(entry)

        return results

    def update_path(self, path_id: str, entry: NASPathEntry) -> Optional[NASPathEntry]:
        """NAS 경로를 수정합니다."""
        index = self._load_index()
        for i, p in enumerate(index["paths"]):
            if p.get("id") == path_id:
                entry.id = path_id
                index["paths"][i] = entry.model_dump()
                self._save_index(index)

                search_text = f"{entry.name} {entry.description} {' '.join(entry.tags)}"
                try:
                    collection = self._vectorstore.get_or_create_collection(
                        NAS_PATHS_COLLECTION
                    )
                    collection.delete(ids=[f"nas_{path_id}"])
                except Exception:
                    pass

                self._vectorstore.add_documents(
                    collection_name=NAS_PATHS_COLLECTION,
                    documents=[search_text],
                    metadatas=[entry.model_dump()],
                    ids=[f"nas_{path_id}"],
                )
                return entry
        return None

    def delete_path(self, path_id: str) -> bool:
        """NAS 경로를 삭제합니다."""
        index = self._load_index()
        original_len = len(index["paths"])
        index["paths"] = [p for p in index["paths"] if p.get("id") != path_id]

        if len(index["paths"]) == original_len:
            return False

        self._save_index(index)

        try:
            collection = self._vectorstore.get_or_create_collection(
                NAS_PATHS_COLLECTION
            )
            collection.delete(ids=[f"nas_{path_id}"])
        except Exception:
            pass

        return True

    # === NAS 파일 관리 ===

    def _files_metadata_path(self) -> Path:
        return self._files_dir / NAS_FILES_METADATA

    def _load_files_metadata(self) -> dict:
        path = self._files_metadata_path()
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        return {}

    def _save_files_metadata(self, metadata: dict) -> None:
        path = self._files_metadata_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def upload_file(
        self, filename: str, file_content: bytes, category: str = "",
        task_id: str = "",
    ) -> NASFileUploadResponse:
        """NAS 파일을 업로드합니다. 읽기 가능한 파일은 벡터 저장소에 인덱싱합니다."""
        # 파일을 nas_files 디렉토리에 저장
        file_path = self._files_dir / filename
        file_path.write_bytes(file_content)

        return self.index_file_at_path(
            file_path=file_path,
            filename=filename,
            file_size=len(file_content),
            category=category,
            task_id=task_id,
        )

    def index_file_at_path(
        self,
        file_path: Path,
        filename: str,
        file_size: int = 0,
        relative_path: str = "",
        category: str = "",
        task_id: str = "",
    ) -> NASFileUploadResponse:
        """이미 디스크에 있는 파일을 벡터DB에 인덱싱합니다. 파일을 복사하지 않습니다."""
        file_id = str(uuid.uuid4())[:8]
        progress_key = task_id or file_id
        if not file_size:
            file_size = file_path.stat().st_size

        def _progress(step: str, percent: int, detail: str = "") -> None:
            update_progress(progress_key, step, percent, detail)

        _progress("saving", 5, "파일 확인 중...")

        try:
            file_content = file_path.read_bytes()

            # 2. 텍스트 추출 가능 여부 확인
            if not is_extractable(filename):
                _progress("finalizing", 95, "메타데이터 저장 중...")
                metadata = self._load_files_metadata()
                metadata[file_id] = {
                    "id": file_id,
                    "filename": filename,
                    "relative_path": relative_path,
                    "uploaded_at": datetime.now().isoformat(),
                    "total_chunks": 0,
                    "status": "stored",
                    "file_size": file_size,
                    "category": category,
                }
                self._save_files_metadata(metadata)

                _progress("done", 100, "완료 (저장만)")
                logger.info(f"파일 저장 완료 (인덱싱 불가): {filename}")

                return NASFileUploadResponse(
                    id=file_id,
                    filename=filename,
                    total_chunks=0,
                    status="stored",
                    message="파일이 저장되었습니다. (텍스트 추출 불가 형식)",
                )

            # 3. 텍스트 추출
            _progress("extracting", 10, "텍스트 추출 중...")
            full_text = extract_text(file_path, file_content)

            if not full_text.strip():
                _progress("finalizing", 95, "메타데이터 저장 중...")
                metadata = self._load_files_metadata()
                metadata[file_id] = {
                    "id": file_id,
                    "filename": filename,
                    "relative_path": relative_path,
                    "uploaded_at": datetime.now().isoformat(),
                    "total_chunks": 0,
                    "status": "stored",
                    "file_size": file_size,
                    "category": category,
                }
                self._save_files_metadata(metadata)

                _progress("done", 100, "완료 (텍스트 없음)")
                logger.info(f"파일 저장 완료 (텍스트 없음): {filename}")

                return NASFileUploadResponse(
                    id=file_id,
                    filename=filename,
                    total_chunks=0,
                    status="stored",
                    message="파일이 저장되었습니다. (추출된 텍스트 없음)",
                )

            # 4. 청킹
            _progress("chunking", 25, "문서 청킹 중...")
            if self._looks_like_regulation(full_text):
                chunks = chunk_regulation_text(
                    full_text,
                    source_file=filename,
                    max_chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                )
            else:
                chunks = chunk_general_text(
                    full_text,
                    source_file=filename,
                    max_chunk_size=settings.chunk_size,
                    chunk_overlap=settings.chunk_overlap,
                )

            # 5. 벡터 저장소에 인덱싱
            documents = [c.content for c in chunks]
            metadatas = [c.metadata for c in chunks]
            ids = [f"nasfile_{file_id}_{c.chunk_id}" for c in chunks]

            def _on_embed(current: int, total: int) -> None:
                pct = 30 + int(60 * current / max(total, 1))
                _progress("embedding", pct, f"임베딩 생성 중... ({current}/{total})")

            _progress("embedding", 30, f"임베딩 생성 중... (0/{len(chunks)})")
            self._vectorstore.add_documents(
                collection_name=NAS_FILES_COLLECTION,
                documents=documents,
                metadatas=metadatas,
                ids=ids,
                on_embed_progress=_on_embed,
            )

            # 6. 메타데이터 저장
            _progress("finalizing", 95, "메타데이터 저장 중...")
            metadata = self._load_files_metadata()
            metadata[file_id] = {
                "id": file_id,
                "filename": filename,
                "relative_path": relative_path,
                "uploaded_at": datetime.now().isoformat(),
                "total_chunks": len(chunks),
                "status": "indexed",
                "file_size": file_size,
                "category": category,
            }
            self._save_files_metadata(metadata)

            _progress("done", 100, "완료")
            logger.info(f"NAS 파일 인덱싱 완료: {filename} ({len(chunks)}개 청크)")

            return NASFileUploadResponse(
                id=file_id,
                filename=filename,
                total_chunks=len(chunks),
                status="indexed",
                message=f"파일이 성공적으로 업로드되고 인덱싱되었습니다. ({len(chunks)}개 청크)",
            )

        except Exception as e:
            logger.error(f"NAS 파일 처리 실패: {filename} - {e}")
            _progress("error", 100, f"오류: {e}")
            metadata = self._load_files_metadata()
            metadata[file_id] = {
                "id": file_id,
                "filename": filename,
                "relative_path": relative_path,
                "uploaded_at": datetime.now().isoformat(),
                "total_chunks": 0,
                "status": "error",
                "file_size": file_size,
                "category": category,
                "error": str(e),
            }
            self._save_files_metadata(metadata)
            raise
        finally:
            import threading

            def _delayed_clear() -> None:
                import time
                time.sleep(3)
                clear_progress(progress_key)

            threading.Thread(target=_delayed_clear, daemon=True).start()

    def list_files(self) -> list[NASFileInfo]:
        """업로드된 NAS 파일 목록을 반환합니다."""
        metadata = self._load_files_metadata()
        return [NASFileInfo(**data) for data in metadata.values()]

    def get_indexed_relative_paths(self) -> set[str]:
        """인덱싱된 파일의 relative_path 집합을 반환합니다."""
        metadata = self._load_files_metadata()
        return {
            v.get("relative_path", "")
            for v in metadata.values()
            if v.get("relative_path")
        }

    def remove_by_relative_path(self, relative_path: str) -> bool:
        """relative_path로 인덱스와 벡터DB 항목을 제거합니다."""
        metadata = self._load_files_metadata()
        to_remove = [
            fid for fid, v in metadata.items()
            if v.get("relative_path") == relative_path
        ]
        if not to_remove:
            return False

        for fid in to_remove:
            filename = metadata[fid]["filename"]
            self._vectorstore.delete_by_source(NAS_FILES_COLLECTION, filename)
            del metadata[fid]

        self._save_files_metadata(metadata)
        logger.info(f"인덱스 제거 완료: {relative_path}")
        return True

    def delete_file(self, file_id: str) -> bool:
        """NAS 파일과 벡터 인덱스를 삭제합니다."""
        metadata = self._load_files_metadata()

        if file_id not in metadata:
            return False

        file_info = metadata[file_id]
        filename = file_info["filename"]

        # 벡터 저장소에서 삭제
        self._vectorstore.delete_by_source(NAS_FILES_COLLECTION, filename)

        # nas_files 디렉토리의 파일 삭제 (기존 호환)
        file_path = self._files_dir / filename
        if file_path.exists():
            file_path.unlink()

        # 메타데이터에서 제거
        del metadata[file_id]
        self._save_files_metadata(metadata)

        logger.info(f"NAS 파일 삭제 완료: {filename}")
        return True

    def get_file_count(self) -> int:
        """NAS 파일 수를 반환합니다."""
        return len(self._load_files_metadata())

    def get_total_file_chunks(self) -> int:
        """NAS 파일 전체 청크 수를 반환합니다."""
        return self._vectorstore.get_collection_count(NAS_FILES_COLLECTION)

    @staticmethod
    def _looks_like_regulation(text: str) -> bool:
        """텍스트가 규정 문서 형식인지 간단히 판별합니다."""
        import re
        article_matches = re.findall(r"제\s*\d+\s*조", text)
        return len(article_matches) >= 3
