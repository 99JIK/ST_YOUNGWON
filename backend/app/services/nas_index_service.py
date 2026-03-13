from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.config import settings
from backend.app.services.synology_service import SynologyService

logger = logging.getLogger(__name__)

# 폴더당 최대 파일 수 (페이지네이션으로 전부 가져옴)
_PAGE_SIZE = 2000
# 스캔 시작 실패 시 재시도 횟수
_INITIAL_RETRY = 2
_INITIAL_RETRY_DELAY = 10  # 초
# 병렬 스캔 동시 요청 수 (NAS 부하 제한)
_CONCURRENCY = 5
# 최대 재귀 깊이 (base_dir 기준, 0 = base_dir 자체)
_MAX_DEPTH = 5
# 인덱스 캐시 파일
_CACHE_FILE = settings.data_dir / "nas_index_cache.json"

# 스캔 제외 폴더명 (소문자 비교)
_SKIP_DIRS: set[str] = {
    # 버전 관리
    ".git", ".svn", ".hg",
    # 개발 빌드/의존성
    "node_modules", "__pycache__", ".tox", ".venv", "venv",
    ".gradle", ".maven", "build", "dist", "target", "out",
    ".next", ".nuxt",
    # IDE/에디터
    ".idea", ".vscode", ".vs", ".settings",
    # OS 생성 파일
    ".ds_store", "__macosx", "thumbs.db",
    # 기타 대용량/불필요
    ".cache", ".tmp", "tmp", "temp", ".trash",
    "@eadir",  # Synology 썸네일 폴더
}


class NASIndexService:
    """NAS 파일 인덱스 — 주기적 스캔으로 파일 목록을 메모리에 캐시합니다.

    등록된 기본 디렉토리를 재귀 스캔하여 모든 파일/폴더 정보를
    메모리에 보관합니다. 챗봇이 "~~ 파일 어디 있어?" 질문에
    즉시 응답할 수 있도록 키워드 검색을 제공합니다.

    개선사항:
    - 병렬 스캔: 하위 폴더들을 동시에 스캔 (semaphore로 동시성 제한)
    - JSON 캐시: 스캔 결과를 파일로 저장하여 서버 재시작 시 즉시 로드
    """

    def __init__(self, synology: SynologyService) -> None:
        self._synology = synology
        self._index: list[dict] = []
        self._last_scan: Optional[datetime] = None
        self._scanning: bool = False
        self._task: Optional[asyncio.Task] = None
        self._scan_errors: list[str] = []
        self._semaphore = asyncio.Semaphore(_CONCURRENCY)

        # 서버 시작 시 캐시 파일에서 즉시 로드
        self._load_cache()

    # ──────────────────────────────────────────
    # 캐시 저장/로드
    # ──────────────────────────────────────────

    def _load_cache(self) -> None:
        """캐시 파일에서 인덱스를 로드합니다."""
        try:
            if _CACHE_FILE.exists():
                data = json.loads(_CACHE_FILE.read_text(encoding="utf-8"))
                self._index = data.get("index", [])
                scan_time = data.get("last_scan")
                if scan_time:
                    self._last_scan = datetime.fromisoformat(scan_time)
                logger.info(
                    f"NAS 인덱스 캐시 로드: {len(self._index)}개 항목 "
                    f"(스캔 시각: {self._last_scan})"
                )
        except Exception as e:
            logger.warning(f"NAS 인덱스 캐시 로드 실패 (무시): {e}")

    def _save_cache(self) -> None:
        """인덱스를 캐시 파일에 저장합니다."""
        try:
            _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "last_scan": self._last_scan.isoformat() if self._last_scan else None,
                "total": len(self._index),
                "index": self._index,
            }
            _CACHE_FILE.write_text(
                json.dumps(data, ensure_ascii=False), encoding="utf-8"
            )
            logger.info(f"NAS 인덱스 캐시 저장: {len(self._index)}개 항목")
        except Exception as e:
            logger.warning(f"NAS 인덱스 캐시 저장 실패 (무시): {e}")

    # ──────────────────────────────────────────
    # 속성
    # ──────────────────────────────────────────

    @property
    def last_scan_time(self) -> Optional[datetime]:
        return self._last_scan

    @property
    def total_indexed(self) -> int:
        return len(self._index)

    @property
    def is_scanning(self) -> bool:
        return self._scanning

    @property
    def scan_errors(self) -> list[str]:
        return self._scan_errors

    # ──────────────────────────────────────────
    # 스캔
    # ──────────────────────────────────────────

    async def scan_all(self) -> int:
        """등록된 모든 기본 디렉토리를 재귀 스캔하여 인덱스를 갱신합니다."""
        if self._scanning:
            logger.info("이미 스캔 중입니다.")
            return len(self._index)

        self._scanning = True
        self._scan_errors = []
        scan_start = time.monotonic()
        try:
            await self._synology._ensure_session()
            base_dirs = self._synology.list_base_dirs()
            if not base_dirs:
                logger.info("등록된 기본 디렉토리가 없어 스캔 건너뜁니다.")
                self._last_scan = datetime.now()
                return len(self._index)

            new_index: list[dict] = []
            # 기본 디렉토리들을 병렬 스캔 (depth=0부터 시작)
            tasks = [
                self._scan_recursive(bd["path"], new_index, depth=0)
                for bd in base_dirs
            ]
            await asyncio.gather(*tasks)

            # 새 인덱스가 비어있고 이전 인덱스가 있으면 유지 (스캔 실패 보호)
            if not new_index and self._index and self._scan_errors:
                logger.warning(
                    f"스캔 결과가 비어있고 에러 {len(self._scan_errors)}건 발생 — 이전 인덱스 유지 ({len(self._index)}개)"
                )
            else:
                self._index = new_index
                elapsed = time.monotonic() - scan_start
                logger.info(f"NAS 파일 인덱스 완료: {len(self._index)}개 항목 ({elapsed:.1f}초 소요)")

            if self._scan_errors:
                elapsed = time.monotonic() - scan_start
                logger.warning(f"스캔 중 {len(self._scan_errors)}개 폴더에서 에러 발생 ({elapsed:.1f}초 소요)")
                for err in self._scan_errors[:5]:
                    logger.warning(f"  - {err}")

            self._last_scan = datetime.now()
            self._save_cache()
            return len(self._index)
        except Exception as e:
            logger.error(f"NAS 인덱스 스캔 실패: {e}")
            # 이전 인덱스 유지
            if self._index:
                logger.info(f"이전 인덱스 유지: {len(self._index)}개 항목")
            return len(self._index)
        finally:
            self._scanning = False

    async def _scan_recursive(
        self, folder_path: str, accumulator: list[dict], depth: int = 0
    ) -> None:
        """폴더를 재귀적으로 스캔합니다. semaphore로 동시성을 제한합니다."""
        if depth > _MAX_DEPTH:
            return

        async with self._semaphore:
            offset = 0
            sub_dirs: list[str] = []

            while True:
                params = {
                    "api": "SYNO.FileStation.List",
                    "version": "2",
                    "method": "list",
                    "folder_path": folder_path,
                    "offset": str(offset),
                    "limit": str(_PAGE_SIZE),
                    "additional": '["size","time"]',
                    "_sid": self._synology._sid,
                }
                try:
                    data = await self._synology._raw_get("/webapi/entry.cgi", params)
                    if not data.get("success"):
                        code = data.get("error", {}).get("code", "unknown")
                        self._scan_errors.append(f"{folder_path} (에러 코드: {code})")
                        logger.warning(f"스캔 실패 ({folder_path}): 에러 코드 {code}")
                        return

                    files = data["data"].get("files", [])
                    total = data["data"].get("total", 0)

                    for f in files:
                        # 제외 폴더 스킵
                        if f["isdir"] and f["name"].lower() in _SKIP_DIRS:
                            continue

                        additional = f.get("additional", {})
                        entry = {
                            "name": f["name"],
                            "path": f["path"],
                            "is_dir": f["isdir"],
                            "size": additional.get("size", 0),
                            "mtime": additional.get("time", {}).get("mtime", 0),
                            "extension": (
                                Path(f["name"]).suffix.lstrip(".").lower()
                                if not f["isdir"]
                                else ""
                            ),
                        }
                        accumulator.append(entry)

                        if f["isdir"]:
                            sub_dirs.append(f["path"])

                    # 다음 페이지가 있으면 계속
                    offset += len(files)
                    if offset >= total or not files:
                        break

                except Exception as e:
                    self._scan_errors.append(f"{folder_path}: {e}")
                    logger.warning(f"스캔 실패 ({folder_path}): {e}")
                    return

        # semaphore 밖에서 하위 폴더들을 병렬 스캔
        if sub_dirs:
            tasks = [
                self._scan_recursive(sub_dir, accumulator, depth + 1)
                for sub_dir in sub_dirs
            ]
            await asyncio.gather(*tasks)

    # ──────────────────────────────────────────
    # 검색
    # ──────────────────────────────────────────

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """인덱스에서 키워드로 파일을 검색합니다.

        하나 이상의 키워드가 파일명 또는 경로에 포함된 항목을 반환합니다.
        매칭된 키워드가 많을수록 상위에 노출됩니다.
        """
        if not self._index or not query.strip():
            return []

        query_lower = query.lower()
        keywords = query_lower.split()

        scored: list[tuple[int, dict]] = []
        for item in self._index:
            name_lower = item["name"].lower()
            path_lower = item["path"].lower()
            # 각 키워드별 매칭 점수 (이름 매칭 2점, 경로 매칭 1점)
            score = 0
            for kw in keywords:
                if kw in name_lower:
                    score += 2
                elif kw in path_lower:
                    score += 1
            if score > 0:
                scored.append((score, item))

        # 점수 높은 순 정렬
        scored.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in scored[:limit]]

    # ──────────────────────────────────────────
    # 상태 정보
    # ──────────────────────────────────────────

    def get_index_info(self) -> dict:
        """인덱스 상태 정보를 반환합니다."""
        return {
            "total_indexed": self.total_indexed,
            "last_scan": self._last_scan.isoformat() if self._last_scan else None,
            "is_scanning": self._scanning,
            "scan_errors": len(self._scan_errors),
        }

    # ──────────────────────────────────────────
    # 주기적 스캔
    # ──────────────────────────────────────────

    def start_periodic_scan(self, interval_seconds: int = 3600) -> None:
        """주기적 스캔을 백그라운드 태스크로 시작합니다."""

        async def _periodic() -> None:
            # 시작 직후 첫 스캔 (실패 시 재시도)
            for attempt in range(_INITIAL_RETRY + 1):
                count = await self.scan_all()
                if count > 0 or not self._scan_errors:
                    break
                if attempt < _INITIAL_RETRY:
                    logger.info(
                        f"첫 스캔 실패 — {_INITIAL_RETRY_DELAY}초 후 재시도 ({attempt + 1}/{_INITIAL_RETRY})"
                    )
                    await asyncio.sleep(_INITIAL_RETRY_DELAY)

            while True:
                await asyncio.sleep(interval_seconds)
                await self.scan_all()

        self._task = asyncio.create_task(_periodic())
        logger.info(
            f"NAS 파일 인덱스 주기적 스캔 시작 (간격: {interval_seconds}초)"
        )

    def stop_periodic_scan(self) -> None:
        """주기적 스캔을 중지합니다."""
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("NAS 파일 인덱스 주기적 스캔 중지")
