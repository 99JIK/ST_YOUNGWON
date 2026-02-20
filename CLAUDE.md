# ST영원 스마트 오피스

## 프로젝트 개요
에스티영원 사내 AI 어시스턴트 + NAS 파일 관리 서비스.
시놀로지 NAS에 Docker로 배포.

## 기술 스택
- Backend: Python 3.11 + FastAPI
- Frontend: Jinja2 + Vanilla JS
- Vector DB: ChromaDB (embedded)
- LLM: OpenAI/Claude/Ollama (hybrid)
- Embedding: OpenAI text-embedding-3-small
- Deploy: Docker Compose

## 프로젝트 구조
- `backend/app/` - FastAPI 애플리케이션
- `frontend/` - Jinja2 템플릿 + 정적 파일
- `data/` - 영구 데이터 (Docker 볼륨)
- `config/` - 설정 파일
- `scripts/` - 유틸리티 스크립트

## 개발 규칙
- 한국어 UI/UX
- 모든 API는 `/api/` 접두사
- Pydantic으로 요청/응답 검증
- 비동기 함수 우선 사용
