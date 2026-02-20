from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.models.schemas import (
    CreateFolderRequest,
    FolderItem,
    FolderListResponse,
)
from backend.app.services.document_service import DocumentService
from backend.app.services.nas_path_service import NASPathService

logger = logging.getLogger(__name__)


class FileSystemService:
    """실제 파일시스템 기반 파일 브라우저 — data/files/ 루트."""

    def __init__(
        self,
        doc_service: DocumentService,
        nas_service: NASPathService,
    ):
        self._doc_service = doc_service
        self._nas_service = nas_service
        self._root = settings.files_dir
        self._root.mkdir(parents=True, exist_ok=True)

    # === 경로 유틸리티 ===

    def _resolve_safe_path(self, virtual_path: str) -> Path:
        """가상경로 → 실제 경로로 변환합니다. path traversal 방지."""
        virtual_path = virtual_path.replace("\\", "/")
        parts = [p for p in virtual_path.split("/") if p and p != ".." and p != "."]
        real = self._root.joinpath(*parts) if parts else self._root
        # resolve()로 심볼릭 링크 등을 해소하고 루트 밖 접근을 차단
        real = real.resolve()
        root_resolved = self._root.resolve()
        if not str(real).startswith(str(root_resolved)):
            raise ValueError("잘못된 경로입니다.")
        return real

    @staticmethod
    def _normalize_path(path: str) -> str:
        """가상 경로를 정규화합니다."""
        path = path.replace("\\", "/")
        parts = [p for p in path.split("/") if p and p != ".." and p != "."]
        return "/" + "/".join(parts) if parts else "/"

    @staticmethod
    def _build_breadcrumbs(path: str) -> list[dict]:
        breadcrumbs = [{"name": "루트", "path": "/"}]
        if path == "/":
            return breadcrumbs
        parts = [p for p in path.split("/") if p]
        current = ""
        for part in parts:
            current += f"/{part}"
            breadcrumbs.append({"name": part, "path": current})
        return breadcrumbs

    # === 브라우징 ===

    def browse(self, path: str = "/") -> FolderListResponse:
        """실제 디렉토리의 내용을 조회합니다."""
        path = self._normalize_path(path)
        real_path = self._resolve_safe_path(path)

        if not real_path.exists() or not real_path.is_dir():
            path = "/"
            real_path = self._root

        folders: list[FolderItem] = []
        files: list[FolderItem] = []

        try:
            for entry in sorted(real_path.iterdir(), key=lambda e: e.name.lower()):
                if entry.name.startswith("."):
                    continue

                if entry.is_dir():
                    folders.append(
                        FolderItem(
                            id=entry.name,
                            name=entry.name,
                            type="folder",
                            folder_path=path,
                            uploaded_at=datetime.fromtimestamp(
                                entry.stat().st_mtime
                            ).isoformat(),
                        )
                    )
                elif entry.is_file():
                    stat = entry.stat()
                    files.append(
                        FolderItem(
                            id=entry.name,
                            name=entry.name,
                            type="file",
                            folder_path=path,
                            file_type="file",
                            file_size=stat.st_size,
                            uploaded_at=datetime.fromtimestamp(
                                stat.st_mtime
                            ).isoformat(),
                        )
                    )
        except PermissionError:
            logger.warning(f"권한 없음: {real_path}")

        parent_path = None
        if path != "/":
            parts = path.rsplit("/", 1)
            parent_path = parts[0] if parts[0] else "/"

        return FolderListResponse(
            current_path=path,
            parent_path=parent_path,
            breadcrumbs=self._build_breadcrumbs(path),
            folders=folders,
            files=files,
        )

    # === 폴더 CRUD ===

    def create_folder(self, request: CreateFolderRequest) -> FolderItem:
        """실제 디렉토리를 생성합니다."""
        parent = self._normalize_path(request.parent_path)
        parent_real = self._resolve_safe_path(parent)

        folder_real = parent_real / request.name
        if folder_real.exists():
            raise ValueError("이미 같은 이름의 폴더가 존재합니다.")

        folder_real.mkdir(parents=True, exist_ok=True)
        logger.info(f"폴더 생성: {request.name} ({parent})")

        return FolderItem(
            id=request.name,
            name=request.name,
            type="folder",
            folder_path=parent,
            uploaded_at=datetime.now().isoformat(),
        )

    def delete_folder(self, path: str, name: str) -> bool:
        """빈 폴더를 삭제합니다."""
        parent_real = self._resolve_safe_path(path)
        folder_real = parent_real / name

        if not folder_real.exists() or not folder_real.is_dir():
            return False

        if any(folder_real.iterdir()):
            return False

        folder_real.rmdir()
        logger.info(f"폴더 삭제: {name} ({path})")
        return True

    # === 파일 저장/삭제/다운로드 ===

    def save_file(self, path: str, filename: str, content: bytes) -> Path:
        """파일을 실제 경로에 저장합니다."""
        parent_real = self._resolve_safe_path(path)
        parent_real.mkdir(parents=True, exist_ok=True)

        file_path = parent_real / filename
        file_path.write_bytes(content)
        logger.info(f"파일 저장: {filename} ({path})")
        return file_path

    def delete_file(self, path: str, filename: str) -> bool:
        """파일을 삭제하고 벡터DB 인덱스도 정리합니다."""
        parent_real = self._resolve_safe_path(path)
        file_path = parent_real / filename

        if not file_path.exists() or not file_path.is_file():
            return False

        # 벡터DB 인덱스 정리
        norm = self._normalize_path(path)
        relative_path = (norm + "/" + filename).replace("//", "/")
        try:
            self._nas_service.remove_by_relative_path(relative_path)
        except Exception as e:
            logger.warning(f"인덱스 정리 실패: {relative_path} - {e}")

        file_path.unlink()
        logger.info(f"파일 삭제: {filename} ({path})")
        return True

    def get_file_path(self, path: str, filename: str) -> Optional[Path]:
        """다운로드용 실제 파일 경로를 반환합니다."""
        parent_real = self._resolve_safe_path(path)
        file_path = parent_real / filename

        if not file_path.exists() or not file_path.is_file():
            return None
        return file_path

    # === 폴더에 업로드 (인덱싱 포함) ===

    def upload_to_folder(
        self,
        filename: str,
        file_content: bytes,
        folder_path: str = "/",
        file_type: str = "document",
        category: str = "",
        task_id: str = "",
    ):
        """파일을 저장하고, 타입에 따라 벡터DB 인덱싱도 수행합니다."""
        folder_path = self._normalize_path(folder_path)

        # 실제 파일 저장 (data/files/ 에만)
        saved_path = self.save_file(folder_path, filename, file_content)
        relative_path = (folder_path + "/" + filename).replace("//", "/")

        if file_type == "document":
            # 규정 문서 → DocumentService (st_youngwon_regulations 컬렉션)
            result = self._doc_service.upload_and_index(
                filename, file_content, task_id
            )
            return result
        else:
            # 일반 파일 → NASPathService (nas_files 컬렉션, 중복 저장 없음)
            result = self._nas_service.index_file_at_path(
                file_path=saved_path,
                filename=filename,
                file_size=len(file_content),
                relative_path=relative_path,
                category=category,
                task_id=task_id,
            )
            return result

    # === 파일 동기화 ===

    def sync_files(self, task_id: str = "") -> dict:
        """data/files/ 디렉토리를 스캔하여 벡터DB와 동기화합니다.

        - 새 파일 → 자동 인덱싱
        - 삭제된 파일 → 인덱스 제거
        Returns: {indexed: int, removed: int, skipped: int, errors: list}
        """
        from backend.app.core.progress import update_progress

        def _progress(step: str, percent: int, detail: str = "") -> None:
            if task_id:
                update_progress(task_id, step, percent, detail)

        _progress("scanning", 5, "파일 스캔 중...")

        # 1. 실제 파일시스템의 모든 파일 수집
        fs_files: dict[str, Path] = {}  # relative_path → real_path
        root_resolved = self._root.resolve()
        for real_path in self._root.rglob("*"):
            if real_path.is_file() and not real_path.name.startswith("."):
                rel = "/" + str(real_path.resolve().relative_to(root_resolved)).replace("\\", "/")
                fs_files[rel] = real_path

        # 2. 이미 인덱싱된 파일 목록
        indexed_paths = self._nas_service.get_indexed_relative_paths()

        # 3. 새 파일 (파일시스템에 있지만 인덱스에 없음)
        new_files = {k: v for k, v in fs_files.items() if k not in indexed_paths}

        # 4. 삭제된 파일 (인덱스에 있지만 파일시스템에 없음)
        deleted_paths = indexed_paths - set(fs_files.keys())

        total_work = len(new_files) + len(deleted_paths)
        if total_work == 0:
            _progress("done", 100, "변경 사항 없음")
            return {"indexed": 0, "removed": 0, "skipped": 0, "errors": []}

        indexed = 0
        removed = 0
        skipped = 0
        errors = []
        done = 0

        # 5. 새 파일 인덱싱
        for rel_path, real_path in new_files.items():
            done += 1
            pct = 10 + int(80 * done / total_work)
            _progress("indexing", pct, f"인덱싱 중: {real_path.name}")

            try:
                self._nas_service.index_file_at_path(
                    file_path=real_path,
                    filename=real_path.name,
                    relative_path=rel_path,
                )
                indexed += 1
            except Exception as e:
                logger.warning(f"인덱싱 실패: {rel_path} - {e}")
                errors.append(f"{rel_path}: {e}")
                skipped += 1

        # 6. 삭제된 파일 정리
        for rel_path in deleted_paths:
            done += 1
            pct = 10 + int(80 * done / total_work)
            _progress("cleaning", pct, f"정리 중: {rel_path}")

            try:
                self._nas_service.remove_by_relative_path(rel_path)
                removed += 1
            except Exception as e:
                logger.warning(f"인덱스 정리 실패: {rel_path} - {e}")
                errors.append(f"{rel_path}: {e}")

        _progress("done", 100, f"완료 (인덱싱: {indexed}, 제거: {removed})")
        logger.info(f"파일 동기화 완료: 인덱싱={indexed}, 제거={removed}, 스킵={skipped}")

        return {
            "indexed": indexed,
            "removed": removed,
            "skipped": skipped,
            "errors": errors,
        }
