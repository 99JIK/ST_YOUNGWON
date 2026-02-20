from __future__ import annotations

import logging
from typing import Protocol

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


class EmbeddingProvider(Protocol):
    def encode(self, texts: list[str]) -> list[list[float]]: ...

    @property
    def dimension(self) -> int: ...


class OpenAIEmbeddings:
    """OpenAI text-embedding-3-small을 사용한 임베딩."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "text-embedding-3-small",
    ):
        from openai import OpenAI

        self._client = OpenAI(api_key=api_key or settings.openai_api_key)
        self._model = model
        self._dimension = 1536

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            model=self._model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    @property
    def dimension(self) -> int:
        return self._dimension


class OllamaEmbeddings:
    """Ollama 로컬 모델을 사용한 임베딩."""

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
    ):
        self._base_url = base_url or settings.ollama_base_url
        self._model = model or settings.ollama_embedding_model
        self._dimension = 0  # 첫 호출 시 결정

    def _embed_single(self, text: str) -> list[float]:
        """단일 텍스트 임베딩 (폴백용)."""
        response = httpx.post(
            f"{self._base_url}/api/embed",
            json={"model": self._model, "input": text},
            timeout=120.0,
        )
        response.raise_for_status()
        data = response.json()
        return data["embeddings"][0]

    def encode(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []

        # 빈 문자열 / 공백만 있는 텍스트 필터링 (400 에러 원인)
        cleaned: list[tuple[int, str]] = []
        for i, t in enumerate(texts):
            stripped = t.strip()
            if stripped:
                cleaned.append((i, stripped))

        if not cleaned:
            return [[] for _ in texts]

        clean_texts = [t for _, t in cleaned]

        # 1차: 배치 호출 시도
        try:
            response = httpx.post(
                f"{self._base_url}/api/embed",
                json={"model": self._model, "input": clean_texts},
                timeout=300.0,
            )
            response.raise_for_status()
            data = response.json()
            clean_embeddings = data["embeddings"]
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            # 2차: 배치 실패 시 개별 호출로 폴백
            logger.warning(f"배치 임베딩 실패, 개별 호출로 전환합니다: {e}")
            clean_embeddings = []
            for idx, text in enumerate(clean_texts):
                try:
                    emb = self._embed_single(text)
                    clean_embeddings.append(emb)
                except Exception as single_err:
                    logger.error(f"개별 임베딩 실패 (index {idx}): {single_err}")
                    raise

        if self._dimension == 0 and clean_embeddings:
            self._dimension = len(clean_embeddings[0])

        # 원래 순서대로 결과 매핑 (빈 텍스트는 빈 리스트)
        result: list[list[float]] = [[] for _ in texts]
        for (orig_idx, _), emb in zip(cleaned, clean_embeddings):
            result[orig_idx] = emb

        return result

    @property
    def dimension(self) -> int:
        return self._dimension


def create_embedding_provider() -> EmbeddingProvider:
    """설정에 따라 임베딩 프로바이더를 생성합니다."""
    provider = settings.embedding_provider
    if provider == "openai":
        return OpenAIEmbeddings(
            api_key=settings.openai_api_key,
            model=settings.embedding_model,
        )
    elif provider == "ollama":
        return OllamaEmbeddings(
            base_url=settings.ollama_base_url,
            model=settings.ollama_embedding_model,
        )
    raise ValueError(f"지원하지 않는 임베딩 프로바이더: {provider}")
