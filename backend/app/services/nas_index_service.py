from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from backend.app.services.synology_service import SynologyService

logger = logging.getLogger(__name__)


class NASIndexService:
    """NAS 파일 인덱스 — 주기적 스캔으로 파일 목록을 메모리에 캐시합니다.

    등록된 기본 디렉토리를 재귀 스캔하여 모든 파일/폴더 정보를
    메모리에 보관합니다. 챗봇이 "~~ 파일 어디 있어?" 질문에
    즉시 응답할 수 있도록 키워드 검색을 제공합니다.
    """

    def __init__(self, synology: SynologyService) -> None:
        self._synology = synology
        self._index: list[dict] = []
        self._last_scan: Optional[datetime] = None
        self._scanning: bool = False
        self._task: Optional[asyncio.Task] = None

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

    # ──────────────────────────────────────────
    # 스캔
    # ──────────────────────────────────────────

    async def scan_all(self) -> int:
        """등록된 모든 기본 디렉토리를 재귀 스캔하여 인덱스를 갱신합니다."""
        if self._scanning:
            logger.info("이미 스캔 중입니다.")
            return len(self._index)

        self._scanning = True
        try:
            await self._synology._ensure_session()
            base_dirs = self._synology.list_base_dirs()
            if not base_dirs:
                logger.info("등록된 기본 디렉토리가 없어 스캔 건너뜁니다.")
                self._index = []
                self._last_scan = datetime.now()
                return 0

            new_index: list[dict] = []
            for bd in base_dirs:
                await self._scan_recursive(bd["path"], new_index)

            self._index = new_index
            self._last_scan = datetime.now()
            logger.info(f"NAS 파일 인덱스 완료: {len(self._index)}개 항목")
            return len(self._index)
        except Exception as e:
            logger.error(f"NAS 인덱스 스캔 실패: {e}")
            return len(self._index)
        finally:
            self._scanning = False

    async def _scan_recursive(
        self, folder_path: str, accumulator: list[dict]
    ) -> None:
        """폴더를 재귀적으로 스캔합니다."""
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": folder_path,
            "limit": "2000",
            "additional": '["size","time"]',
            "_sid": self._synology._sid,
        }
        try:
            data = await self._synology._raw_get("/webapi/entry.cgi", params)
            if not data.get("success"):
                return

            for f in data["data"].get("files", []):
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
                    await self._scan_recursive(f["path"], accumulator)
        except Exception as e:
            logger.warning(f"스캔 실패 ({folder_path}): {e}")

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
        }

    # ──────────────────────────────────────────
    # 주기적 스캔
    # ──────────────────────────────────────────

    def start_periodic_scan(self, interval_seconds: int = 3600) -> None:
        """주기적 스캔을 백그라운드 태스크로 시작합니다."""

        async def _periodic() -> None:
            # 시작 직후 첫 스캔
            await self.scan_all()
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
