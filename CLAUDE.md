# ST영원 스마트 오피스

## 프로젝트 개요
에스티영원 사내 AI 어시스턴트 + 시놀로지 NAS 파일 탐색 서비스.
사내 문서(취업규칙, 근무규정 등)를 업로드하면 RAG 기반으로 질의응답이 가능하고,
시놀로지 NAS에 직접 연결하여 파일을 탐색/검색/다운로드할 수 있다.

## 기술 스택
- Backend: Python 3.11 + FastAPI
- Frontend: Jinja2 + Vanilla JS
- Vector DB: ChromaDB (embedded)
- LLM: OpenAI / Claude / Gemini / Ollama (hybrid)
- Embedding: OpenAI text-embedding-3-small 또는 Ollama nomic-embed-text
- Deploy: Docker Compose 또는 직접 실행

## 프로젝트 구조
```
backend/app/         FastAPI 애플리케이션
  ├── api/           API 라우터 (chat, documents, nas_browser, health, users)
  ├── core/          LLM, 임베딩, 벡터스토어, 프롬프트
  ├── services/      비즈니스 로직
  ├── models/        Pydantic 스키마
  ├── utils/         파일 파싱, 한국어 유틸, 텍스트 청킹
  ├── config.py      Pydantic Settings (모든 환경변수 정의)
  └── main.py        FastAPI 엔트리포인트
frontend/            Jinja2 템플릿 + 정적 파일
config/              settings.yaml (설정 레퍼런스)
scripts/             seed_documents.py
data/                영구 데이터 (Docker 볼륨)
```

## 실행 방법

### Docker (프로덕션)
```bash
cp .env.example .env   # 환경변수 설정
docker compose up -d --build
# http://localhost:8080
```

### Docker + Ollama (로컬 LLM)
```bash
docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d --build
docker compose exec ollama ollama pull gemma3:4b
docker compose exec ollama ollama pull nomic-embed-text
```

### 직접 실행 (Docker 없이)
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r backend/requirements.txt
export PYTHONPATH=$(pwd)
uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
```

### Make 명령어
```bash
make up              # Docker 시작
make down            # Docker 종료
make logs            # 로그 확인
make build           # 이미지 재빌드
make seed            # 문서 초기 인덱싱
make dev             # 로컬 개발 서버 (hot-reload)
make up-ollama       # Ollama 포함 시작
```

## 환경변수
`.env.example` 참고. 주요 설정:
- `LLM_PROVIDER`: openai / claude / gemini / ollama
- `EMBEDDING_PROVIDER`: openai / ollama
- `OLLAMA_BASE_URL`: Ollama 서버 주소 (외부 PC 사용 시 `http://<IP>:11434`)
- `SYNOLOGY_URL`, `SYNOLOGY_USERNAME`, `SYNOLOGY_PASSWORD`: 시놀로지 NAS 연결
- `ADMIN_PASSWORD`, `SECRET_KEY`: 반드시 변경

## 개발 규칙
- 한국어 UI/UX
- 모든 API는 `/api/` 접두사
- Pydantic으로 요청/응답 검증
- 비동기 함수 우선 사용
- 설정 추가 시 `backend/app/config.py` → `.env.example` → `docker-compose.yml` 순서로 반영

## API 문서
앱 실행 후 `/docs` (Swagger UI) 또는 `/redoc` 에서 확인 가능.
