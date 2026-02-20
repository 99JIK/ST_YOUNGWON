from __future__ import annotations

import logging
from typing import AsyncIterator, Protocol

import httpx
from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

from backend.app.config import settings

logger = logging.getLogger(__name__)


class LLMProvider(Protocol):
    async def generate(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> str: ...

    async def generate_stream(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> AsyncIterator[str]: ...


def _build_openai_messages(
    system: str, user: str, history: list[dict] | None = None
) -> list[dict]:
    """OpenAI/Ollama 형식의 메시지 목록을 구성합니다."""
    messages = [{"role": "system", "content": system}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user})
    return messages


class OpenAIProvider:
    """OpenAI API (gpt-4o-mini 등) 사용."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ):
        self._client = AsyncOpenAI(api_key=api_key or settings.openai_api_key)
        self._model = model or settings.openai_model

    async def generate(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=_build_openai_messages(system, user, history),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        return response.choices[0].message.content or ""

    async def generate_stream(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._model,
            messages=_build_openai_messages(system, user, history),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            stream=True,
        )
        async for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content


class ClaudeProvider:
    """Anthropic Claude API 사용."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ):
        self._client = AsyncAnthropic(
            api_key=api_key or settings.anthropic_api_key
        )
        self._model = model or settings.anthropic_model

    @staticmethod
    def _build_messages(
        user: str, history: list[dict] | None = None
    ) -> list[dict]:
        messages = []
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": user})
        return messages

    async def generate(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> str:
        response = await self._client.messages.create(
            model=self._model,
            system=system,
            messages=self._build_messages(user, history),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        )
        return response.content[0].text if response.content else ""

    async def generate_stream(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        async with self._client.messages.stream(
            model=self._model,
            system=system,
            messages=self._build_messages(user, history),
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
        ) as stream:
            async for text in stream.text_stream:
                yield text


class GeminiProvider:
    """Google Gemini API 사용."""

    def __init__(
        self,
        api_key: str = "",
        model: str = "",
    ):
        from google import genai

        self._client = genai.Client(api_key=api_key or settings.gemini_api_key)
        self._model = model or settings.gemini_model

    @staticmethod
    def _build_contents(
        user: str, history: list[dict] | None = None
    ) -> list[dict]:
        contents = []
        if history:
            for msg in history:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        contents.append({"role": "user", "parts": [{"text": user}]})
        return contents

    async def generate(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> str:
        from google.genai import types

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=self._build_contents(user, history),
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=settings.llm_temperature,
                max_output_tokens=settings.llm_max_tokens,
            ),
        )
        return response.text or ""

    async def generate_stream(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        from google.genai import types

        response_stream = await self._client.aio.models.generate_content_stream(
            model=self._model,
            contents=self._build_contents(user, history),
            config=types.GenerateContentConfig(
                system_instruction=system,
                temperature=settings.llm_temperature,
                max_output_tokens=settings.llm_max_tokens,
            ),
        )
        async for chunk in response_stream:
            if chunk.text:
                yield chunk.text


class OllamaProvider:
    """Ollama 로컬 LLM 사용."""

    def __init__(
        self,
        base_url: str = "",
        model: str = "",
    ):
        self._base_url = base_url or settings.ollama_base_url
        self._model = model or settings.ollama_model

    async def generate(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> str:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": _build_openai_messages(system, user, history),
                    "stream": False,
                    "options": {
                        "temperature": settings.llm_temperature,
                        "num_predict": settings.llm_max_tokens,
                    },
                },
            )
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")

    async def generate_stream(
        self, system: str, user: str, history: list[dict] | None = None
    ) -> AsyncIterator[str]:
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream(
                "POST",
                f"{self._base_url}/api/chat",
                json={
                    "model": self._model,
                    "messages": _build_openai_messages(system, user, history),
                    "stream": True,
                    "options": {
                        "temperature": settings.llm_temperature,
                        "num_predict": settings.llm_max_tokens,
                    },
                },
            ) as response:
                import json

                async for line in response.aiter_lines():
                    if line:
                        data = json.loads(line)
                        content = data.get("message", {}).get("content", "")
                        if content:
                            yield content


def create_llm_provider() -> LLMProvider:
    """설정에 따라 LLM 프로바이더를 생성합니다."""
    provider = settings.llm_provider
    if provider == "openai":
        return OpenAIProvider()
    elif provider == "claude":
        return ClaudeProvider()
    elif provider == "gemini":
        return GeminiProvider()
    elif provider == "ollama":
        return OllamaProvider()
    raise ValueError(f"지원하지 않는 LLM 프로바이더: {provider}")
