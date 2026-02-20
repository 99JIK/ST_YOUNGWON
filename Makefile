.PHONY: up down logs build seed dev test clean

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f app

build:
	docker compose build --no-cache

seed:
	docker compose exec app python scripts/seed_documents.py

dev:
	uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000

test:
	pytest backend/tests/ -v

clean:
	docker compose down -v
	rm -rf data/chromadb/* data/extracted/* data/documents/*

# With Ollama
up-ollama:
	docker compose -f docker-compose.yml -f docker-compose.ollama.yml up -d

down-ollama:
	docker compose -f docker-compose.yml -f docker-compose.ollama.yml down

# With Gemini API (lightweight, ideal for NAS)
up-gemini:
	LLM_PROVIDER=gemini docker compose up -d

down-gemini:
	docker compose down
