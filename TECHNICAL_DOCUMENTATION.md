# ST영원 스마트 오피스 - 기술 문서

> 에스티영원(ST Youngwon) 사내 AI 어시스턴트 + Synology NAS 파일 관리 서비스
> RAG(Retrieval-Augmented Generation) 기반 사내 문서 질의응답 시스템

---

## 목차

### Part 1. 사용자 가이드

1. [서비스 소개](#1-서비스-소개)
2. [설치 방법](#2-설치-방법)
3. [초기 설정](#3-초기-설정)
4. [사용 방법](#4-사용-방법)
5. [지원 파일 포맷](#5-지원-파일-포맷)
6. [문제 해결](#6-문제-해결)

### Part 2. 기술 상세 (개발자용)

7. [기술 스택](#7-기술-스택)
8. [프로젝트 구조](#8-프로젝트-구조)
9. [백엔드 아키텍처](#9-백엔드-아키텍처)
10. [Core 모듈](#10-core-모듈)
11. [서비스 레이어](#11-서비스-레이어)
12. [API 엔드포인트 명세](#12-api-엔드포인트-명세)
13. [Pydantic 모델/스키마](#13-pydantic-모델스키마)
14. [유틸리티](#14-유틸리티)
15. [프론트엔드 아키텍처](#15-프론트엔드-아키텍처)
16. [인증 및 권한 시스템](#16-인증-및-권한-시스템)
17. [데이터 흐름](#17-데이터-흐름)

### Part 3. 부록

- [A. 환경변수 레퍼런스](#부록-a-환경변수-레퍼런스)
- [B. 데이터 디렉토리 구조](#부록-b-데이터-디렉토리-구조)
- [C. 배포 및 인프라 상세](#부록-c-배포-및-인프라-상세)
- [D. 아키텍처 패턴 및 설계 원칙](#부록-d-아키텍처-패턴-및-설계-원칙)
- [E. 확장 가이드](#부록-e-확장-가이드)
- [F. 보안 고려사항](#부록-f-보안-고려사항)
- [G. 운영 관리](#부록-g-운영-관리)
- [H. API 직접 사용 (cURL)](#부록-h-api-직접-사용-curl)
- [I. 스크립트](#부록-i-스크립트)

---

# Part 1. 사용자 가이드

---

## 1. 서비스 소개

ST영원 스마트 오피스는 **사내 문서를 AI에게 학습시켜서 질문하면 답변해주는 서비스**입니다.

취업규칙, 근무규정 등의 문서를 업로드하면 AI가 내용을 학습하고, 직원들이 채팅으로 질문하면 해당 문서를 근거로 정확한 답변을 제공합니다. Synology NAS와 직접 연동하여 사내 파일을 웹에서 탐색·관리할 수 있습니다.

### 주요 기능

| 기능 | 설명 | 사용 대상 |
|------|------|----------|
| AI 채팅 | 사내 규정에 대해 질문하면 문서 근거와 함께 답변 | 모든 직원 |
| NAS 파일 탐색 | Synology NAS 파일을 웹에서 탐색·다운로드·업로드·삭제 | 관리자 |
| 문서 관리 | 규정 문서 업로드/삭제, AI 학습 데이터 관리 | 관리자 |
| NAS 경로 안내 | "파일 어디에 있어?" 질문 시 NAS 경로 안내 | 모든 직원 |
| 사용자 관리 | 직원 계정 생성, 비밀번호 초기화, 삭제 | 관리자 |

### 사용자 역할

- **관리자 (admin):** 문서 업로드/삭제, NAS 파일 탐색·관리, 사용자 관리, NAS 기본 디렉토리 관리
- **일반 사용자 (user):** AI 채팅 (NAS 경로 질문 포함)

> 일반 직원은 NAS 탐색 페이지에 접근할 수 없지만, 채팅에서 "파일 어디에 있어?" 같은 질문을 통해 NAS 경로를 안내받을 수 있습니다.

---

## 2. 설치 방법

### 사전 요구사항

- **Docker Desktop** 설치 필요 (Windows/Mac에서 [docker.com](https://www.docker.com/products/docker-desktop/) 다운로드)
- (선택) 외부 AI 서비스를 사용할 경우 API 키 필요 (OpenAI, Claude, Gemini 중 택1)
- (선택) 무료 로컬 AI를 사용할 경우 Ollama 설치
- (선택) Synology NAS 연동 시 NAS 관리자 계정 정보

### 방법 1: Docker 설치 (권장)

```bash
# 1. 프로젝트 폴더로 이동
cd ST_YOUNGWON

# 2. 환경 설정 파일 복사
cp .env.example .env

# 3. .env 파일을 메모장 등으로 열어서 아래 항목 수정
#    - LLM_PROVIDER: 사용할 AI 선택 (openai / claude / gemini / ollama)
#    - 선택한 AI의 API 키 입력 (예: OPENAI_API_KEY=sk-xxxx)
#    - SYNOLOGY_URL, SYNOLOGY_USERNAME, SYNOLOGY_PASSWORD: NAS 연동 시 설정
#    - ADMIN_PASSWORD: 관리자 비밀번호 설정
#    - SECRET_KEY: 아무 긴 문자열로 변경

# 4. 서비스 시작
docker compose up -d --build

# 5. 브라우저에서 접속
#    http://localhost:8080
```

### 방법 2: 무료 로컬 AI (Ollama) 사용

별도 API 키 없이 PC에서 직접 AI를 돌리는 방법입니다. PC 사양이 충분해야 합니다 (RAM 8GB 이상 권장).

```bash
# 1. 환경 설정
cp .env.example .env
# .env 파일에서 LLM_PROVIDER=ollama 확인 (기본값이라 수정 불필요)

# 2. Ollama 포함 서비스 시작
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build

# 3. AI 모델 다운로드 (최초 1회, 수 분 소요)
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama pull nomic-embed-text

# 4. 브라우저에서 접속
#    http://localhost:8080
```

### 방법 3: 다른 PC의 Ollama 사용

Ollama가 설치된 별도 PC가 있는 경우:

```bash
# .env 파일에서 해당 PC의 IP 주소로 설정
OLLAMA_BASE_URL=http://192.168.1.100:11434
LLM_PROVIDER=ollama
EMBEDDING_PROVIDER=ollama
```

### 서비스 중지/재시작

```bash
# 서비스 중지
docker compose down

# 서비스 재시작
docker compose up -d

# 상태 확인
docker compose ps
```

---

## 3. 초기 설정

서비스 설치 후 관리자가 수행해야 할 초기 설정 단계입니다.

### 3.1 관리자 로그인

1. 브라우저에서 `http://localhost:8080` 접속
2. 기본 관리자 계정으로 로그인:
   - **아이디:** `admin`
   - **비밀번호:** `.env` 파일에서 설정한 `ADMIN_PASSWORD` (기본값: `admin1234`)
3. 로그인 후 채팅 페이지로 이동, 상단 내비게이션에서 관리 페이지 접근 가능

### 3.2 사내 문서 업로드

AI가 답변할 수 있으려면 먼저 사내 문서를 업로드해야 합니다.

1. 관리자 페이지(`/admin`)의 **문서 업로드** 영역으로 이동
2. 파일을 **드래그앤드롭**하거나 클릭하여 선택
3. 지원 포맷: PDF, DOCX, XLSX, PPTX, HWPX, TXT 등 (상세 목록은 [5. 지원 파일 포맷](#5-지원-파일-포맷) 참고)
4. 업로드 진행률 바가 표시됨 (대용량 파일은 수 분 소요)
5. 완료되면 문서 목록에 **"indexed"** 상태로 표시

**업로드 과정:**
```
파일 업로드 → 텍스트 추출 → 내용 분석 → AI 학습 데이터 생성 → 완료
```

> 여러 문서를 한꺼번에 업로드하려면 CLI를 사용할 수 있습니다:
> `data/documents/` 폴더에 PDF 파일을 넣고 `make seed` 실행

### 3.3 직원 계정 생성

1. 관리자 페이지 **사용자 관리** 섹션
2. **"사용자 추가"** 버튼 클릭
3. 입력 항목:
   - **아이디:** 로그인에 사용할 ID
   - **이름:** 표시될 이름
   - **비밀번호:** 초기 비밀번호
   - **역할:** 사용자 또는 관리자
4. 생성된 계정으로 직원이 로그인 가능

### 3.4 NAS 기본 디렉토리 등록 (선택)

Synology NAS와 연동하여 파일 탐색·경로 안내 기능을 사용하려면 기본 디렉토리를 등록해야 합니다.

1. `.env` 파일에서 Synology NAS 접속 정보 설정:
   ```
   SYNOLOGY_URL=https://your-nas-address:5001
   SYNOLOGY_USERNAME=admin
   SYNOLOGY_PASSWORD=your-password
   ```
2. 관리자 페이지의 **NAS 기본 디렉토리 관리** 섹션
3. 입력 항목:
   - **NAS 경로:** `/인사팀` 형식의 공유 폴더 경로
   - **표시 이름:** 예: 인사팀 공유폴더
   - **설명:** 예: 인사팀 규정 및 양식
4. **경로 확인** 버튼으로 NAS에 경로 존재 여부 검증 후 **추가**

> 등록된 기본 디렉토리는 NAS 탐색 페이지의 루트로 표시되며, 1시간 주기로 파일 인덱스가 자동 갱신되어 채팅에서 경로 안내에 활용됩니다.

---

## 4. 사용 방법

### 4.1 AI 채팅

**접속:** 상단 메뉴 **"채팅"** 클릭 또는 메인 페이지(`/`)

**기본 사용법:**
1. 하단 입력창에 질문 입력
2. **Enter**로 전송 (줄바꿈은 **Shift+Enter**)
3. AI가 실시간으로 답변을 생성하여 표시
4. 답변 하단에 **참고 출처** (문서명, 조항, 관련도)가 표시됨

**추천 질문 (첫 화면에서 클릭 가능):**
- "연차 사용 규정이 어떻게 되나요?"
- "출퇴근 시간은 어떻게 되나요?"
- "경조사 휴가 규정을 알려주세요"
- "취업규칙 파일은 어디에 있나요?"

**질문 유형별 동작:**

| 질문 유형 | 예시 | AI 동작 |
|-----------|------|---------|
| 규정 질의 | "연차 규정 알려줘" | 업로드된 문서에서 검색 → 출처와 함께 답변 |
| NAS 경로 | "인사팀 파일 어디에 있어?" | NAS 파일 인덱스 검색 → 경로·파일 크기 안내 |
| 인사/기능 문의 | "안녕", "뭐 할 수 있어?" | 친근한 인사 + 사용 가능한 기능 소개 |
| 미등록 내용 | (업로드 안 된 내용) | 일반 지식으로 답변 + "담당 부서에 확인하세요" 안내 |

**참고:**
- 대화 맥락이 유지되어 이전 질문을 참고한 후속 질문이 가능합니다 (최대 10턴)
- 페이지를 새로고침하면 대화 히스토리가 초기화됩니다

---

### 4.2 NAS 파일 탐색 (관리자 전용)

**접속:** 상단 메뉴 **"NAS 탐색"** 클릭 (`/nas`) — 관리자만 표시됨

**파일 탐색:**
- 등록된 기본 디렉토리 중 하나를 클릭하여 진입
- 폴더를 **더블클릭**하여 하위 폴더로 이동
- 상단 **브레드크럼**(경로 표시)을 클릭하여 상위 폴더로 이동
- 우측 상단에서 **그리드/리스트** 보기 전환 가능
- 파일을 **더블클릭**하면 다운로드
- **검색창**에 파일명을 입력하여 현재 경로 내 파일 검색

**파일 관리:**

| 작업 | 방법 |
|------|------|
| 폴더 생성 | **"새 폴더"** 버튼 → 이름 입력 → 만들기 |
| 파일 업로드 | **"업로드"** 버튼 → 파일 드래그앤드롭 또는 선택 (최대 500MB) |
| 이름 변경 | 파일/폴더 **우클릭** → 컨텍스트 메뉴에서 **"이름 변경"** |
| 삭제 | 파일/폴더 **우클릭** → 컨텍스트 메뉴에서 **"삭제"** |
| 다운로드 | 파일 **우클릭** → **"다운로드"** 또는 더블클릭 |

---

### 4.3 관리자 패널

**접속:** 상단 메뉴 **"관리"** 클릭 (`/admin`) — 관리자만 표시됨

**시스템 상태 확인:**
- 인덱싱된 문서 수, 총 청크 수, 현재 사용 중인 AI 모델, NAS 연결 상태, 등록 디렉토리 수

**문서 관리:**
- 문서 업로드: 드래그앤드롭, 진행률 바 + 예상 완료 시간 표시
- 문서 목록: 파일명, 업로드일, 청크 수, 상태 확인 (페이지네이션 지원, 10건 단위)
- 문서 삭제: 원본 파일 + AI 학습 데이터 모두 삭제

**NAS 기본 디렉토리 관리:**
- 디렉토리 추가 (NAS 경로, 표시 이름, 설명)
- 경로 존재 여부 검증
- 디렉토리 삭제

**사용자 관리:**
- 사용자 추가 (아이디, 이름, 비밀번호, 역할) — 페이지네이션 지원
- 비밀번호 초기화
- 사용자 삭제 (기본 admin 계정은 삭제 불가)

---

## 5. 지원 파일 포맷

### AI가 학습 가능한 포맷 (텍스트 추출 → 인덱싱)

| 카테고리 | 확장자 |
|----------|--------|
| 오피스 문서 | PDF, DOCX, XLSX, PPTX, HWPX |
| 텍스트 파일 | TXT, MD, CSV, JSON, LOG |
| 웹 문서 | XML, HTML, HTM |
| 설정 파일 | YAML, YML, TOML, INI, CFG, CONF |
| 코드 파일 | PY, JS, TS, JAVA, C, CPP, H, SQL, SH, BAT, PS1 |

### 저장만 가능한 포맷 (인덱싱 불가)

| 카테고리 | 확장자 |
|----------|--------|
| 이미지 | JPG, JPEG, PNG, GIF, BMP, SVG, ICO, WEBP |
| 동영상/오디오 | MP3, MP4, AVI, MOV, WAV, FLAC |
| 압축 파일 | ZIP, TAR, GZ, 7Z, RAR |
| 실행 파일 | EXE, DLL, SO, BIN |
| 레거시 | HWP (구형 한글 파일) |

> 최대 업로드 크기: 문서 200MB (환경변수 `MAX_UPLOAD_SIZE_MB`로 변경 가능), NAS 파일 500MB

---

## 6. 문제 해결

### 서비스가 시작되지 않을 때

```bash
# 로그 확인
docker compose logs -f app

# 컨테이너 상태 확인
docker compose ps

# 재시작
docker compose down && docker compose up -d
```

### AI 답변이 나오지 않을 때

- `.env` 파일에서 `LLM_PROVIDER`와 해당 API 키가 올바르게 설정되었는지 확인
- Ollama 사용 시 모델이 다운로드되었는지 확인: `docker compose exec ollama ollama list`
- 헬스 체크: `http://localhost:8080/api/health` 접속하여 상태 확인

### 문서 업로드 후 검색이 안 될 때

- 관리자 패널에서 문서 상태가 **"indexed"**인지 확인
- **"error"** 상태면 해당 문서를 삭제 후 재업로드
- 지원되지 않는 포맷인지 [5. 지원 파일 포맷](#5-지원-파일-포맷) 확인

### NAS 연결이 안 될 때

- `.env`의 `SYNOLOGY_URL`, `SYNOLOGY_USERNAME`, `SYNOLOGY_PASSWORD` 확인
- NAS 관리 페이지에서 해당 계정이 FileStation 접근 권한이 있는지 확인
- HTTPS 사용 시 자체 서명 인증서인 경우 `SYNOLOGY_VERIFY_SSL=false` 설정
- 관리자 페이지 시스템 상태에서 NAS 연결 상태 확인

### 로그인이 안 될 때

- `.env` 파일의 `ADMIN_PASSWORD` 값 확인
- 서비스를 재시작하면 기본 admin 계정이 새 비밀번호로 재생성됨
- 브라우저 쿠키 삭제 후 재시도

### 접속 포트 변경

`.env` 파일에서 `APP_PORT`를 원하는 포트로 변경:
```bash
APP_PORT=9090  # 기본값: 8080
```
변경 후 `docker compose down && docker compose up -d` 재시작

---

# Part 2. 기술 상세 (개발자용)

---

## 7. 기술 스택

| 분류 | 기술 | 설명 |
|------|------|------|
| Backend | Python 3.11 + FastAPI | 비동기 우선 웹 프레임워크 |
| Frontend | Jinja2 + Vanilla JS | 서버사이드 렌더링 + 클라이언트 인터랙션 |
| Vector DB | ChromaDB (embedded) | 임베디드 벡터 데이터베이스 (영구 저장) |
| Database | SQLite | 사용자 관리 |
| LLM | OpenAI / Claude / Gemini / Ollama | 다중 LLM 프로바이더 (하이브리드) |
| Embedding | OpenAI text-embedding-3-small / Ollama nomic-embed-text | 텍스트 임베딩 |
| NAS | Synology FileStation API (DSM 7) | NAS 파일 관리 |
| Auth | JWT + bcrypt | 토큰 기반 인증 + 비밀번호 해싱 |
| Deploy | Docker Compose | 멀티스테이지 빌드 + 오케스트레이션 |
| ASGI Server | Uvicorn | 비동기 서버 |

**Python 의존성 (20개 패키지):**

| 카테고리 | 패키지 | 용도 |
|----------|--------|------|
| 웹 프레임워크 | fastapi>=0.109.0 | 비동기 웹 프레임워크 |
| | uvicorn[standard]>=0.27.0 | ASGI 서버 |
| | python-multipart>=0.0.6 | Form/파일 업로드 파싱 |
| | jinja2>=3.1.3 | 템플릿 렌더링 |
| LLM 클라이언트 | openai>=1.12.0 | OpenAI API |
| | anthropic>=0.18.0 | Anthropic Claude API |
| | google-genai>=1.0.0 | Google Gemini API |
| | httpx>=0.27.0 | 비동기 HTTP 클라이언트 (Ollama, Synology) |
| 벡터 DB | chromadb>=0.4.22 | 임베디드 벡터 데이터베이스 |
| 문서 처리 | pymupdf>=1.23.0 | PDF 텍스트 추출 |
| | python-docx>=1.1.0 | Word 문서 추출 |
| | openpyxl>=3.1.0 | Excel 스프레드시트 추출 |
| | python-pptx>=0.6.23 | PowerPoint 추출 |
| 설정 관리 | pydantic>=2.5.0 | 데이터 검증 |
| | pydantic-settings>=2.1.0 | 환경변수 기반 설정 |
| | python-dotenv>=1.0.0 | .env 파일 로딩 |
| | PyYAML>=6.0.1 | YAML 파싱 |
| 유틸리티 | aiofiles>=23.2.0 | 비동기 파일 I/O |
| | python-jose[cryptography]>=3.3.0 | JWT 토큰 |
| 인증 | bcrypt>=4.0.0 | 비밀번호 해싱 |

**총 코드 규모:**
- 백엔드 Python: ~3,888줄 (16개 모듈)
- 프론트엔드 HTML: ~505줄 (5개 템플릿)
- 프론트엔드 CSS: ~1,644줄
- 프론트엔드 JS: ~1,529줄 (4개 파일)
- 인프라/설정: ~233줄

---

## 8. 프로젝트 구조

```
ST_YOUNGWON/
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                 (163줄) - FastAPI 엔트리포인트, 라우팅, 인증 API
│   │   ├── config.py               (86줄)  - Pydantic Settings, 모든 환경변수 정의
│   │   ├── database.py             (55줄)  - SQLite 초기화, 사용자 테이블
│   │   ├── dependencies.py         (116줄) - DI 컨테이너, JWT 인증 함수
│   │   │
│   │   ├── api/                    # API 라우트 핸들러 (511줄)
│   │   │   ├── router.py           (12줄)  - 라우터 통합
│   │   │   ├── chat.py             (62줄)  - 채팅 (동기/스트리밍)
│   │   │   ├── documents.py        (83줄)  - 문서 업로드/관리
│   │   │   ├── nas_browser.py      (261줄) - NAS 탐색/파일 관리 (관리자 전용)
│   │   │   ├── users.py            (87줄)  - 사용자 관리 (관리자 전용)
│   │   │   └── health.py           (32줄)  - 헬스 체크
│   │   │
│   │   ├── core/                   # 핵심 비즈니스 로직 (799줄)
│   │   │   ├── llm_provider.py     (252줄) - LLM 프로바이더 구현체
│   │   │   ├── embeddings.py       (138줄) - 임베딩 프로바이더
│   │   │   ├── vectorstore.py      (258줄) - ChromaDB 래퍼, 하이브리드 검색
│   │   │   ├── prompts.py          (126줄) - 시스템 프롬프트 & 템플릿
│   │   │   └── progress.py         (30줄)  - 스레드 안전 진행률 추적
│   │   │
│   │   ├── services/               # 서비스 레이어 (1,464줄)
│   │   │   ├── synology_service.py (581줄) - Synology FileStation API 클라이언트
│   │   │   ├── chat_service.py     (336줄) - RAG 채팅 오케스트레이션
│   │   │   ├── nas_index_service.py(189줄) - NAS 파일 주기적 인덱싱
│   │   │   ├── document_service.py (204줄) - 문서 업로드/인덱싱
│   │   │   └── user_service.py     (119줄) - 사용자 CRUD
│   │   │
│   │   ├── models/
│   │   │   └── schemas.py          (128줄) - Pydantic 요청/응답 모델
│   │   │
│   │   └── utils/                  # 유틸리티 (545줄)
│   │       ├── file_parser.py      (227줄) - 30+ 포맷 텍스트 추출
│   │       ├── text_chunker.py     (229줄) - 한국어 규정 최적화 청킹
│   │       ├── korean_utils.py     (45줄)  - 한국어 정규화
│   │       └── pdf_parser.py       (48줄)  - PDF 전용 추출
│   │
│   ├── requirements.txt            (34줄)  - Python 패키지 의존성
│   └── tests/
│       └── __init__.py
│
├── frontend/
│   ├── templates/                  # Jinja2 템플릿 (505줄)
│   │   ├── base.html               (50줄)  - 베이스 레이아웃 (헤더, 네비게이션)
│   │   ├── chat.html               (45줄)  - 채팅 인터페이스
│   │   ├── nas.html                (150줄) - NAS 파일 탐색 + 관리 (모달, 컨텍스트 메뉴)
│   │   ├── admin.html              (196줄) - 관리자 패널 (상태, 문서, NAS, 사용자)
│   │   └── login.html              (69줄)  - 로그인
│   └── static/
│       ├── css/
│       │   └── style.css           (1,644줄) - 전체 스타일 (반응형)
│       ├── js/
│       │   ├── auth.js             (49줄)  - 인증 로직
│       │   ├── chat.js             (247줄) - 채팅 로직 (SSE 스트리밍)
│       │   ├── nas.js              (592줄) - NAS 탐색/파일 관리
│       │   └── admin.js            (645줄) - 관리자 패널 (페이지네이션 포함)
│       └── img/
│           └── favicon.png         - 사이트 아이콘
│
├── config/
│   └── settings.yaml               (57줄)  - 설정 레퍼런스
│
├── scripts/
│   └── seed_documents.py           (46줄)  - 문서 초기 인덱싱
│
├── data/                           # 영구 데이터 (Docker 볼륨)
│   ├── chromadb/                   # 벡터 DB 데이터
│   ├── documents/                  # 업로드된 원본 문서
│   ├── extracted/                  # 추출된 텍스트 캐시
│   ├── nas/                        # NAS 메타데이터 (기본 디렉토리 목록)
│   └── users.db                    # 사용자 DB
│
├── Dockerfile                      (40줄)  - 멀티스테이지 빌드
├── docker-compose.yml              (52줄)  - 메인 Compose
├── docker-compose.ollama.yml       (28줄)  - Ollama 확장
├── Makefile                        (41줄)  - 개발 명령어
├── .env.example                    (80줄)  - 환경변수 템플릿
├── .gitignore
├── CLAUDE.md                       # 프로젝트 가이드
└── TECHNICAL_DOCUMENTATION.md      # 기술 문서 (본 파일)
```

---

## 9. 백엔드 아키텍처

### 9.1 애플리케이션 엔트리포인트 (`main.py`)

**파일:** `backend/app/main.py` (163줄)

FastAPI 애플리케이션의 진입점으로, 라이프사이클 관리, 라우팅, 인증 API를 포함한다.

**Lifespan 관리 (async context manager):**
- Startup: 로깅 초기화, 필수 디렉토리 생성 (documents, extracted, chromadb 등), DB 초기화, NAS 인덱스 서비스 주기적 스캔 시작 (1시간 간격)
- Shutdown: NAS 인덱스 서비스 정리, 로깅 정리

**정적 파일 & 템플릿:**
- `/static` → `frontend/static` 마운트
- Jinja2 템플릿 → `frontend/templates`

**페이지 라우트:**
```
GET  /login  → login.html
GET  /       → chat.html (메인 채팅)
GET  /nas    → nas.html (NAS 파일 탐색, 관리자 전용)
GET  /admin  → admin.html (관리자 대시보드)
```

**인증 API (main.py 내 직접 정의):**
```
POST /api/auth/login   → 로그인, JWT 토큰 발급, httponly 쿠키 설정
POST /api/auth/logout  → 로그아웃, 쿠키 삭제
GET  /api/auth/me      → 현재 사용자 정보 (JWT 검증)
```

**API 라우터 포함:**
```python
app.include_router(api_router, prefix="/api")
# api_router는 chat, documents, nas_browser, users, health 라우터를 통합
```

---

### 9.2 설정 시스템 (`config.py`)

**파일:** `backend/app/config.py` (86줄)

Pydantic Settings 기반 환경변수 관리 시스템이다. `.env` 파일에서 자동 로딩한다.

```python
class Settings(BaseSettings):
    # 애플리케이션
    APP_NAME: str = "ST영원 스마트 오피스"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # 경로 (프로젝트 루트 기준, 환경변수 오버라이드 가능)
    DATA_DIR: Path          # → data/
    DOCUMENTS_DIR: Path     # → data/documents/
    EXTRACTED_DIR: Path     # → data/extracted/
    CHROMADB_DIR: Path      # → data/chromadb/
    BASE_DIRS_FILE: Path    # → data/nas/base_dirs.json

    # LLM 프로바이더
    LLM_PROVIDER: str = "ollama"    # openai | claude | gemini | ollama
    LLM_TEMPERATURE: float = 0.3
    LLM_MAX_TOKENS: int = 1024

    # OpenAI
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"

    # Anthropic Claude
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-3-5-haiku-20241022"

    # Google Gemini
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = "gemini-2.0-flash"

    # Ollama
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "gemma3:4b"

    # 임베딩
    EMBEDDING_PROVIDER: str = "ollama"  # openai | ollama
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    OLLAMA_EMBEDDING_MODEL: str = "nomic-embed-text"

    # RAG 파라미터
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 100
    RETRIEVAL_TOP_K: int = 5
    SIMILARITY_THRESHOLD: float = 0.3

    # Synology NAS
    SYNOLOGY_URL: str = ""
    SYNOLOGY_USERNAME: str = ""
    SYNOLOGY_PASSWORD: str = ""
    SYNOLOGY_VERIFY_SSL: bool = False

    # 업로드 / 인증
    MAX_UPLOAD_SIZE_MB: int = 200
    ADMIN_PASSWORD: str = "admin1234"
    SECRET_KEY: str = "change-this-secret-key-in-production"
```

**경로 해석 전략:** `_resolve_data_path()` 헬퍼를 통해 환경변수가 설정되어 있으면 해당 값을, 없으면 프로젝트 루트 기준 상대 경로를 사용한다.

---

### 9.3 데이터베이스 (`database.py`)

**파일:** `backend/app/database.py` (55줄)

SQLite 기반 사용자 관리 데이터베이스이다. 파일 위치: `{DATA_DIR}/users.db`

**Users 테이블 스키마:**
```sql
CREATE TABLE users (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    username        TEXT UNIQUE NOT NULL,
    display_name    TEXT DEFAULT '',
    hashed_password TEXT NOT NULL,
    role            TEXT DEFAULT 'user',    -- 'user' | 'admin'
    is_active       INTEGER DEFAULT 1,
    created_at      TEXT DEFAULT datetime('now')
)
```

**기본 관리자 계정:** username `admin` / display_name `관리자` / 비밀번호 `{ADMIN_PASSWORD}` (bcrypt 해시). 최초 실행 시 자동 생성.

---

### 9.4 의존성 주입 & 인증 (`dependencies.py`)

**파일:** `backend/app/dependencies.py` (116줄)

**싱글톤 서비스 팩토리:**
```python
get_vectorstore()         → VectorStore (ChromaDB 래퍼)
get_nas_index_service()   → NASIndexService (NAS 파일 인덱싱)
get_chat_service()        → ChatService (RAG 채팅)
get_document_service()    → DocumentService (문서 관리)
get_synology_service()    → SynologyService (NAS API 클라이언트)
get_user_service()        → UserService (사용자 CRUD)
```

**인증 함수:**
```python
create_token(user: dict) → str
    # JWT 생성: {user_id, username, role}을 HS256으로 서명

async def get_current_user(request, auth_token) → dict
    # Authorization 헤더 또는 Cookie에서 JWT 추출/검증
    # 실패 시: HTTPException 401

async def verify_admin(request, auth_token) → dict
    # get_current_user() + role == 'admin' 검증
    # 실패 시: HTTPException 403
```

---

## 10. Core 모듈

### 10.1 LLM 프로바이더 (`core/llm_provider.py`)

**파일:** `backend/app/core/llm_provider.py` (252줄)

Protocol 기반 다중 LLM 추상화 레이어이다.

```python
class LLMProvider(Protocol):
    async def generate(system: str, user: str, history: list[dict] | None) → str
    async def generate_stream(system: str, user: str, history: list[dict] | None) → AsyncIterator[str]
```

**구현체 4종:**

| 클래스 | SDK | 메시지 형식 | 스트리밍 |
|--------|-----|------------|---------|
| `OpenAIProvider` | AsyncOpenAI | `[{role: system}, ...history, {role: user}]` | `stream=True` |
| `ClaudeProvider` | AsyncAnthropic | system 별도 전달, `[...history, {role: user}]` | `messages.stream()` |
| `GeminiProvider` | google.genai async | `[{role, parts: [{text}]}]` + `system_instruction` | `generate_content_stream()` |
| `OllamaProvider` | httpx (직접 호출) | OpenAI 호환 `[{role, content}]` | `{base_url}/api/chat` + `stream: true` |

**OllamaProvider 특이사항:** SDK 없이 httpx로 직접 HTTP 호출. 타임아웃 120초. 배치 실패 시 개별 메시지 스트리밍으로 폴백.

**팩토리 함수:** `create_llm_provider()` — `settings.llm_provider` 값에 따라 적절한 구현체 인스턴스화.

---

### 10.2 임베딩 프로바이더 (`core/embeddings.py`)

**파일:** `backend/app/core/embeddings.py` (138줄)

```python
class EmbeddingProvider(Protocol):
    def encode(texts: list[str]) → list[list[float]]
    @property
    def dimension(self) → int
```

**OpenAIEmbeddings:** 모델 `text-embedding-3-small` (1536 차원), 동기 호출.

**OllamaEmbeddings:** 모델 `nomic-embed-text`, 동기 httpx 호출.
- 스마트 배치: `{base_url}/api/embed` 배치 → 실패 시 개별 폴백
- 빈/공백 텍스트 자동 필터링, 결과 순서 유지
- 차원 자동 감지
- 타임아웃: 배치 300초, 개별 120초

---

### 10.3 벡터 스토어 (`core/vectorstore.py`)

**파일:** `backend/app/core/vectorstore.py` (258줄)

ChromaDB 래퍼로 하이브리드 검색(키워드 + 벡터)을 구현한다.

**컬렉션:**
```python
REGULATIONS_COLLECTION = "st_youngwon_regulations"  # 사내 규정 문서
```

**주요 메서드:**

```python
add_documents(collection_name, documents, metadatas, ids, on_embed_progress)
    # 배치 임베딩 (10개씩) + 진행률 콜백
    # 빈 임베딩 필터링, 차원 불일치 시 컬렉션 자동 재생성

search(collection_name, query, top_k=5)  # ⭐ 하이브리드 검색
    # 1단계: 키워드 검색 — 쿼리에서 키워드 추출, ChromaDB $contains 쿼리
    #   키워드 점수 = 0.7 + 0.3 * (hits / max_hits)
    # 2단계: 벡터 검색 (보충) — 키워드 결과 부족 시에만 실행
    #   벡터 점수 = 0.7 * (1 - distance)

delete_by_source(collection_name, source_file)
get_collection_count(collection_name)
```

**키워드 추출 (`_extract_keywords`):**
- 한국어 불용어 필터링 (이, 가, 은, 는, 을, 를 등)
- 최소 2자, 한국어만 (`[가-힣]+`)
- 동의어 확장: 26종 HR 용어 (휴가 → [연차, 연차유급휴가, ...], 급여, 경조사, 출퇴근 등)

---

### 10.4 프롬프트 시스템 (`core/prompts.py`)

**파일:** `backend/app/core/prompts.py` (126줄)

5종의 시스템 프롬프트와 4종의 템플릿 함수를 정의한다.

| 프롬프트/템플릿 | 용도 | 변수 |
|----------------|------|------|
| `SYSTEM_PROMPT` | 규정 질의응답 시스템 프롬프트 | — |
| `META_SYSTEM_PROMPT` | 인사/기능 문의 시스템 프롬프트 | — |
| `QA_PROMPT_TEMPLATE` | 규정 질의응답 | `{context}`, `{question}` |
| `NAS_SEARCH_PROMPT_TEMPLATE` | NAS 경로 안내 (파일 경로·크기 포함) | `{nas_results}`, `{question}` |
| `FALLBACK_PROMPT_TEMPLATE` | 등록 자료 없을 때 | `{question}` |
| `META_PROMPT_TEMPLATE` | 인사/기능 문의 | `{question}` |

**NAS_SEARCH_PROMPT_TEMPLATE 특이사항:** 검색 결과에 파일 전체 경로와 크기를 포함하며, 결과 없음/단일 결과/다중 결과에 대한 예시 답변을 프롬프트에 포함하여 일관된 응답 형식을 유도한다.

---

### 10.5 진행률 추적 (`core/progress.py`)

**파일:** `backend/app/core/progress.py` (30줄)

스레드 안전한 전역 진행률 딕셔너리이다.

```python
_progress: dict[str, dict]  # {task_id: {step, percent, detail}}
_lock = threading.Lock()

update_progress(task_id, step, percent, detail)
get_progress(task_id) → Optional[dict]
clear_progress(task_id)  # 완료 후 3초 뒤 자동 정리
```

단계: `saving` → `extracting` → `chunking` → `embedding` → `finalizing` → `done`

---

## 11. 서비스 레이어

### 11.1 SynologyService

**파일:** `backend/app/services/synology_service.py` (581줄)

Synology DSM 7 FileStation API 클라이언트이다. NAS 파일 탐색, 검색, 다운로드, 업로드, 삭제, 이름 변경, 폴더 생성 기능을 제공한다.

**인증:**
```python
login()     # SYNO.API.Auth, version 6, method login (DSM 7)
logout()    # SYNO.API.Auth, version 6, method logout
_ensure_session()  # 세션 자동 갱신 (syno_token 관리)
```

**기본 디렉토리 관리:**
```python
list_base_dirs()       # JSON 파일에서 등록된 디렉토리 목록 반환
add_base_dir()         # NAS에 실제 존재하는지 검증 후 등록
remove_base_dir()      # 등록 해제
_is_within_base_dirs() # 보안: 요청 경로가 등록된 기본 디렉토리 내에 있는지 검증
```

**파일 탐색:**
```python
list_directory(path, offset, limit, sort_by, sort_direction)
    # SYNO.FileStation.List, version 2, method list
    # 정렬: name, size, mtime / asc, desc
    # 페이지네이션: offset + limit

search_files(query, path, extension)
    # SYNO.FileStation.Search, version 2
    # 시작 → 폴링(최대 30초) → 결과 수집 → 정리
    # 전체 기본 디렉토리에서 검색

download_file(path) → (content, filename)
    # SYNO.FileStation.Download, version 2, method download
    # Content-Disposition 헤더에서 파일명 추출
```

**파일 관리:**
```python
create_folder(folder_path, name)   # SYNO.FileStation.CreateFolder
upload_file(folder_path, filename, content, overwrite)  # SYNO.FileStation.Upload (multipart)
rename_item(path, new_name)        # SYNO.FileStation.Rename
delete_item(path)                  # SYNO.FileStation.Delete
```

**보안:** 모든 파일 조작은 `_is_within_base_dirs()` 검증을 통과해야 한다. 등록된 기본 디렉토리 범위 밖의 경로 접근은 차단된다.

**연결:** httpx 비동기 클라이언트 사용, SSL 검증 옵션 지원, 업로드 시 120초 타임아웃.

---

### 11.2 ChatService

**파일:** `backend/app/services/chat_service.py` (336줄)

RAG 기반 채팅 오케스트레이션 서비스이다. 쿼리를 분류하여 적절한 핸들러로 라우팅한다.

**쿼리 분류 & 처리 흐름:**
```
사용자 메시지 입력
    │
    ├─ 메타 쿼리? (인사/기능 문의, 5자 이하 짧은 인사)
    │   └─ _handle_meta_query() → META_SYSTEM_PROMPT + META_PROMPT
    │
    ├─ NAS 경로 쿼리? (NAS_KEYWORDS 포함)
    │   └─ _handle_nas_query()
    │       ├─ NASIndexService.search() → 인메모리 인덱스 검색
    │       ├─ 결과 있으면 → NAS_SEARCH_PROMPT_TEMPLATE (경로+크기 포함)
    │       └─ 결과 없으면 → 지식 검색으로 폴백
    │
    └─ 지식 쿼리 (규정)
        └─ _handle_knowledge_query()
            ├─ REGULATIONS_COLLECTION 검색 (top 5)
            ├─ 결과 있으면 → QA_PROMPT_TEMPLATE
            └─ 결과 없으면 → _handle_fallback_query() (FALLBACK_PROMPT)
```

**상수:**
- `MAX_HISTORY_TURNS` = 10 (최근 20개 메시지)
- `NAS_KEYWORDS` = 40+ 키워드 ("파일 위치", "어디에 있", "폴더", "경로", "NAS", ...)
- `META_KEYWORDS` = ("안녕", "반갑", "기능", "도움말", ...)

**주요 메서드:**
```python
async def answer(message, session_id, history) → ChatResponse      # 동기 전체 응답
async def answer_stream(message, session_id, history) → AsyncIterator[str]  # SSE 스트리밍
_search_all_knowledge_raw(message) → list[dict]   # REGULATIONS 검색
_extract_nas_search_query(message) → str           # NAS 검색용 노이즈 제거
_extract_sources(results) → list[SourceReference]  # (document, article_number) 중복 제거
_format_context(results) → str                     # 검색 결과 컨텍스트 포맷
_format_index_results(results) → str               # NAS 인덱스 결과 포맷 (경로+크기)
```

---

### 11.3 NASIndexService

**파일:** `backend/app/services/nas_index_service.py` (189줄)

NAS 파일 인덱스를 주기적으로 갱신하고 인메모리 키워드 검색을 제공한다.

**주기적 스캔:**
```python
start_periodic_scan(interval=3600)  # 1시간 주기 백그라운드 태스크
stop_periodic_scan()                # 태스크 취소
scan_all()                          # 전체 기본 디렉토리 재귀 스캔
_scan_recursive(path, depth=0)      # 깊이 제한 없는 재귀 탐색 (폴더당 최대 2000건)
```

**인메모리 검색:**
```python
search(query, limit=20) → list[dict]
    # 키워드 분리 → OR 매칭
    # 이름 매칭: 2점, 경로 매칭: 1점
    # 점수 내림차순 정렬
```

**인덱스 구조:** 각 항목은 `{name, path, is_dir, size, mtime, extension}`

**상태 속성:**
- `last_scan_time` — 마지막 스캔 시각
- `total_indexed` — 인덱싱된 항목 수
- `is_scanning` — 현재 스캔 중 여부

---

### 11.4 DocumentService

**파일:** `backend/app/services/document_service.py` (204줄)

문서 업로드, 텍스트 추출, 벡터 인덱싱 파이프라인이다.

**핵심 파이프라인 (`upload_and_index`):**
```
1. 파일 저장 (5%)
2. 텍스트 추출 (10%) - file_parser.extract_text()
3. 규정 형식 자동 감지 ("제X조" 패턴 3개 이상?)
4. 텍스트 청킹 (25%) — 규정: chunk_regulation_text() / 일반: chunk_general_text()
5. 배치 임베딩 (30-90%) — 10개씩, 진행률 콜백
6. 벡터 DB 추가 → REGULATIONS_COLLECTION
7. 메타데이터 저장 (95%) → documents_metadata.json
8. 완료 (100%)
```

**파일 위치:** 원본 `{DOCUMENTS_DIR}/`, 추출 텍스트 `{EXTRACTED_DIR}/`, 메타데이터 `documents_metadata.json`

---

### 11.5 UserService

**파일:** `backend/app/services/user_service.py` (119줄)

SQLite 기반 사용자 CRUD: `authenticate`, `list_users`, `create_user`, `update_user`, `reset_password`, `delete_user`. 비밀번호는 bcrypt으로 해싱.

---

## 12. API 엔드포인트 명세

### 12.1 인증 API

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `POST` | `/api/auth/login` | 없음 | 로그인, JWT 토큰 발급 |
| `POST` | `/api/auth/logout` | 필요 | 로그아웃, 쿠키 삭제 |
| `GET` | `/api/auth/me` | 필요 | 현재 사용자 정보 |

### 12.2 채팅 API

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `POST` | `/api/chat` | 사용자 | 동기 채팅 응답 |
| `POST` | `/api/chat/stream` | 사용자 | SSE 스트리밍 채팅 |

**요청:**
```json
{
  "message": "연차 사용 규정이 어떻게 되나요?",
  "session_id": "optional",
  "history": [{"role": "user", "content": "이전 질문"}, {"role": "assistant", "content": "이전 답변"}]
}
```

**동기 응답:**
```json
{
  "answer": "답변 텍스트...",
  "sources": [{"document": "취업규칙.pdf", "article": "제25조(연차유급휴가)", "relevance_score": 0.95}],
  "session_id": "uuid"
}
```

**스트리밍 응답 (SSE):**
```
data: {"token": "연차"}
data: {"token": "유급"}
data: {"token": "휴가는"}
...
data: {"token": "[DONE]"}
```

### 12.3 문서 관리 API

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `POST` | `/api/documents/upload` | 관리자 | 문서 업로드 & 인덱싱 |
| `GET` | `/api/documents/progress/{task_id}` | 없음 | 업로드 진행률 |
| `GET` | `/api/documents` | 관리자 | 문서 목록 |
| `DELETE` | `/api/documents/{doc_id}` | 관리자 | 문서 삭제 |

### 12.4 NAS 탐색 & 파일 관리 API (관리자 전용)

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/api/nas/base-dirs` | 등록된 기본 디렉토리 목록 |
| `POST` | `/api/nas/base-dirs` | 기본 디렉토리 추가 (NAS 존재 검증) |
| `DELETE` | `/api/nas/base-dirs/{dir_id}` | 기본 디렉토리 제거 |
| `POST` | `/api/nas/base-dirs/validate` | NAS 경로 존재 여부 확인 |
| `GET` | `/api/nas/browse?path=&offset=&limit=&sort_by=&sort_direction=` | 디렉토리 탐색 (페이지네이션) |
| `GET` | `/api/nas/search?q=&path=&extension=` | 파일 검색 |
| `GET` | `/api/nas/download?path=` | 파일 다운로드 |
| `GET` | `/api/nas/status` | NAS 연결 상태 확인 |
| `POST` | `/api/nas/folder` | 새 폴더 생성 (folder_path, name) |
| `POST` | `/api/nas/upload` | 파일 업로드 (path, file, overwrite) — 500MB 제한 |
| `POST` | `/api/nas/rename` | 파일/폴더 이름 변경 (path, new_name) |
| `DELETE` | `/api/nas/delete?path=` | 파일/폴더 삭제 |

### 12.5 사용자 관리 API

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `GET` | `/api/admin/users` | 관리자 | 사용자 목록 |
| `POST` | `/api/admin/users` | 관리자 | 사용자 생성 |
| `PUT` | `/api/admin/users/{user_id}/password` | 관리자 | 비밀번호 초기화 |
| `DELETE` | `/api/admin/users/{user_id}` | 관리자 | 사용자 삭제 |

### 12.6 헬스 체크 API

| 메서드 | 경로 | 인증 | 설명 |
|--------|------|------|------|
| `GET` | `/api/health` | 없음 | 시스템 상태 |

**응답:**
```json
{
  "status": "ok",
  "document_count": 5,
  "total_chunks": 374,
  "llm_provider": "ollama",
  "nas_connected": true,
  "nas_base_dir_count": 3
}
```

---

## 13. Pydantic 모델/스키마

**파일:** `backend/app/models/schemas.py` (128줄)

### 채팅 모델
```python
class ChatMessage(BaseModel):
    role: str               # "user" | "assistant"
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
```

### 문서 모델
```python
class DocumentInfo(BaseModel):
    id: str
    filename: str
    uploaded_at: str
    total_chunks: int
    status: str             # "indexed" | "processing" | "error"
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
```

### NAS 모델 (Synology)
```python
class BaseDirectory(BaseModel):
    id: str
    path: str
    label: str
    description: str = ""
    created_at: str = ""

class BaseDirectoryRequest(BaseModel):
    path: str
    label: str = ""
    description: str = ""

class NASItem(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: int = 0
    modified_time: str = ""
    extension: str = ""

class NASDirectoryListing(BaseModel):
    current_path: str
    parent_path: str = ""
    breadcrumbs: list[dict] = []
    items: list[NASItem] = []
    total: int = 0
    offset: int = 0

class NASSearchResponse(BaseModel):
    query: str
    results: list[NASItem] = []
    total_count: int = 0
```

### 시스템 모델
```python
class HealthResponse(BaseModel):
    status: str
    document_count: int
    total_chunks: int
    llm_provider: str
```

---

## 14. 유틸리티

### 14.1 파일 파서 (`utils/file_parser.py`)

**파일:** `backend/app/utils/file_parser.py` (227줄)

30+ 포맷의 텍스트 추출을 지원한다.

| 카테고리 | 확장자 | 추출 방식 |
|----------|--------|----------|
| Office | PDF | PyMuPDF (fitz) |
| | DOCX | python-docx (단락 + 표 셀) |
| | XLSX | openpyxl (시트별, 파이프 구분) |
| | PPTX | python-pptx (슬라이드별) |
| | HWPX | ZIP 압축 해제 → XML 파싱 |
| 텍스트 | TXT, MD, CSV, JSON, LOG | 직접 디코딩 |
| 웹 | XML, HTML, HTM | 태그 제거 |
| 코드 | PY, JS, TS, JAVA, C, CPP, etc. | 직접 디코딩 |
| 설정 | YAML, YML, TOML, INI, CFG | 직접 디코딩 |

**텍스트 인코딩 순서:** UTF-8 → CP949 → EUC-KR → Latin-1

---

### 14.2 텍스트 청커 (`utils/text_chunker.py`)

**파일:** `backend/app/utils/text_chunker.py` (229줄)

한국어 규정 문서에 최적화된 스마트 청킹 시스템이다.

**정규식 패턴:**
```python
CHAPTER_PATTERN = r"^제\s*(\d+)\s*장\s+(.+)$"            # 제1장 총칙
ARTICLE_PATTERN = r"^제\s*(\d+)\s*조\s*[\(（](.+?)[\)）]"  # 제25조(연차유급휴가)
PARAGRAPH_PATTERN = r"^[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮]"       # ① ...
```

**청킹 전략 2종:**

**1. 규정 문서 (`chunk_regulation_text`)** — 3단계 계층 분할:
```
Level 1: 조항별 분할 (제X조)
    ├─ 크기 ≤ max_size → 하나의 청크
    └─ 크기 > max_size
        ├─ Level 2: 항별 분할 (①②③)
        └─ Level 3: 고정 크기 분할 (문장 경계, 오버랩)
```

**2. 일반 문서 (`chunk_general_text`)** — 문단 기반: 이중 줄바꿈 분리 → 병합 → 큰 문단은 고정 크기 분할

---

### 14.3 한국어 유틸리티 (`utils/korean_utils.py`)

```python
normalize_korean_text(text) → str     # NFC 정규화, 공백/빈줄 축소
is_header_or_footer(line) → bool      # 페이지 번호, 반복 제목 감지
clean_extracted_text(text) → str      # 헤더/푸터 제거 + 정규화
```

---

### 14.4 PDF 파서 (`utils/pdf_parser.py`)

```python
extract_pdf_text(file_path) → list[dict]  # 페이지별 추출 (page_number, text, metadata)
extract_full_text(file_path) → str         # 전체 텍스트 추출 (페이지 간 \n\n)
```

---

## 15. 프론트엔드 아키텍처

### 15.1 템플릿 상속 구조

```
base.html (베이스: 헤더 + 내비게이션)
├── chat.html (채팅 페이지)
├── nas.html (NAS 파일 탐색 — 관리자 전용)
├── admin.html (관리자 패널)
└── login.html (로그인 - 헤더 숨김)
```

### 15.2 JavaScript 모듈

| 파일 | 줄 수 | 주요 기능 |
|------|-------|----------|
| `auth.js` | 49줄 | 인증 확인 (`checkAuth`), 역할 기반 UI (`.admin-only` 토글), 로그아웃 |
| `chat.js` | 247줄 | SSE 스트리밍, Markdown 렌더링 (marked.js), 대화 히스토리, 한국어 IME 처리, 폴백 |
| `nas.js` | 592줄 | 그리드/리스트 뷰, 브레드크럼, 컨텍스트 메뉴 (우클릭), 파일 업로드/삭제/이름변경/폴더 생성, 파일 타입별 SVG 아이콘 |
| `admin.js` | 645줄 | 시스템 상태, 문서/사용자/NAS 관리, 업로드 ETA 표시, 페이지네이션 (10건 단위, 스마트 페이지 번호) |

### 15.3 CSS 디자인 시스템

**CSS 변수:** `--primary: #2563eb`, `--bg: #f8fafc`, `--success: #22c55e`, `--error: #ef4444`, `--warning: #f59e0b`

**폰트:** Pretendard, 시스템 sans-serif 스택

**주요 컴포넌트:**
- 헤더 (56px, 고정): 로고 + 아이콘 내비게이션 + 사용자 정보
- 채팅: 메시지 버블 (사용자: 파란색, AI: 흰색), 타이핑 인디케이터, 제안 칩
- NAS: 파일 그리드/리스트 뷰, 브레드크럼, 컨텍스트 메뉴, 업로드 모달
- 관리: 섹션 카드, 상태 그리드, 테이블, 페이지네이션
- 모달: backdrop-filter blur, scale 애니메이션
- 알림 토스트: 슬라이드 업 애니메이션

**반응형:** `@media (max-width: 768px)` — 모바일 최적화 (단일 컬럼 레이아웃, 아이콘 숨김)

**외부 의존성:** `marked.min.js` (CDN) — Markdown 파서

---

## 16. 인증 및 권한 시스템

### 인증 플로우

```
1. POST /api/auth/login {username, password}
2. UserService.authenticate() → bcrypt 비밀번호 검증
3. JWT 생성: jwt.encode({user_id, username, role}, SECRET_KEY, HS256)
4. httpOnly 쿠키 설정: auth_token=JWT, max_age=86400(24시간), samesite=lax
5. 응답: {success, token, user: {username, display_name, role}}

이후 요청: 쿠키 자동 전송 → get_current_user() → jwt.decode() 검증
로그아웃: POST /api/auth/logout → 쿠키 삭제
```

### 역할 기반 접근 제어 (RBAC)

| 역할 | API 권한 | UI 접근 |
|------|----------|---------|
| `admin` | 문서 업로드/삭제, NAS 탐색/관리, 사용자 관리, 시스템 상태 | 채팅, NAS 탐색, 관리 |
| `user` | 채팅 (규정 질의 + NAS 경로 질문) | 채팅만 |

**프론트엔드 권한 처리:**
- `auth.js`의 `updateNavForRole()` — `.admin-only` CSS 클래스로 내비게이션 링크 숨김/표시
- `nas.js` — 초기화 시 `checkAuth()` → admin이 아니면 `/`로 리다이렉트
- `admin.js` — 초기화 시 `checkAuth()` → admin이 아니면 `/`로 리다이렉트

---

## 17. 데이터 흐름

### 채팅 흐름

```
사용자 메시지 → POST /api/chat/stream
                    │
            ChatService.answer_stream()
                    │
            ┌── 쿼리 분류 ──┐
            │               │
    ┌───────┼───────────────┼───────┐
    │       │               │       │
 메타 쿼리  NAS 쿼리     지식 쿼리   │
    │       │               │       │
META_PROMPT NASIndex    REGULATIONS │
    │    .search()     검색(top 5)  │
    │   (인메모리)          │       │
    │       │               │       │
    │   NAS_SEARCH     QA_PROMPT    │
    │    _PROMPT            │       │
    └───────┴───────┬───────┘       │
                    │       결과 없음
            LLM.generate_stream()   │
                    │          FALLBACK_PROMPT
            SSE 토큰 스트리밍       │
            ChatResponse       ChatResponse
         {answer, sources}     {answer만}
```

### 문서 업로드 흐름

```
파일 업로드 → POST /api/documents/upload
    │
    ├── 파일 저장 (5%)
    ├── 텍스트 추출 (10%)        ← file_parser.extract_text()
    ├── 규정 형식 감지            ← "제X조" 패턴 3개 이상?
    ├── 텍스트 청킹 (25%)        ← chunk_regulation/general_text()
    ├── 배치 임베딩 (30-90%)     ← 10개씩, 진행률 콜백
    ├── 벡터 DB 저장              ← REGULATIONS_COLLECTION
    ├── 메타데이터 저장 (95%)
    └── 완료 (100%)

프론트엔드: GET /api/documents/progress/{taskId} (500ms 폴링, ETA 계산)
```

### NAS 파일 인덱싱 흐름

```
앱 시작 → NASIndexService.start_periodic_scan(interval=3600)
    │
    └── 1시간 주기 반복
        ├── SynologyService.list_base_dirs() → 등록된 디렉토리 목록
        ├── 각 디렉토리별 재귀 스캔 (_scan_recursive)
        │   ├── SynologyService.list_directory()
        │   └── 하위 폴더 재귀 (폴더당 최대 2000건)
        └── 인메모리 인덱스 갱신 [{name, path, is_dir, size, mtime, extension}]

채팅에서 NAS 쿼리 감지 시:
    → NASIndexService.search(query) → 인메모리 키워드 매칭
    → 결과를 NAS_SEARCH_PROMPT_TEMPLATE에 전달 → LLM 답변
```

---

# Part 3. 부록

---

## 부록 A. 환경변수 레퍼런스

| 변수 | 기본값 | 설명 |
|------|--------|------|
| **LLM 설정** | | |
| `LLM_PROVIDER` | `ollama` | LLM 프로바이더: openai / claude / gemini / ollama |
| `LLM_TEMPERATURE` | `0.3` | 생성 온도 (0=일관성, 1=창의성) |
| `LLM_MAX_TOKENS` | `1024` | 최대 출력 토큰 |
| `OPENAI_API_KEY` | `""` | OpenAI API 키 |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI 모델명 |
| `ANTHROPIC_API_KEY` | `""` | Anthropic API 키 |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Claude 모델명 |
| `GEMINI_API_KEY` | `""` | Google Gemini API 키 |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini 모델명 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 URL |
| `OLLAMA_MODEL` | `gemma3:4b` | Ollama 모델명 |
| **임베딩 설정** | | |
| `EMBEDDING_PROVIDER` | `ollama` | 임베딩 프로바이더: openai / ollama |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI 임베딩 모델 (1536차원) |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama 임베딩 모델 |
| **RAG 설정** | | |
| `CHUNK_SIZE` | `800` | 문서 분할 크기 (문자 수) |
| `CHUNK_OVERLAP` | `100` | 청크 겹침 크기 |
| `RETRIEVAL_TOP_K` | `5` | 검색 결과 수 |
| `SIMILARITY_THRESHOLD` | `0.3` | 최소 유사도 임계값 |
| **Synology NAS** | | |
| `SYNOLOGY_URL` | `""` | Synology NAS URL (예: `https://nas.example.com:5001`) |
| `SYNOLOGY_USERNAME` | `""` | NAS 로그인 아이디 |
| `SYNOLOGY_PASSWORD` | `""` | NAS 로그인 비밀번호 |
| `SYNOLOGY_VERIFY_SSL` | `false` | SSL 인증서 검증 여부 |
| **기타 설정** | | |
| `MAX_UPLOAD_SIZE_MB` | `200` | 문서 최대 업로드 크기 (MB) |
| `ADMIN_PASSWORD` | `admin1234` | 관리자 초기 비밀번호 (⚠️ 반드시 변경) |
| `SECRET_KEY` | `change-this-...` | JWT 서명 키 (⚠️ 반드시 변경) |
| `APP_PORT` | `8080` | 외부 접근 포트 (Docker) |
| `LOG_LEVEL` | `INFO` | 로깅 레벨: DEBUG / INFO / WARNING / ERROR |

---

## 부록 B. 데이터 디렉토리 구조

```
data/
├── chromadb/                           # ChromaDB 벡터 데이터베이스
│   ├── chroma.sqlite3                  # 메인 SQLite (메타데이터)
│   └── {uuid}/                         # HNSW 인덱스 디렉토리
│       ├── data_level0.bin             # 벡터 데이터
│       ├── header.bin
│       ├── length.bin
│       └── link_lists.bin
│
├── documents/                          # 업로드된 원본 문서
│   ├── *.pdf, *.docx, ...             # 원본 파일
│   └── documents_metadata.json         # 문서 메타데이터
│
├── extracted/                          # 추출된 텍스트 캐시
│   └── *.txt                          # 문서별 추출 텍스트
│
├── nas/                                # NAS 관련 데이터
│   └── base_dirs.json                  # 등록된 기본 디렉토리 목록
│
└── users.db                            # SQLite 사용자 DB
```

**Docker 볼륨:** `chatbot_data:/app/data` (영구 저장)

---

## 부록 C. 배포 및 인프라 상세

### Docker 멀티스테이지 빌드

| 스테이지 | 베이스 이미지 | 용도 |
|----------|-------------|------|
| Base | python:3.11-slim | 공통 환경 설정 |
| Builder | Base | 가상환경 생성 + 의존성 설치 |
| Production | Base | 최소 이미지 + 앱 코드 |

- 비루트 사용자 `appuser`로 실행
- 헬스 체크: `curl http://localhost:8000/api/health` (30초 간격)
- 포트: 8000 (내부), 8080 (외부 기본)

### Docker Compose 구성

**docker-compose.yml (메인):**
```yaml
services:
  app:
    build: {context: ., target: production}
    container_name: st-youngwon-chatbot
    ports: ["${APP_PORT:-8080}:8000"]
    volumes: [chatbot_data:/app/data]
    environment:
      - LLM_PROVIDER, OPENAI_API_KEY, ANTHROPIC_API_KEY, ...
      - SYNOLOGY_URL, SYNOLOGY_USERNAME, SYNOLOGY_PASSWORD, ...
      - ADMIN_PASSWORD, SECRET_KEY, LOG_LEVEL
    restart: unless-stopped
    mem_limit: 1g
    cpus: 2.0
```

**docker-compose.ollama.yml (확장):**
```yaml
services:
  ollama:
    image: ollama/ollama:latest
    container_name: st-youngwon-ollama
    ports: ["11434:11434"]
    volumes: [ollama_data:/root/.ollama]
    mem_limit: 4g
    cpus: 4.0
  app:
    depends_on: [ollama]
    environment:
      - LLM_PROVIDER=ollama
      - EMBEDDING_PROVIDER=ollama
      - OLLAMA_BASE_URL=http://ollama:11434
```

### Makefile 명령어

```makefile
make up              # docker compose up -d
make down            # docker compose down
make logs            # docker compose logs -f app
make build           # docker compose build --no-cache
make seed            # docker compose exec app python scripts/seed_documents.py
make dev             # uvicorn --reload --host 0.0.0.0 --port 8000
make test            # pytest backend/tests/ -v
make clean           # 컨테이너/볼륨/데이터 모두 삭제 (주의!)
make up-ollama       # Ollama 포함 시작
make down-ollama     # Ollama 포함 종료
make up-gemini       # Gemini 프로바이더로 시작
```

### 로컬 개발 환경

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=$(pwd)
make dev  # uvicorn --reload → http://localhost:8000
```

---

## 부록 D. 아키텍처 패턴 및 설계 원칙

| 패턴 | 설명 |
|------|------|
| **싱글톤 DI** | 서비스는 한 번만 인스턴스화되어 모든 요청에서 재사용 |
| **비동기 우선** | 모든 I/O 비동기 처리, 무거운 작업은 `asyncio.to_thread()` |
| **진행률 추적** | 스레드 안전 전역 딕셔너리 + 잠금, 500ms 폴링, 3초 후 자동 정리 |
| **하이브리드 검색** | 키워드 1차(가중 0.7) + 벡터 2차 보충(가중 0.3) |
| **쿼리 분류** | 메타/NAS/지식 3종으로 분류 → 각각 다른 프롬프트/컨텍스트 |
| **스마트 청킹** | 규정: 조항→항→고정크기 3단계 / 일반: 문단 기반 |
| **Protocol 추상화** | LLM/임베딩을 Python Protocol로 추상화, 새 프로바이더 추가 용이 |
| **인메모리 인덱스** | NAS 파일 인덱스는 1시간 주기로 갱신, 검색은 인메모리 키워드 매칭 |
| **보안 경계** | NAS 모든 조작은 등록된 기본 디렉토리 내로 제한 |

**성능 특성:**
- 임베딩 배치: 10문서/API 호출
- Ollama 타임아웃: 배치 300초, 개별 120초
- 벡터 검색: 코사인 거리, HNSW 인덱스
- NAS 인덱스: 인메모리, 폴더당 최대 2000건
- Docker 메모리: App 1GB, Ollama 4GB

---

## 부록 E. 확장 가이드

### 새 LLM 프로바이더 추가
1. `core/llm_provider.py`에 `LLMProvider` Protocol 구현 클래스 작성
2. `generate()`, `generate_stream()` 메서드 구현
3. `create_llm_provider()` 팩토리에 case 추가
4. `config.py`에 환경변수 추가 → `.env.example` → `docker-compose.yml`

### 새 임베딩 프로바이더 추가
1. `core/embeddings.py`에 `encode()` + `dimension` 프로퍼티 구현
2. `create_embedding_provider()` 팩토리에 추가
3. `config.py` 업데이트

### 새 문서 포맷 지원
1. `utils/file_parser.py`의 `EXTRACTABLE_EXTENSIONS`에 확장자 추가
2. `_extract_<format>()` 추출 함수 작성
3. `extract_text()`에 라우팅 추가

### 새 API 엔드포인트 추가
1. `api/*.py`에 라우트 핸들러 작성
2. `api/router.py`에 라우터 등록
3. `models/schemas.py`에 요청/응답 모델 정의
4. 서비스 의존성 주입 연결

### 개발 규칙
- 한국어 UI/UX 유지
- 모든 API는 `/api/` 접두사
- Pydantic으로 요청/응답 검증
- 비동기 함수 우선 사용
- 설정 추가 순서: `config.py` → `.env.example` → `docker-compose.yml`

---

## 부록 F. 보안 고려사항

### 프로덕션 필수 조치

1. `ADMIN_PASSWORD`를 "admin1234"에서 강력한 비밀번호로 변경
2. `SECRET_KEY`를 기본값에서 무작위 문자열로 변경
3. HTTPS/TLS 적용
4. CORS 정책 강화
5. 파일 업로드 검증 (확장자 + MIME 타입)
6. 민감 엔드포인트 레이트 리밋
7. 정기 보안 감사
8. Synology NAS 계정 권한 최소화 (필요한 공유 폴더만 접근)

### 현재 구현된 보안 기능

| 기능 | 구현 방식 |
|------|----------|
| 비밀번호 해싱 | bcrypt (gensalt) |
| 토큰 인증 | JWT HS256 |
| NAS 경로 제한 | `_is_within_base_dirs()` — 등록된 기본 디렉토리 내로 제한 |
| 관리자 전용 엔드포인트 | `verify_admin()` 의존성 |
| NAS 탐색 접근 제어 | 관리자만 NAS 탐색 페이지 접근 가능 |
| 쿠키 보안 | httpOnly, samesite=lax |
| XSS 방지 (프론트엔드) | `escapeHtml()`, `escapeAttr()` 함수 |
| 비루트 실행 (Docker) | appuser 사용자 |
| 헬스 체크 | Docker HEALTHCHECK |
| 한국어 IME 처리 | `isComposing` + `keyCode === 229` 체크 (입력 중복 방지) |

---

## 부록 G. 운영 관리

### 로그 확인
```bash
make logs                   # Docker 로그 실시간
docker compose logs -f app  # 동일
```

### 데이터 백업
```bash
docker compose cp app:/app/data ./backup_data
```

### 서비스 재시작
```bash
make down && make up        # 전체 재시작
docker compose restart app  # 앱만 재시작
```

### 이미지 재빌드 (코드 변경 후)
```bash
make build                  # 캐시 없이 재빌드
docker compose up -d        # 새 이미지로 시작
```

### 전체 초기화 (주의: 모든 데이터 삭제)
```bash
make clean
# 컨테이너, 볼륨, data/chromadb/*, data/extracted/*, data/documents/* 모두 삭제
```

---

## 부록 H. API 직접 사용 (cURL)

Swagger UI에서 모든 API를 테스트할 수 있다:
- **Swagger UI:** `http://localhost:8080/docs`
- **ReDoc:** `http://localhost:8080/redoc`

```bash
# 로그인
curl -X POST http://localhost:8080/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin1234"}' \
  -c cookies.txt

# 채팅 (동기)
curl -X POST http://localhost:8080/api/chat \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "연차 규정 알려줘", "history": []}'

# 채팅 (스트리밍)
curl -X POST http://localhost:8080/api/chat/stream \
  -H "Content-Type: application/json" \
  -b cookies.txt \
  -d '{"message": "출퇴근 시간은?", "history": []}' \
  --no-buffer

# 문서 업로드
curl -X POST http://localhost:8080/api/documents/upload \
  -b cookies.txt \
  -F "file=@취업규칙.pdf" \
  -F "task_id=upload_001"

# NAS 디렉토리 탐색
curl "http://localhost:8080/api/nas/browse?path=/인사팀&offset=0&limit=100" \
  -b cookies.txt

# NAS 파일 검색
curl "http://localhost:8080/api/nas/search?q=취업규칙&path=" \
  -b cookies.txt

# 헬스 체크
curl http://localhost:8080/api/health
```

---

## 부록 I. 스크립트

### seed_documents.py

프로젝트 루트와 `data/documents/` 디렉토리의 PDF 파일을 찾아 벡터 스토어에 인덱싱한다.

```bash
python scripts/seed_documents.py
# 또는
make seed
```
