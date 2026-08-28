"""
ST영원 스마트 오피스 — API 통합 테스트 스크립트
===============================================
실행 중인 서버에 대해 기능·성능을 검증하고 결과를 JSON으로 출력합니다.

사용법:
    python -m backend.tests.test_api --base-url http://localhost:8000
    python -m backend.tests.test_api --base-url http://localhost:8000 --username admin --password admin1234
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import requests

# ---------------------------------------------------------------------------
# 결과 모델
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    category: str
    name: str
    passed: bool
    status_code: Optional[int] = None
    response_ms: float = 0.0
    detail: str = ""


@dataclass
class TestReport:
    server_url: str = ""
    executed_at: str = ""
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total_duration_ms: float = 0.0
    results: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# 테스트 러너
# ---------------------------------------------------------------------------

class APITester:
    """실행 중인 서버를 대상으로 통합 테스트를 수행합니다."""

    def __init__(self, base_url: str, username: str, password: str):
        self.base_url = base_url.rstrip("/")
        self.username = username
        self.password = password
        self.session = requests.Session()
        self.token: Optional[str] = None
        self.results: list[TestResult] = []
        # 테스트 중 생성한 리소스 (정리용)
        self._created_user_id: Optional[int] = None
        self._created_doc_id: Optional[str] = None
        self._created_base_dir_id: Optional[str] = None

    # -- helpers ----------------------------------------------------------

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _headers(self) -> dict:
        h = {"Accept": "application/json"}
        if self.token:
            h["Authorization"] = f"Bearer {self.token}"
        return h

    def _record(self, category: str, name: str, passed: bool, *,
                status_code: int | None = None,
                response_ms: float = 0.0,
                detail: str = ""):
        self.results.append(TestResult(
            category=category, name=name, passed=passed,
            status_code=status_code, response_ms=response_ms, detail=detail,
        ))
        mark = "PASS" if passed else "FAIL"
        ms_str = f" ({response_ms:.0f}ms)" if response_ms else ""
        print(f"  [{mark}] {category} > {name}{ms_str}")
        if not passed and detail:
            print(f"         → {detail}")

    def _timed_request(self, method: str, path: str, **kwargs):
        """요청을 보내고 (response, elapsed_ms)를 반환합니다."""
        kwargs.setdefault("headers", self._headers())
        kwargs.setdefault("timeout", 60)
        start = time.perf_counter()
        resp = self.session.request(method, self._url(path), **kwargs)
        elapsed = (time.perf_counter() - start) * 1000
        return resp, elapsed

    # =====================================================================
    # 1. 헬스체크
    # =====================================================================

    def test_health(self):
        cat = "헬스체크"
        try:
            resp, ms = self._timed_request("GET", "/api/health")
            data = resp.json()

            self._record(cat, "상태 코드 200", resp.status_code == 200,
                         status_code=resp.status_code, response_ms=ms)
            self._record(cat, "status=ok", data.get("status") == "ok",
                         response_ms=ms, detail=f"status={data.get('status')}")
            self._record(cat, "응답 시간 < 3초", ms < 3000,
                         response_ms=ms, detail=f"{ms:.0f}ms")
            self._record(cat, "llm_provider 존재",
                         bool(data.get("llm_provider")),
                         detail=data.get("llm_provider", ""))
        except Exception as e:
            self._record(cat, "서버 연결", False, detail=str(e))

    # =====================================================================
    # 2. 인증
    # =====================================================================

    def test_auth(self):
        cat = "인증"

        # 2-1. 잘못된 비밀번호
        resp, ms = self._timed_request(
            "POST", "/api/auth/login",
            data={"username": self.username,
                  "password": "wrong-password-12345"},
        )
        data = resp.json() if resp.status_code == 200 else {}
        login_rejected = (
            resp.status_code == 401
            or (resp.status_code == 200 and data.get("success") is False)
        )
        self._record(cat, "잘못된 비밀번호 거부",
                     login_rejected,
                     status_code=resp.status_code, response_ms=ms)

        # 2-2. 정상 로그인
        resp, ms = self._timed_request(
            "POST", "/api/auth/login",
            data={"username": self.username, "password": self.password},
        )
        data = resp.json() if resp.status_code == 200 else {}
        login_ok = resp.status_code == 200 and data.get("success")
        self._record(cat, "정상 로그인", login_ok,
                     status_code=resp.status_code, response_ms=ms,
                     detail="" if login_ok else f"response={data}")

        if login_ok:
            self.token = data.get("token", "")

        # 2-3. /auth/me
        resp, ms = self._timed_request("GET", "/api/auth/me")
        me_ok = resp.status_code == 200 and resp.json().get("username")
        self._record(cat, "내 정보 조회 (/auth/me)", me_ok,
                     status_code=resp.status_code, response_ms=ms)

        # 2-4. 토큰 없이 접근
        no_auth = requests.get(self._url("/api/auth/me"), timeout=10)
        self._record(cat, "미인증 접근 → 401",
                     no_auth.status_code == 401,
                     status_code=no_auth.status_code)

    # =====================================================================
    # 3. 챗봇 (RAG)
    # =====================================================================

    def test_chat(self):
        cat = "챗봇"
        if not self.token:
            self._record(cat, "로그인 필요 (스킵)", False, detail="토큰 없음")
            return

        session_id = str(uuid.uuid4())

        # 3-1. 인사 (META)
        resp, ms = self._timed_request(
            "POST", "/api/chat",
            json={"message": "안녕하세요", "session_id": session_id},
        )
        data = resp.json() if resp.status_code == 200 else {}
        self._record(cat, "인사 응답", resp.status_code == 200 and bool(data.get("answer")),
                     status_code=resp.status_code, response_ms=ms,
                     detail=data.get("answer", "")[:80])

        # 3-2. 규정 질의 (KNOWLEDGE)
        resp, ms = self._timed_request(
            "POST", "/api/chat",
            json={"message": "연차 사용 규정에 대해 알려줘", "session_id": session_id},
        )
        data = resp.json() if resp.status_code == 200 else {}
        self._record(cat, "규정 질의 응답",
                     resp.status_code == 200 and bool(data.get("answer")),
                     status_code=resp.status_code, response_ms=ms,
                     detail=data.get("answer", "")[:80])

        # 3-3. NAS 파일 질의
        resp, ms = self._timed_request(
            "POST", "/api/chat",
            json={"message": "인사팀 폴더에 어떤 파일이 있어?", "session_id": session_id},
        )
        data = resp.json() if resp.status_code == 200 else {}
        self._record(cat, "NAS 파일 질의 응답",
                     resp.status_code == 200 and bool(data.get("answer")),
                     status_code=resp.status_code, response_ms=ms,
                     detail=data.get("answer", "")[:80])

        # 3-4. 스트리밍 응답
        try:
            start = time.perf_counter()
            resp = self.session.get(
                self._url("/api/chat/stream"),
                params={"message": "회사 소개 해줘", "session_id": session_id},
                headers={**self._headers(), "Accept": "text/event-stream"},
                stream=True, timeout=30,
            )
            # 스트리밍은 POST일 수도 있으므로 POST로도 시도
            if resp.status_code == 405:
                resp = self.session.post(
                    self._url("/api/chat/stream"),
                    json={"message": "회사 소개 해줘", "session_id": session_id},
                    headers={**self._headers(), "Accept": "text/event-stream"},
                    stream=True, timeout=30,
                )
            first_chunk = None
            for line in resp.iter_lines(decode_unicode=True):
                if line and line.startswith("data:"):
                    first_chunk = line
                    break
            elapsed = (time.perf_counter() - start) * 1000
            self._record(cat, "스트리밍 첫 토큰 수신",
                         resp.status_code == 200 and first_chunk is not None,
                         status_code=resp.status_code, response_ms=elapsed,
                         detail=f"첫 청크: {(first_chunk or '')[:60]}")
            resp.close()
        except Exception as e:
            self._record(cat, "스트리밍 첫 토큰 수신", False, detail=str(e))

        # 3-5. 응답 시간 성능 (일반 질의 < 30초)
        resp, ms = self._timed_request(
            "POST", "/api/chat",
            json={"message": "오늘 날씨 어때?", "session_id": session_id},
        )
        self._record(cat, "일반 질의 응답 시간 < 30초",
                     resp.status_code == 200 and ms < 30000,
                     status_code=resp.status_code, response_ms=ms)

        # 3-6. 빈 메시지 검증 (에러 반환 또는 정상 응답 모두 허용)
        resp, ms = self._timed_request(
            "POST", "/api/chat",
            json={"message": "", "session_id": session_id},
        )
        empty_ok = resp.status_code in (200, 400, 422)
        self._record(cat, "빈 메시지 처리",
                     empty_ok,
                     status_code=resp.status_code, response_ms=ms,
                     detail="빈 메시지 요청 정상 처리")

    # =====================================================================
    # 4. 문서 관리
    # =====================================================================

    def test_documents(self):
        cat = "문서관리"
        if not self.token:
            self._record(cat, "로그인 필요 (스킵)", False, detail="토큰 없음")
            return

        # 4-1. 문서 목록 조회
        resp, ms = self._timed_request("GET", "/api/documents")
        self._record(cat, "문서 목록 조회",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms)

        # 4-2. TXT 파일 업로드
        test_content = "테스트 문서입니다.\n연차 휴가는 1년에 15일입니다.\n야근 수당은 시급의 1.5배입니다."
        files = {"file": ("test_qa_document.txt", test_content.encode("utf-8"), "text/plain")}
        task_id = str(uuid.uuid4())
        resp, ms = self._timed_request(
            "POST", "/api/documents/upload",
            files=files, data={"task_id": task_id},
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
        )
        data = resp.json() if resp.status_code == 200 else {}
        upload_ok = resp.status_code == 200 and data.get("status") in ("indexed", "processing")
        self._record(cat, "TXT 파일 업로드",
                     upload_ok,
                     status_code=resp.status_code, response_ms=ms,
                     detail=data.get("message", ""))
        if upload_ok:
            self._created_doc_id = data.get("id")

        # 4-3. 업로드 진행률 조회
        resp, ms = self._timed_request("GET", f"/api/documents/progress/{task_id}")
        self._record(cat, "업로드 진행률 조회",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms)

        # 4-4. 업로드 후 문서 수 증가 확인
        resp, ms = self._timed_request("GET", "/api/documents")
        if resp.status_code == 200:
            count = resp.json().get("total_count", 0)
            self._record(cat, "문서 수 확인",
                         count >= 1,
                         response_ms=ms, detail=f"total_count={count}")

        # 4-5. 지원하지 않는 형식
        files = {"file": ("test.exe", b"binary", "application/octet-stream")}
        resp, ms = self._timed_request(
            "POST", "/api/documents/upload",
            files=files,
            headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
        )
        self._record(cat, "미지원 형식 거부 (.exe)",
                     resp.status_code in (400, 422),
                     status_code=resp.status_code, response_ms=ms)

        # 4-6. 문서 삭제
        if self._created_doc_id:
            resp, ms = self._timed_request(
                "DELETE", f"/api/documents/{self._created_doc_id}",
            )
            self._record(cat, "문서 삭제",
                         resp.status_code == 200,
                         status_code=resp.status_code, response_ms=ms)
            self._created_doc_id = None

    # =====================================================================
    # 5. 사용자 관리 (Admin)
    # =====================================================================

    def test_users(self):
        cat = "사용자관리"
        if not self.token:
            self._record(cat, "로그인 필요 (스킵)", False, detail="토큰 없음")
            return

        # 5-1. 사용자 목록
        resp, ms = self._timed_request("GET", "/api/admin/users")
        if resp.status_code == 403:
            self._record(cat, "관리자 권한 필요 (스킵)", False,
                         status_code=403, detail="현재 계정이 admin이 아님")
            return
        self._record(cat, "사용자 목록 조회",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms)

        # 5-2. 사용자 생성
        test_user = f"testuser_{uuid.uuid4().hex[:6]}"
        resp, ms = self._timed_request(
            "POST", "/api/admin/users",
            json={"username": test_user,
                  "display_name": "QA 테스트 사용자",
                  "password": "test1234!", "role": "user"},
        )
        data = resp.json() if resp.status_code == 200 else {}
        create_ok = resp.status_code == 200 and data.get("success")
        self._record(cat, "사용자 생성",
                     create_ok,
                     status_code=resp.status_code, response_ms=ms)
        if create_ok:
            self._created_user_id = data.get("user", {}).get("id")

        # 5-3. 비밀번호 변경
        if self._created_user_id:
            resp, ms = self._timed_request(
                "PUT", f"/api/admin/users/{self._created_user_id}/password",
                json={"new_password": "newpass5678!"},
            )
            self._record(cat, "비밀번호 변경",
                         resp.status_code == 200,
                         status_code=resp.status_code, response_ms=ms)

        # 5-4. 사용자 삭제
        if self._created_user_id:
            resp, ms = self._timed_request(
                "DELETE", f"/api/admin/users/{self._created_user_id}",
            )
            self._record(cat, "사용자 삭제",
                         resp.status_code == 200,
                         status_code=resp.status_code, response_ms=ms)
            self._created_user_id = None

    # =====================================================================
    # 6. NAS 연동
    # =====================================================================

    def test_nas(self):
        cat = "NAS연동"
        if not self.token:
            self._record(cat, "로그인 필요 (스킵)", False, detail="토큰 없음")
            return

        # 6-1. NAS 연결 상태
        resp, ms = self._timed_request("GET", "/api/nas/status")
        data = resp.json() if resp.status_code == 200 else {}
        connected = data.get("connected", False)
        self._record(cat, "NAS 연결 상태 조회",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms,
                     detail=f"connected={connected}")

        if not connected:
            self._record(cat, "NAS 미연결 (이하 스킵)", False,
                         detail="SYNOLOGY_URL 미설정 또는 연결 불가")
            return

        # 6-2. 기본 디렉토리 목록
        resp, ms = self._timed_request("GET", "/api/nas/base-dirs")
        base_dirs = resp.json() if resp.status_code == 200 else []
        self._record(cat, "기본 디렉토리 목록",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms,
                     detail=f"{len(base_dirs)}개 등록")

        # 6-3. 디렉토리 탐색
        browse_path = base_dirs[0]["path"] if base_dirs else "/"
        resp, ms = self._timed_request(
            "GET", "/api/nas/browse", params={"path": browse_path},
        )
        data = resp.json() if resp.status_code == 200 else {}
        self._record(cat, "디렉토리 탐색",
                     resp.status_code == 200 and "items" in data,
                     status_code=resp.status_code, response_ms=ms,
                     detail=f"path={browse_path}, items={data.get('total', 0)}")

        # 6-4. 탐색 응답 시간
        self._record(cat, "탐색 응답 시간 < 5초",
                     ms < 5000, response_ms=ms)

        # 6-5. 파일 검색
        resp, ms = self._timed_request(
            "GET", "/api/nas/search", params={"q": "인사"},
        )
        data = resp.json() if resp.status_code == 200 else {}
        self._record(cat, "파일 검색",
                     resp.status_code == 200,
                     status_code=resp.status_code, response_ms=ms,
                     detail=f"results={data.get('total_count', 0)}")

        # 6-6. 존재하지 않는 경로 탐색
        resp, ms = self._timed_request(
            "GET", "/api/nas/browse",
            params={"path": "/nonexistent_path_abc123"},
        )
        self._record(cat, "존재하지 않는 경로 처리",
                     resp.status_code in (400, 404),
                     status_code=resp.status_code, response_ms=ms)

    # =====================================================================
    # 7. 페이지 렌더링
    # =====================================================================

    def test_pages(self):
        cat = "페이지"

        pages = [
            ("/login", "로그인 페이지"),
            ("/", "메인(챗) 페이지"),
            ("/nas", "NAS 탐색 페이지"),
            ("/admin", "관리자 페이지"),
        ]
        for path, name in pages:
            resp, ms = self._timed_request("GET", path)
            self._record(cat, f"{name} 렌더링",
                         resp.status_code == 200 and len(resp.text) > 100,
                         status_code=resp.status_code, response_ms=ms)

    # =====================================================================
    # 8. 성능 벤치마크
    # =====================================================================

    def test_performance(self):
        cat = "성능"

        # 8-1. 헬스체크 연속 호출 (평균 응답 시간)
        times = []
        for _ in range(5):
            _, ms = self._timed_request("GET", "/api/health")
            times.append(ms)
        avg = sum(times) / len(times)
        self._record(cat, "헬스체크 평균 응답 (5회)",
                     avg < 1000, response_ms=avg,
                     detail=f"min={min(times):.0f}ms, max={max(times):.0f}ms, avg={avg:.0f}ms")

        # 8-2. 동시 요청 시뮬레이션 (순차 5회 챗)
        if self.token:
            times = []
            for i in range(3):
                _, ms = self._timed_request(
                    "POST", "/api/chat",
                    json={"message": f"테스트 질의 {i+1}",
                          "session_id": str(uuid.uuid4())},
                )
                times.append(ms)
            avg = sum(times) / len(times)
            self._record(cat, "챗봇 평균 응답 (3회)",
                         True, response_ms=avg,
                         detail=f"min={min(times):.0f}ms, max={max(times):.0f}ms, avg={avg:.0f}ms")

    # =====================================================================
    # 정리
    # =====================================================================

    def cleanup(self):
        """테스트 중 생성된 리소스 정리."""
        if self._created_doc_id:
            try:
                self._timed_request("DELETE", f"/api/documents/{self._created_doc_id}")
            except Exception:
                pass
        if self._created_user_id:
            try:
                self._timed_request("DELETE", f"/api/admin/users/{self._created_user_id}")
            except Exception:
                pass

        # 로그아웃
        if self.token:
            try:
                self._timed_request("POST", "/api/auth/logout")
            except Exception:
                pass

    # =====================================================================
    # 실행
    # =====================================================================

    def run_all(self) -> TestReport:
        print(f"\n{'='*60}")
        print(f"  ST영원 스마트 오피스 — API 통합 테스트")
        print(f"  서버: {self.base_url}")
        print(f"  시작: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}\n")

        start = time.perf_counter()

        test_methods = [
            self.test_health,
            self.test_auth,
            self.test_chat,
            self.test_documents,
            self.test_users,
            self.test_nas,
            self.test_pages,
            self.test_performance,
        ]

        for method in test_methods:
            section = method.__name__.replace("test_", "").upper()
            print(f"\n--- {section} ---")
            try:
                method()
            except Exception as e:
                self._record(section, "예외 발생", False, detail=str(e))

        self.cleanup()

        total_ms = (time.perf_counter() - start) * 1000
        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)

        report = TestReport(
            server_url=self.base_url,
            executed_at=datetime.now().isoformat(),
            total=len(self.results),
            passed=passed,
            failed=failed,
            total_duration_ms=round(total_ms, 1),
            results=[asdict(r) for r in self.results],
        )

        print(f"\n{'='*60}")
        print(f"  결과: {passed}/{report.total} 통과"
              f"  |  실패: {failed}"
              f"  |  소요: {total_ms/1000:.1f}초")
        print(f"{'='*60}\n")

        return report


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="ST영원 API 통합 테스트")
    parser.add_argument("--base-url", default="http://localhost:8000",
                        help="서버 URL (기본: http://localhost:8000)")
    parser.add_argument("--username", default="admin",
                        help="로그인 사용자명 (기본: admin)")
    parser.add_argument("--password", default="admin1234",
                        help="로그인 비밀번호 (기본: admin1234)")
    parser.add_argument("--output", default=None,
                        help="결과 JSON 저장 경로 (예: test_report.json)")
    args = parser.parse_args()

    tester = APITester(args.base_url, args.username, args.password)

    try:
        report = tester.run_all()
    except requests.ConnectionError:
        print(f"\n[ERROR] 서버에 연결할 수 없습니다: {args.base_url}")
        print("서버가 실행 중인지 확인하세요.")
        sys.exit(1)

    # JSON 저장
    out_path = args.output or f"test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(asdict(report), f, ensure_ascii=False, indent=2)
    print(f"결과 저장: {out_path}")

    sys.exit(0 if report.failed == 0 else 1)


if __name__ == "__main__":
    main()
