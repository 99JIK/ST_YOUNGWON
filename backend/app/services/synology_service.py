from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


class SynologyAuthError(Exception):
    """시놀로지 인증 실패."""


class SynologyAPIError(Exception):
    """시놀로지 API 호출 실패."""


class SynologyService:
    """Synology FileStation API 클라이언트.

    - 세션 기반 인증 (SYNO.API.Auth)
    - 디렉토리 목록 조회 (SYNO.FileStation.List)
    - 파일 검색 (SYNO.FileStation.Search)
    - 파일 다운로드 (SYNO.FileStation.Download)
    - 기본 디렉토리(base_dirs) 관리 (로컬 JSON)
    """

    def __init__(self) -> None:
        self._base_url = settings.synology_url.rstrip("/")
        self._username = settings.synology_username
        self._password = settings.synology_password
        self._verify_ssl = settings.synology_verify_ssl
        self._session_name = settings.synology_session_name
        self._sid: str = ""
        self._synotoken: str = ""
        self._base_dirs_path = settings.base_dirs_file

    # ──────────────────────────────────────────
    # 인증
    # ──────────────────────────────────────────

    async def login(self) -> str:
        """시놀로지 NAS에 로그인하고 세션 ID를 반환합니다."""
        # DSM 7: version 6 + enable_syno_token + POST (비밀번호 특수문자 안전)
        form_data = {
            "api": "SYNO.API.Auth",
            "version": "6",
            "method": "login",
            "account": self._username,
            "passwd": self._password,
            "session": self._session_name,
            "format": "sid",
            "enable_syno_token": "yes",
        }
        data = await self._raw_post("/webapi/entry.cgi", form_data)
        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            raise SynologyAuthError(f"로그인 실패 (에러 코드: {code})")
        self._sid = data["data"]["sid"]
        self._synotoken = data["data"].get("synotoken", "")
        logger.info("시놀로지 NAS 로그인 성공")
        return self._sid

    async def logout(self) -> None:
        """현재 세션을 로그아웃합니다."""
        if not self._sid:
            return
        params = {
            "api": "SYNO.API.Auth",
            "version": "6",
            "method": "logout",
            "session": self._session_name,
            "_sid": self._sid,
        }
        try:
            await self._raw_get("/webapi/entry.cgi", params)
        except Exception:
            pass
        self._sid = ""
        self._synotoken = ""
        logger.info("시놀로지 NAS 로그아웃")

    async def _ensure_session(self) -> None:
        """세션이 없으면 로그인합니다."""
        if not self._sid:
            await self.login()

    # ──────────────────────────────────────────
    # 기본 디렉토리 관리 (로컬 JSON)
    # ──────────────────────────────────────────

    def _load_base_dirs(self) -> list[dict]:
        if self._base_dirs_path.exists():
            data = json.loads(self._base_dirs_path.read_text(encoding="utf-8"))
            return data.get("base_dirs", [])
        return []

    def _save_base_dirs(self, dirs: list[dict]) -> None:
        self._base_dirs_path.parent.mkdir(parents=True, exist_ok=True)
        self._base_dirs_path.write_text(
            json.dumps({"base_dirs": dirs}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def list_base_dirs(self) -> list[dict]:
        """등록된 기본 디렉토리 목록을 반환합니다."""
        return self._load_base_dirs()

    async def add_base_dir(
        self, path: str, label: str, description: str = ""
    ) -> dict:
        """기본 디렉토리를 추가합니다. NAS에 실제 존재하는지 검증합니다."""
        # NAS에서 경로 존재 여부 확인
        await self._ensure_session()
        exists = await self._validate_path(path)
        if not exists:
            raise SynologyAPIError(f"NAS에 경로가 존재하지 않습니다: {path}")

        dirs = self._load_base_dirs()

        # 중복 체크
        if any(d["path"] == path for d in dirs):
            raise SynologyAPIError(f"이미 등록된 경로입니다: {path}")

        entry = {
            "id": str(uuid.uuid4())[:8],
            "path": path,
            "label": label,
            "description": description,
            "created_at": datetime.now().isoformat(),
        }
        dirs.append(entry)
        self._save_base_dirs(dirs)
        logger.info(f"기본 디렉토리 추가: {label} -> {path}")
        return entry

    def remove_base_dir(self, dir_id: str) -> bool:
        """기본 디렉토리를 제거합니다."""
        dirs = self._load_base_dirs()
        original_len = len(dirs)
        dirs = [d for d in dirs if d.get("id") != dir_id]
        if len(dirs) == original_len:
            return False
        self._save_base_dirs(dirs)
        logger.info(f"기본 디렉토리 제거: {dir_id}")
        return True

    def _is_within_base_dirs(self, path: str) -> bool:
        """주어진 경로가 등록된 기본 디렉토리 하위인지 확인합니다."""
        dirs = self._load_base_dirs()
        normalized = path.rstrip("/")
        for d in dirs:
            base = d["path"].rstrip("/")
            if normalized == base or normalized.startswith(base + "/"):
                return True
        return False

    # ──────────────────────────────────────────
    # 디렉토리 탐색
    # ──────────────────────────────────────────

    async def list_directory(
        self,
        folder_path: str,
        offset: int = 0,
        limit: int = 100,
        sort_by: str = "name",
        sort_direction: str = "asc",
    ) -> dict:
        """디렉토리 내용을 조회합니다.

        Returns:
            {
                "current_path": str,
                "parent_path": str | None,
                "items": list[dict],
                "total": int,
                "offset": int,
            }
        """
        if not self._is_within_base_dirs(folder_path):
            raise SynologyAPIError(
                "접근 권한이 없는 경로입니다. 등록된 기본 디렉토리 하위만 탐색 가능합니다."
            )

        await self._ensure_session()
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "list",
            "folder_path": folder_path,
            "offset": str(offset),
            "limit": str(limit),
            "sort_by": sort_by,
            "sort_direction": sort_direction,
            "additional": '["size","time","type"]',
            "_sid": self._sid,
        }
        data = await self._raw_get("/webapi/entry.cgi", params)
        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            if code == 408:
                raise SynologyAuthError("세션 만료")
            raise SynologyAPIError(f"디렉토리 조회 실패 (에러 코드: {code})")

        files_data = data["data"]
        items = []
        for f in files_data.get("files", []):
            additional = f.get("additional", {})
            items.append({
                "name": f["name"],
                "path": f["path"],
                "is_dir": f["isdir"],
                "size": additional.get("size", 0),
                "modified_time": self._format_timestamp(
                    additional.get("time", {}).get("mtime", 0)
                ),
                "extension": Path(f["name"]).suffix.lstrip(".").lower()
                if not f["isdir"]
                else "",
            })

        # 부모 경로 계산
        parent_path = None
        parts = folder_path.rstrip("/").rsplit("/", 1)
        if len(parts) == 2 and parts[0]:
            candidate = parts[0]
            if self._is_within_base_dirs(candidate):
                parent_path = candidate

        return {
            "current_path": folder_path,
            "parent_path": parent_path,
            "items": items,
            "total": files_data.get("total", len(items)),
            "offset": offset,
        }

    # ──────────────────────────────────────────
    # 파일 검색
    # ──────────────────────────────────────────

    async def search_files(
        self,
        query: str,
        folder_path: str = "",
        extension: str = "",
    ) -> list[dict]:
        """파일을 검색합니다. folder_path가 비어있으면 모든 기본 디렉토리에서 검색합니다."""
        await self._ensure_session()

        search_paths: list[str] = []
        if folder_path:
            if not self._is_within_base_dirs(folder_path):
                raise SynologyAPIError("접근 권한이 없는 경로입니다.")
            search_paths = [folder_path]
        else:
            search_paths = [d["path"] for d in self._load_base_dirs()]

        if not search_paths:
            return []

        all_results: list[dict] = []
        for sp in search_paths:
            results = await self._search_in_folder(query, sp, extension)
            all_results.extend(results)

        return all_results

    async def _search_in_folder(
        self, query: str, folder_path: str, extension: str = ""
    ) -> list[dict]:
        """특정 폴더에서 파일을 검색합니다."""
        # 검색 시작
        start_params: dict[str, str] = {
            "api": "SYNO.FileStation.Search",
            "version": "2",
            "method": "start",
            "folder_path": folder_path,
            "pattern": f"*{query}*",
            "_sid": self._sid,
        }
        if extension:
            start_params["extension"] = extension

        start_data = await self._raw_get("/webapi/entry.cgi", start_params)
        if not start_data.get("success"):
            logger.warning(f"검색 시작 실패: {folder_path}")
            return []

        task_id = start_data["data"]["taskid"]

        # 검색 결과 조회 (폴링)
        import asyncio

        results: list[dict] = []
        for _ in range(30):  # 최대 30초 대기
            await asyncio.sleep(1)
            list_params = {
                "api": "SYNO.FileStation.Search",
                "version": "2",
                "method": "list",
                "taskid": task_id,
                "offset": "0",
                "limit": "100",
                "additional": '["size","time","type"]',
                "_sid": self._sid,
            }
            list_data = await self._raw_get("/webapi/entry.cgi", list_params)
            if not list_data.get("success"):
                break

            search_data = list_data["data"]
            finished = search_data.get("finished", False)

            for f in search_data.get("files", []):
                additional = f.get("additional", {})
                results.append({
                    "name": f["name"],
                    "path": f["path"],
                    "is_dir": f["isdir"],
                    "size": additional.get("size", 0),
                    "modified_time": self._format_timestamp(
                        additional.get("time", {}).get("mtime", 0)
                    ),
                    "extension": Path(f["name"]).suffix.lstrip(".").lower()
                    if not f["isdir"]
                    else "",
                })

            if finished:
                break

        # 검색 태스크 정리
        try:
            stop_params = {
                "api": "SYNO.FileStation.Search",
                "version": "2",
                "method": "stop",
                "taskid": task_id,
                "_sid": self._sid,
            }
            await self._raw_get("/webapi/entry.cgi", stop_params)
        except Exception:
            pass

        return results

    # ──────────────────────────────────────────
    # 파일 다운로드
    # ──────────────────────────────────────────

    async def download_file(self, file_path: str) -> tuple[bytes, str]:
        """파일을 다운로드하여 (바이트, 파일명) 튜플을 반환합니다."""
        if not self._is_within_base_dirs(file_path):
            raise SynologyAPIError("접근 권한이 없는 경로입니다.")

        await self._ensure_session()
        params = {
            "api": "SYNO.FileStation.Download",
            "version": "2",
            "method": "download",
            "path": file_path,
            "mode": "download",
            "_sid": self._sid,
        }

        headers = {}
        if self._synotoken:
            headers["X-SYNO-TOKEN"] = self._synotoken
        async with httpx.AsyncClient(verify=self._verify_ssl) as client:
            resp = await client.get(
                f"{self._base_url}/webapi/entry.cgi",
                params=params,
                headers=headers,
                timeout=120.0,
            )
            resp.raise_for_status()

            filename = Path(file_path).name
            # Content-Disposition 헤더에서 파일명 추출 시도
            cd = resp.headers.get("content-disposition", "")
            if "filename=" in cd:
                filename = cd.split("filename=")[-1].strip('"')

            return resp.content, filename

    # ──────────────────────────────────────────
    # 파일 관리 (관리자용)
    # ──────────────────────────────────────────

    async def create_folder(self, folder_path: str, name: str) -> dict:
        """새 폴더를 생성합니다."""
        if not self._is_within_base_dirs(folder_path):
            raise SynologyAPIError("접근 권한이 없는 경로입니다.")

        await self._ensure_session()
        params = {
            "api": "SYNO.FileStation.CreateFolder",
            "version": "2",
            "method": "create",
            "folder_path": json.dumps([folder_path]),
            "name": json.dumps([name]),
            "_sid": self._sid,
        }
        data = await self._raw_get("/webapi/entry.cgi", params)
        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            raise SynologyAPIError(f"폴더 생성 실패 (에러 코드: {code})")

        folders = data["data"].get("folders", [])
        if folders:
            return {"name": folders[0]["name"], "path": folders[0]["path"]}
        return {"name": name, "path": f"{folder_path}/{name}"}

    async def rename_item(self, path: str, new_name: str) -> dict:
        """파일 또는 폴더의 이름을 변경합니다."""
        if not self._is_within_base_dirs(path):
            raise SynologyAPIError("접근 권한이 없는 경로입니다.")

        await self._ensure_session()
        params = {
            "api": "SYNO.FileStation.Rename",
            "version": "2",
            "method": "rename",
            "path": json.dumps([path]),
            "name": json.dumps([new_name]),
            "_sid": self._sid,
        }
        data = await self._raw_get("/webapi/entry.cgi", params)
        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            raise SynologyAPIError(f"이름 변경 실패 (에러 코드: {code})")

        files = data["data"].get("files", [])
        if files:
            return {"name": files[0]["name"], "path": files[0]["path"]}
        return {"name": new_name, "path": path}

    async def delete_item(self, path: str) -> bool:
        """파일 또는 폴더를 삭제합니다."""
        if not self._is_within_base_dirs(path):
            raise SynologyAPIError("접근 권한이 없는 경로입니다.")

        await self._ensure_session()
        params = {
            "api": "SYNO.FileStation.Delete",
            "version": "2",
            "method": "delete",
            "path": json.dumps([path]),
            "_sid": self._sid,
        }
        data = await self._raw_get("/webapi/entry.cgi", params)
        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            raise SynologyAPIError(f"삭제 실패 (에러 코드: {code})")
        return True

    async def upload_file(
        self, folder_path: str, filename: str, content: bytes, overwrite: bool = False
    ) -> dict:
        """파일을 NAS에 업로드합니다."""
        if not self._is_within_base_dirs(folder_path):
            raise SynologyAPIError("접근 권한이 없는 경로입니다.")

        await self._ensure_session()
        headers = {}
        if self._synotoken:
            headers["X-SYNO-TOKEN"] = self._synotoken

        async with httpx.AsyncClient(verify=self._verify_ssl) as client:
            resp = await client.post(
                f"{self._base_url}/webapi/entry.cgi",
                data={
                    "api": "SYNO.FileStation.Upload",
                    "version": "2",
                    "method": "upload",
                    "path": folder_path,
                    "overwrite": "true" if overwrite else "false",
                    "_sid": self._sid,
                },
                files={"file": (filename, content)},
                headers=headers,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()

        if not data.get("success"):
            code = data.get("error", {}).get("code", "unknown")
            raise SynologyAPIError(f"업로드 실패 (에러 코드: {code})")
        return {"name": filename, "path": f"{folder_path}/{filename}"}

    # ──────────────────────────────────────────
    # 상태 확인
    # ──────────────────────────────────────────

    async def check_connection(self) -> dict:
        """NAS 연결 상태를 확인합니다."""
        if not self._base_url or not self._username:
            return {"connected": False, "message": "시놀로지 NAS 설정이 없습니다."}

        try:
            await self._ensure_session()
            return {"connected": True, "message": "연결 성공"}
        except SynologyAuthError as e:
            return {"connected": False, "message": f"인증 실패: {e}"}
        except Exception as e:
            return {"connected": False, "message": f"연결 실패: {e}"}

    async def validate_path(self, path: str) -> bool:
        """NAS 경로가 존재하는지 확인합니다 (공개 API)."""
        await self._ensure_session()
        return await self._validate_path(path)

    # ──────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────

    async def _validate_path(self, path: str) -> bool:
        """NAS 경로가 실제 존재하는지 확인합니다."""
        params = {
            "api": "SYNO.FileStation.List",
            "version": "2",
            "method": "getinfo",
            "path": path,
            "_sid": self._sid,
        }
        try:
            data = await self._raw_get("/webapi/entry.cgi", params)
            if not data.get("success"):
                return False
            # getinfo returns success=True even for missing paths,
            # but each file entry has "code": 408 if not found.
            files = data.get("data", {}).get("files", [])
            if not files:
                return False
            return "code" not in files[0]
        except Exception:
            return False

    async def _raw_get(self, endpoint: str, params: dict) -> dict:
        """시놀로지 API에 GET 요청을 보내고 JSON을 반환합니다."""
        headers = {}
        if self._synotoken:
            headers["X-SYNO-TOKEN"] = self._synotoken
        async with httpx.AsyncClient(verify=self._verify_ssl) as client:
            resp = await client.get(
                f"{self._base_url}{endpoint}",
                params=params,
                headers=headers,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    async def _raw_post(self, endpoint: str, data: dict) -> dict:
        """시놀로지 API에 POST 요청을 보내고 JSON을 반환합니다."""
        async with httpx.AsyncClient(verify=self._verify_ssl) as client:
            resp = await client.post(
                f"{self._base_url}{endpoint}",
                data=data,
                timeout=30.0,
            )
            resp.raise_for_status()
            return resp.json()

    @staticmethod
    def _format_timestamp(ts: int) -> str:
        """유닉스 타임스탬프를 ISO 형식으로 변환합니다."""
        if not ts:
            return ""
        return datetime.fromtimestamp(ts).isoformat()
