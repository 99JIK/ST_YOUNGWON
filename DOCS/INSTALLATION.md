# ST영원 스마트 오피스 — 설치 및 운용 가이드

## 목차

1. [시스템 요구사항](#1-시스템-요구사항)
2. [프로젝트 구조](#2-프로젝트-구조)
3. [환경변수 설정](#3-환경변수-설정)
4. [설치 방법](#4-설치-방법)
   - [방법 A: Docker (프로덕션 권장)](#방법-a-docker-프로덕션-권장)
   - [방법 B: Docker + Ollama (로컬 LLM)](#방법-b-docker--ollama-로컬-llm)
   - [방법 C: 직접 실행 (개발용)](#방법-c-직접-실행-개발용)
5. [Synology NAS 배포](#5-synology-nas-배포)
6. [초기 설정](#6-초기-설정)
7. [기능별 사용법](#7-기능별-사용법)
8. [관리자 운용 가이드](#8-관리자-운용-가이드)
9. [LLM 프로바이더 설정](#9-llm-프로바이더-설정)
10. [트러블슈팅](#10-트러블슈팅)
11. [업데이트 방법](#11-업데이트-방법)
12. [백업 및 복구](#12-백업-및-복구)

---

## 1. 시스템 요구사항

### 최소 사양 (Docker 배포)

| 항목 | 최소 | 권장 |
|------|------|------|
| CPU | 2코어 | 4코어 이상 |
| RAM | 1GB | 2GB 이상 |
| 디스크 | 2GB | 10GB 이상 |
| Docker | 20.10+ | 최신 버전 |
| Docker Compose | v2.0+ | 최신 버전 |

### Ollama 사용 시 추가 요구사항

| 항목 | 최소 | 권장 |
|------|------|------|
| RAM | 4GB 추가 | 8GB 추가 |
| GPU | 없어도 동작 (느림) | NVIDIA GPU (VRAM 4GB+) |

### 직접 실행 시

- Python 3.11+
- pip 또는 venv

---

## 2. 프로젝트 구조

```
ST_YOUNGWON/
├── backend/
│   └── app/
│       ├── api/                    # API 라우터
│       │   ├── router.py           # 라우터 통합
│       │   ├── chat.py             # 채팅 API (RAG 질의응답)
│       │   ├── documents.py        # 문서 업로드/관리 API
│       │   ├── nas_browser.py      # NAS 탐색/다운로드/업로드 API
│       │   ├── users.py            # 사용자 관리 API (관리자용)
│       │   └── health.py           # 헬스체크 API
│       ├── core/
│       │   ├── llm_provider.py     # LLM 프로바이더 팩토리
│       │   ├── prompts.py          # 시스템/질의 프롬프트 정의
│       │   └── vectorstore.py      # ChromaDB 벡터스토어
│       ├── services/
│       │   ├── chat_service.py     # RAG 챗봇 서비스 (NAS+규정 통합 검색)
│       │   ├── document_service.py # 문서 파싱/인덱싱 서비스
│       │   ├── synology_service.py # Synology FileStation API 클라이언트
│       │   ├── nas_index_service.py# NAS 파일 인덱스 (주기적 스캔)
│       │   └── user_service.py     # 사용자 CRUD
│       ├── models/
│       │   └── schemas.py          # Pydantic 요청/응답 스키마
│       ├── utils/                  # 파일 파싱, 텍스트 청킹 유틸
│       ├── config.py               # 환경변수 설정 (Pydantic Settings)
│       ├── database.py             # SQLite DB 초기화
│       ├── dependencies.py         # FastAPI 의존성 주입 + 인증
│       └── main.py                 # FastAPI 엔트리포인트
│   └── requirements.txt
├── frontend/
│   ├── templates/                  # Jinja2 HTML 템플릿
│   │   ├── base.html               # 공통 레이아웃 (헤더, 네비게이션)
│   │   ├── login.html              # 로그인 페이지
│   │   ├── chat.html               # 채팅 페이지
│   │   ├── nas.html                # NAS 탐색 페이지
│   │   └── admin.html              # 관리자 페이지
│   └── static/
│       ├── css/style.css           # 전체 스타일시트
│       ├── js/
│       │   ├── auth.js             # 인증 공통 로직
│       │   ├── chat.js             # 채팅 UI 로직
│       │   ├── nas.js              # NAS 탐색 UI 로직
│       │   └── admin.js            # 관리자 페이지 로직
│       └── img/favicon.png
├── config/
│   └── settings.yaml               # 설정 레퍼런스
├── scripts/
│   └── seed_documents.py           # 문서 초기 인덱싱 스크립트
├── data/                           # 영구 데이터 (Docker 볼륨)
│   ├── documents/                  # 업로드된 원본 문서
│   ├── extracted/                  # 파싱된 텍스트
│   ├── chromadb/                   # 벡터DB 데이터
│   ├── nas/                        # NAS 기본 디렉토리 설정
│   └── users.db                    # SQLite 사용자 DB
├── docker-compose.yml              # Docker 프로덕션 설정
├── docker-compose.ollama.yml       # Ollama 추가 설정
├── Dockerfile                      # 멀티스테이지 빌드
├── Makefile                        # 편의 명령어
├── .env.example                    # 환경변수 템플릿
└── CLAUDE.md                       # 프로젝트 메타 정보
```

---

## 3. 환경변수 설정

### 3.1. `.env` 파일 생성

```bash
cp .env.example .env
```

### 3.2. 필수 설정

```env
# === 반드시 변경 ===
ADMIN_PASSWORD=your-secure-password     # 초기 관리자 비밀번호
SECRET_KEY=random-32-char-string-here   # JWT 서명 키 (랜덤 문자열)

# === LLM 설정 (하나 선택) ===
LLM_PROVIDER=ollama                     # openai / claude / gemini / ollama
```

### 3.3. LLM 프로바이더별 설정

#### OpenAI

```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini
EMBEDDING_PROVIDER=openai
```

#### Anthropic Claude

```env
LLM_PROVIDER=claude
ANTHROPIC_API_KEY=sk-ant-...
ANTHROPIC_MODEL=claude-3-5-haiku-20241022
EMBEDDING_PROVIDER=openai          # Claude는 임베딩 미지원, OpenAI 사용
OPENAI_API_KEY=sk-...              # 임베딩용
```

#### Google Gemini

```env
LLM_PROVIDER=gemini
GEMINI_API_KEY=AI...
GEMINI_MODEL=gemini-2.0-flash
EMBEDDING_PROVIDER=openai          # Gemini 임베딩 미지원
OPENAI_API_KEY=sk-...
```

#### Ollama (로컬 LLM, 무료)

```env
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434   # Docker 내부: http://ollama:11434
OLLAMA_MODEL=gemma3:4b
EMBEDDING_PROVIDER=ollama
OLLAMA_EMBEDDING_MODEL=nomic-embed-text
```

### 3.4. Synology NAS 설정

```env
SYNOLOGY_URL=http://192.168.1.100:5000   # NAS 주소 (DSM 포트)
SYNOLOGY_USERNAME=your-nas-username       # FileStation 접근 권한 필요
SYNOLOGY_PASSWORD=your-nas-password
SYNOLOGY_VERIFY_SSL=false                 # 자체 서명 SSL이면 false
```

> **Docker 환경 주의**: 컨테이너 안에서 `localhost`는 자기 자신입니다.
> NAS와 같은 서버에 Docker를 돌린다면 NAS의 실제 IP를 사용하세요.
> 예: `SYNOLOGY_URL=http://155.230.34.136:5000`

### 3.5. 전체 환경변수 목록

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `LLM_PROVIDER` | `ollama` | LLM 프로바이더 (openai/claude/gemini/ollama) |
| `OPENAI_API_KEY` | (없음) | OpenAI API 키 |
| `OPENAI_MODEL` | `gpt-4o-mini` | OpenAI 모델 |
| `ANTHROPIC_API_KEY` | (없음) | Anthropic API 키 |
| `ANTHROPIC_MODEL` | `claude-3-5-haiku-20241022` | Claude 모델 |
| `GEMINI_API_KEY` | (없음) | Google Gemini API 키 |
| `GEMINI_MODEL` | `gemini-2.0-flash` | Gemini 모델 |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama 서버 주소 |
| `OLLAMA_MODEL` | `gemma3:4b` | Ollama LLM 모델 |
| `LLM_TEMPERATURE` | `0.3` | 응답 다양성 (0~1) |
| `LLM_MAX_TOKENS` | `1024` | 최대 응답 토큰 수 |
| `EMBEDDING_PROVIDER` | `ollama` | 임베딩 프로바이더 (openai/ollama) |
| `EMBEDDING_MODEL` | `text-embedding-3-small` | OpenAI 임베딩 모델 |
| `OLLAMA_EMBEDDING_MODEL` | `nomic-embed-text` | Ollama 임베딩 모델 |
| `CHUNK_SIZE` | `800` | 문서 분할 크기 (토큰) |
| `CHUNK_OVERLAP` | `100` | 청크 간 겹침 |
| `RETRIEVAL_TOP_K` | `5` | 검색 결과 개수 |
| `SIMILARITY_THRESHOLD` | `0.3` | 유사도 임계값 |
| `MAX_UPLOAD_SIZE_MB` | `200` | 최대 업로드 크기 (MB) |
| `SYNOLOGY_URL` | (없음) | NAS 주소 |
| `SYNOLOGY_USERNAME` | (없음) | NAS 계정 |
| `SYNOLOGY_PASSWORD` | (없음) | NAS 비밀번호 |
| `SYNOLOGY_VERIFY_SSL` | `false` | NAS SSL 인증서 검증 |
| `ADMIN_PASSWORD` | `admin1234` | 초기 관리자 비밀번호 |
| `SECRET_KEY` | (변경 필요) | JWT 서명 키 |
| `APP_PORT` | `8080` | Docker 외부 포트 |
| `LOG_LEVEL` | `INFO` | 로그 레벨 (DEBUG/INFO/WARNING/ERROR) |

---

## 4. 설치 방법

### 방법 A: Docker (프로덕션 권장)

외부 LLM API (OpenAI, Gemini 등)를 사용하는 경우 가장 간단합니다.

```bash
# 1. 저장소 클론
git clone https://github.com/99JIK/ST_YOUNGWON.git
cd ST_YOUNGWON

# 2. 환경변수 설정
cp .env.example .env
# .env 파일을 열어서 값 수정 (필수: ADMIN_PASSWORD, SECRET_KEY, LLM 설정)

# 3. Docker 빌드 & 실행
docker compose up -d --build

# 4. 접속 확인
# http://localhost:8080 (또는 APP_PORT에 설정한 포트)
```

### 방법 B: Docker + Ollama (로컬 LLM)

GPU가 있는 서버에서 무료로 LLM을 돌릴 때 사용합니다.

```bash
# 1. 저장소 클론 & 환경변수 설정
git clone https://github.com/99JIK/ST_YOUNGWON.git
cd ST_YOUNGWON
cp .env.example .env
# .env에서 LLM_PROVIDER=ollama 확인

# 2. Ollama 포함 실행
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build

# 3. 모델 다운로드 (최초 1회)
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama pull nomic-embed-text

# 4. 접속 확인
# http://localhost:8080
```

#### 외부 PC의 Ollama 사용 (이미 Ollama가 설치된 PC가 있는 경우)

```bash
# 외부 PC에서 Ollama를 외부 접속 허용으로 실행
OLLAMA_HOST=0.0.0.0 ollama serve

# .env에 외부 PC IP 설정
OLLAMA_BASE_URL=http://192.168.1.50:11434

# Docker 실행 (Ollama 컨테이너 불필요)
docker compose up -d --build
```

### 방법 C: 직접 실행 (개발용)

Docker 없이 로컬에서 직접 실행합니다.

```bash
# 1. 저장소 클론
git clone https://github.com/99JIK/ST_YOUNGWON.git
cd ST_YOUNGWON

# 2. 가상환경 생성 & 패키지 설치
python -m venv venv

# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

pip install -r backend/requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일 수정

# 4. 실행
# Windows
set PYTHONPATH=%cd%
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# Linux/Mac
PYTHONPATH=$(pwd) uvicorn backend.app.main:app --host 0.0.0.0 --port 8000 --reload

# 5. 접속
# http://localhost:8000
```

---

## 5. Synology NAS 배포

NAS에서 Docker로 서비스를 운영하는 경우입니다.

### 5.1. 사전 준비

1. NAS에서 **Docker 패키지** 설치 (패키지 센터)
2. NAS에서 **SSH 서비스** 활성화 (제어판 → 터미널 및 SNMP)
3. NAS에 **git** 설치 (패키지 센터 또는 수동)

### 5.2. 배포 절차

```bash
# 1. SSH로 NAS에 접속
ssh your-user@nas-ip

# 2. 프로젝트 디렉토리 생성 & 클론
sudo mkdir -p /volume1/chatbot
cd /volume1/chatbot
sudo git clone https://github.com/99JIK/ST_YOUNGWON.git
cd ST_YOUNGWON

# 3. git safe directory 설정 (ownership 문제 방지)
sudo git config --global --add safe.directory /volume1/chatbot/ST_YOUNGWON

# 4. 환경변수 설정
sudo cp .env.example .env
sudo vi .env
# 주요 설정:
#   SYNOLOGY_URL=http://<NAS_내부_IP>:5000
#   SYNOLOGY_USERNAME=your-nas-account
#   SYNOLOGY_PASSWORD=your-nas-password
#   ADMIN_PASSWORD=secure-password
#   SECRET_KEY=random-string
#   LLM_PROVIDER=gemini  (NAS는 GPU가 없으므로 외부 API 권장)
#   GEMINI_API_KEY=AI...

# 5. Docker 빌드 & 실행
sudo docker compose up -d --build

# 6. 접속 확인
curl http://localhost:8080/api/health
```

### 5.3. NAS Docker 네트워크 주의사항

Docker 컨테이너 내부에서 NAS 자체에 접속할 때:

- `localhost`는 **컨테이너 자신**을 가리킴
- NAS의 **실제 IP 주소**를 사용해야 함
- 예: `SYNOLOGY_URL=http://155.230.34.136:5000`

### 5.4. 자동 시작

`docker-compose.yml`에 `restart: unless-stopped`가 설정되어 있으므로:

- NAS 재부팅 → Docker 자동 시작 → 컨테이너 자동 실행
- `docker compose stop`으로 수동 중지하면 자동 시작 안 됨
- `docker compose down` 후 `up`하면 다시 자동 시작 활성화

---

## 6. 초기 설정

### 6.1. 첫 로그인

1. 브라우저에서 서비스 주소 접속 (예: `http://nas-ip:8080`)
2. 로그인 화면에서:
   - **아이디**: `admin`
   - **비밀번호**: `.env`의 `ADMIN_PASSWORD` 값 (기본값: `admin1234`)
3. 로그인 성공 후 **관리** 페이지로 이동

### 6.2. 관리자 비밀번호 변경

1. **관리** 페이지 → 사용자 관리 섹션
2. admin 행의 **비밀번호 변경** 버튼 클릭
3. 현재 비밀번호 입력 → 새 비밀번호 입력 → 확인

> **주의**: `.env`의 `ADMIN_PASSWORD`는 **최초 DB 생성 시에만 사용**됩니다.
> 이후 비밀번호를 변경하면 `.env` 값과 무관합니다.
> DB를 삭제하면(`data/users.db`) 다시 `.env` 값으로 초기화됩니다.

### 6.3. NAS 기본 디렉토리 등록

NAS 파일 탐색을 위해 탐색 가능한 디렉토리를 등록해야 합니다.

1. **관리** 페이지 → NAS 기본 디렉토리 관리 섹션
2. **NAS 경로** 입력 (예: `/공유폴더`)
3. **표시 이름** 입력 (예: `공유폴더`)
4. **경로 확인** 버튼으로 NAS에 실제 존재하는지 검증
5. **추가** 버튼 클릭

> 등록하지 않은 경로는 NAS 탐색 및 챗봇 파일 검색에서 접근할 수 없습니다.

### 6.4. 문서 업로드 (RAG 용)

챗봇이 답변할 수 있는 규정/사내문서를 업로드합니다.

1. **관리** 페이지 → 문서 업로드 섹션
2. 파일을 드래그하거나 클릭하여 업로드
3. 지원 형식: PDF, DOCX, XLSX, PPTX, TXT, MD, CSV, JSON, XML, HTML, YAML
4. 업로드 후 자동으로 텍스트 추출 → 청킹 → 벡터화 진행
5. 진행률이 100%가 되면 챗봇에서 검색 가능

### 6.5. 사용자 추가

1. **관리** 페이지 → 사용자 관리 → **사용자 추가** 버튼
2. 아이디, 이름, 비밀번호, 역할(관리자/사용자) 입력
3. 일반 사용자(`user`)는 채팅만 가능
4. 관리자(`admin`)는 모든 기능 접근 가능

---

## 7. 기능별 사용법

### 7.1. AI 채팅 (RAG 질의응답)

- 사내 규정/문서에 대한 질문 → 벡터DB에서 관련 내용 검색 → LLM이 답변 생성
- NAS 파일 위치 질문 → NAS 인덱스에서 검색 + 규정 DB 통합 검색
- 예시:
  - "연차 신청 절차 알려줘" → 취업규칙에서 관련 조항 검색
  - "강의 관련 자료 어디 있어?" → NAS 파일 인덱스에서 검색
  - "출장비 관련 서류 경로 찾아줘" → NAS + 규정 통합 검색

### 7.2. NAS 파일 탐색

- 등록된 기본 디렉토리 하위를 탐색
- 파일 더블클릭 → 다운로드
- 폴더 더블클릭 → 하위 폴더 이동
- 검색창 → 현재 폴더에서 파일명 검색
- 업로드 / 새 폴더 / 이름 변경 / 삭제 지원
- 우클릭 컨텍스트 메뉴 지원

### 7.3. 관리자 페이지

- **시스템 상태**: 문서 수, 청크 수, LLM 프로바이더, NAS 연결, 인덱스 현황
- **문서 업로드**: 사내 규정/양식 업로드 (RAG 소스)
- **등록된 문서**: 업로드된 문서 목록, 삭제
- **NAS 기본 디렉토리**: 탐색 가능 경로 등록/삭제
- **사용자 관리**: 사용자 추가/삭제, 비밀번호 리셋

---

## 8. 관리자 운용 가이드

### 8.1. 서비스 상태 확인

```bash
# Docker 컨테이너 상태
docker compose ps

# 서비스 로그 (실시간)
docker compose logs -f app

# 최근 로그 50줄
docker compose logs --tail=50 app

# 헬스체크 API
curl http://localhost:8080/api/health
```

헬스체크 응답 예시:

```json
{
  "status": "ok",
  "document_count": 4,
  "total_chunks": 627,
  "llm_provider": "ollama",
  "nas_connected": true,
  "nas_base_dir_count": 1,
  "nas_index_count": 1523,
  "nas_index_last_scan": "2026-03-12T17:30:00",
  "nas_index_errors": 0
}
```

### 8.2. NAS 인덱스 관리

- **자동 스캔**: 서버 시작 시 즉시 1회 + 이후 1시간마다 자동 스캔
- **첫 스캔 실패**: 10초 간격으로 최대 2회 재시도
- **스캔 실패 보호**: 스캔 실패 시 이전 인덱스 유지 (빈 결과로 덮어쓰지 않음)
- **스캔 상태 확인**: 관리 페이지의 "인덱스 파일" 수와 "마지막 스캔" 시간 확인
- **에러 확인**: 로그에서 `스캔 실패` 키워드 검색

### 8.3. 일반적인 관리 작업

#### 서비스 재시작

```bash
docker compose restart app
```

#### 서비스 중지/시작

```bash
docker compose stop    # 중지 (자동 시작 비활성화)
docker compose start   # 시작
```

#### 이미지 재빌드 (코드 변경 후)

```bash
docker compose down
docker compose up -d --build
```

#### 로그 확인

```bash
# 전체 로그
docker compose logs app

# 에러만
docker compose logs app 2>&1 | grep ERROR

# NAS 관련 로그
docker compose logs app 2>&1 | grep -i nas
```

---

## 9. LLM 프로바이더 설정

### 9.1. 프로바이더별 특징

| 프로바이더 | 장점 | 단점 | 비용 |
|-----------|------|------|------|
| **OpenAI** | 고품질, 한국어 우수 | API 키 필요 | 유료 |
| **Gemini** | 무료 티어 있음, 가벼움 | 응답 품질 편차 | 무료/유료 |
| **Claude** | 긴 문맥, 정확함 | 임베딩 별도 | 유료 |
| **Ollama** | 무료, 데이터 외부 유출 없음 | GPU 필요, 한국어 약함 | 무료 |

### 9.2. NAS 배포 시 추천

NAS는 보통 GPU가 없으므로:

1. **Gemini** (추천): 무료 티어로 충분, 가벼움
2. **OpenAI**: 안정적, 고품질
3. **외부 PC Ollama**: GPU 있는 PC에서 Ollama 실행 후 연결

### 9.3. Ollama 모델 관리

```bash
# 모델 목록 확인
ollama list

# 모델 다운로드
ollama pull gemma3:4b          # LLM 모델
ollama pull nomic-embed-text   # 임베딩 모델

# 모델 삭제
ollama rm gemma3:4b

# 모델 테스트
ollama run gemma3:4b "안녕하세요"
```

---

## 10. 트러블슈팅

### 10.1. 서버가 시작되지 않음

**증상**: `docker compose up -d` 후 컨테이너가 바로 종료됨

```bash
# 로그 확인
docker compose logs app
```

**원인별 해결**:

| 에러 메시지 | 원인 | 해결 |
|------------|------|------|
| `ValidationError: Extra inputs are not permitted` | `.env`에 `config.py`에 없는 변수 | `.env`에서 해당 변수 삭제 |
| `Connection refused` (Ollama) | Ollama 서버 미실행 | `OLLAMA_BASE_URL` 확인, Ollama 서버 시작 |
| `Permission denied` | 파일 권한 문제 | `chmod -R 755 data/` |

### 10.2. NAS 탐색이 안 됨

**증상**: "디렉토리 조회 실패 (재인증 후에도 실패)"

1. `.env`의 `SYNOLOGY_URL`, `SYNOLOGY_USERNAME`, `SYNOLOGY_PASSWORD` 확인
2. Docker 내부에서 NAS에 접근 가능한지 확인:
   ```bash
   docker compose exec app curl -s http://NAS_IP:5000/webapi/entry.cgi
   ```
3. NAS 계정에 FileStation 접근 권한이 있는지 DSM에서 확인
4. 기본 디렉토리가 등록되어 있는지 확인 (관리 페이지)

### 10.3. 챗봇이 NAS 파일을 못 찾음

**증상**: "NAS 검색 결과 없음"

1. 관리 페이지에서 **인덱스 파일** 수 확인 → 0이면 스캔 실패
2. 로그에서 `NAS 인덱스 스캔 실패` 확인
3. 서버 재시작으로 재스캔 시도:
   ```bash
   docker compose restart app
   ```
4. 기본 디렉토리가 등록되어 있는지 확인

### 10.4. 파일 다운로드 실패

**증상**: 다운로드 클릭 시 에러 알림

1. 브라우저 개발자 도구(F12) → Network 탭에서 에러 상태 코드 확인
2. `400`: 경로가 기본 디렉토리 외부 → 기본 디렉토리 설정 확인
3. `500`: 서버 내부 에러 → `docker compose logs --tail=20 app` 확인
4. `502`: NAS 인증 만료 → 자동 재인증 실패, NAS 계정/비밀번호 확인

### 10.5. LLM 응답이 이상함 (러시아어 등)

**증상**: Ollama gemma3:4b가 한국어 대신 다른 언어로 응답

- gemma3:4b의 한계입니다
- 해결: 더 큰 모델 사용 (`gemma3:12b`) 또는 외부 API (Gemini, OpenAI) 사용

### 10.6. git pull 시 ownership 에러

**증상**: `fatal: detected dubious ownership in repository`

```bash
sudo git config --global --add safe.directory /volume1/chatbot/ST_YOUNGWON
```

홈 디렉토리가 없으면:

```bash
sudo mkdir -p /var/services/homes/$(whoami)
sudo git config --global --add safe.directory /volume1/chatbot/ST_YOUNGWON
```

---

## 11. 업데이트 방법

### 11.1. NAS 배포 업데이트

```bash
# 1. SSH 접속
ssh your-user@nas-ip

# 2. 프로젝트 디렉토리로 이동
cd /volume1/chatbot/ST_YOUNGWON

# 3. Docker 중지
sudo docker compose down

# 4. 코드 업데이트
sudo git pull origin main

# 5. Docker 재빌드 & 실행
sudo docker compose up -d --build

# 6. 정상 동작 확인
sudo docker compose logs --tail=20 app
```

### 11.2. 로컬 개발 업데이트

```bash
git pull origin main
pip install -r backend/requirements.txt  # 의존성 변경 시
# 서버 재시작
```

---

## 12. 백업 및 복구

### 12.1. 백업 대상

| 파일/디렉토리 | 내용 | 중요도 |
|--------------|------|--------|
| `.env` | 환경변수 (비밀번호, API 키) | 필수 |
| `data/users.db` | 사용자 계정 DB | 필수 |
| `data/documents/` | 업로드된 원본 문서 | 필수 |
| `data/chromadb/` | 벡터DB (재생성 가능) | 권장 |
| `data/nas/base_dirs.json` | NAS 기본 디렉토리 설정 | 권장 |

### 12.2. Docker 볼륨 백업

```bash
# 볼륨 위치 확인
docker volume inspect st_youngwon_chatbot_data

# 수동 백업
docker compose exec app tar czf /tmp/backup.tar.gz /app/data
docker cp st-youngwon-chatbot:/tmp/backup.tar.gz ./backup.tar.gz
```

### 12.3. 직접 실행 백업

```bash
# data 폴더와 .env 백업
tar czf backup-$(date +%Y%m%d).tar.gz data/ .env
```

### 12.4. 복구

```bash
# 1. 백업 파일 복원
tar xzf backup.tar.gz

# 2. Docker 재시작
docker compose up -d --build
```

### 12.5. 벡터DB만 재생성 (문서 원본이 있는 경우)

```bash
# chromadb 삭제 후 재시작하면 비어있는 상태
rm -rf data/chromadb/*
docker compose restart app

# 관리 페이지에서 문서 다시 업로드
# 또는 seed 스크립트 실행
docker compose exec app python scripts/seed_documents.py
```

---

## API 레퍼런스

서비스 실행 후 아래 주소에서 자동 생성된 API 문서를 확인할 수 있습니다:

- **Swagger UI**: `http://서비스주소/docs`
- **ReDoc**: `http://서비스주소/redoc`

### 주요 API 엔드포인트

| 메서드 | 경로 | 설명 | 권한 |
|--------|------|------|------|
| `POST` | `/api/auth/login` | 로그인 | 공개 |
| `POST` | `/api/auth/logout` | 로그아웃 | 인증 |
| `GET` | `/api/auth/me` | 내 정보 | 인증 |
| `PUT` | `/api/auth/change-password` | 내 비밀번호 변경 | 인증 |
| `POST` | `/api/chat` | 챗봇 질의 | 인증 |
| `POST` | `/api/chat/stream` | 챗봇 스트리밍 | 인증 |
| `GET` | `/api/documents` | 문서 목록 | 관리자 |
| `POST` | `/api/documents/upload` | 문서 업로드 | 관리자 |
| `DELETE` | `/api/documents/{id}` | 문서 삭제 | 관리자 |
| `GET` | `/api/nas/browse` | NAS 디렉토리 조회 | 관리자 |
| `GET` | `/api/nas/search` | NAS 파일 검색 | 관리자 |
| `GET` | `/api/nas/download` | NAS 파일 다운로드 | 관리자 |
| `POST` | `/api/nas/upload` | NAS 파일 업로드 | 관리자 |
| `POST` | `/api/nas/folder` | NAS 폴더 생성 | 관리자 |
| `POST` | `/api/nas/rename` | NAS 이름 변경 | 관리자 |
| `DELETE` | `/api/nas/delete` | NAS 파일/폴더 삭제 | 관리자 |
| `GET` | `/api/nas/base-dirs` | 기본 디렉토리 목록 | 관리자 |
| `POST` | `/api/nas/base-dirs` | 기본 디렉토리 추가 | 관리자 |
| `DELETE` | `/api/nas/base-dirs/{id}` | 기본 디렉토리 삭제 | 관리자 |
| `GET` | `/api/admin/users` | 사용자 목록 | 관리자 |
| `POST` | `/api/admin/users` | 사용자 생성 | 관리자 |
| `PUT` | `/api/admin/users/{id}/password` | 비밀번호 리셋 | 관리자 |
| `DELETE` | `/api/admin/users/{id}` | 사용자 삭제 | 관리자 |
| `GET` | `/api/health` | 헬스체크 | 공개 |
