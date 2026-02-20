from __future__ import annotations

import logging
import uuid
from typing import AsyncIterator, Optional

from backend.app.config import settings
from backend.app.core.llm_provider import LLMProvider, create_llm_provider
from backend.app.core.prompts import (
    META_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    format_fallback_prompt,
    format_meta_prompt,
    format_nas_prompt,
    format_qa_prompt,
)
from backend.app.core.vectorstore import (
    NAS_FILES_COLLECTION,
    NAS_PATHS_COLLECTION,
    REGULATIONS_COLLECTION,
    VectorStore,
)
from backend.app.models.schemas import ChatResponse, SourceReference

logger = logging.getLogger(__name__)

# 대화 히스토리 최대 턴 수 (user+assistant 쌍 기준)
MAX_HISTORY_TURNS = 10

# NAS 경로 관련 키워드
NAS_KEYWORDS = [
    "파일 위치", "어디에 있", "폴더", "경로", "NAS", "서버",
    "파일 찾", "자료 위치", "파일이 어디", "어디서 찾",
]

# 메타/인사 키워드
META_KEYWORDS = [
    "안녕", "반갑", "하이", "hello", "hi ", "hey",
    "자기소개", "누구", "뭐야", "정체", "이름이",
    "기능", "뭐 할 수", "뭘 할 수", "무엇을 할", "뭘 해", "도움",
    "할 수 있", "해 줄 수", "해줄 수", "사용법", "사용 방법", "어떻게 사용",
    "고마워", "감사", "고맙", "수고",
    "도와줘", "도와 줘",
]


class ChatService:
    """RAG 기반 채팅 서비스."""

    def __init__(
        self,
        vectorstore: Optional[VectorStore] = None,
        llm: Optional[LLMProvider] = None,
    ):
        self._vectorstore = vectorstore or VectorStore()
        self._llm = llm or create_llm_provider()

    @staticmethod
    def _trim_history(history: list[dict] | None) -> list[dict] | None:
        """히스토리를 최대 턴 수로 제한합니다."""
        if not history:
            return None
        max_messages = MAX_HISTORY_TURNS * 2
        if len(history) > max_messages:
            return history[-max_messages:]
        return history

    def _is_nas_query(self, message: str) -> bool:
        """NAS 파일 경로 관련 질문인지 판별합니다."""
        return any(keyword in message for keyword in NAS_KEYWORDS)

    def _is_meta_query(self, message: str) -> bool:
        """메타 질문(인사, 기능 문의 등)인지 판별합니다."""
        msg = message.lower().strip()
        # 짧은 인사말 (5글자 이하)
        if len(msg) <= 5 and any(kw in msg for kw in ["안녕", "하이", "hi", "hey"]):
            return True
        return any(keyword in msg for keyword in META_KEYWORDS)

    async def answer(
        self,
        message: str,
        session_id: str = "",
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """사용자 질문에 대한 답변을 생성합니다."""
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        history = self._trim_history(history)

        # 1. 메타 질문 처리 (인사, 기능 문의 등)
        if self._is_meta_query(message):
            return await self._handle_meta_query(message, session_id, history)

        # 2. NAS 경로 질의 처리
        if self._is_nas_query(message):
            return await self._handle_nas_query(message, session_id, history)

        # 3. 일반 질의 처리 (규정 + NAS 파일 검색)
        return await self._handle_knowledge_query(message, session_id, history)

    async def answer_stream(
        self,
        message: str,
        session_id: str = "",
        history: list[dict] | None = None,
    ) -> AsyncIterator[str]:
        """스트리밍 방식으로 답변을 생성합니다."""
        if not session_id:
            session_id = str(uuid.uuid4())[:8]

        history = self._trim_history(history)

        # 1. 메타 질문 처리
        if self._is_meta_query(message):
            prompt = format_meta_prompt(message)
            async for token in self._llm.generate_stream(
                META_SYSTEM_PROMPT, prompt, history
            ):
                yield token
            return

        # 2. NAS 경로 질의
        if self._is_nas_query(message):
            nas_results = self._vectorstore.search(
                NAS_PATHS_COLLECTION, message, top_k=5
            )
            if nas_results:
                context = self._format_nas_context(nas_results)
                prompt = format_nas_prompt(context, message)
            else:
                results = self._search_all_knowledge_raw(message)
                if results:
                    context = self._format_context(results)
                    prompt = format_qa_prompt(context, message)
                else:
                    prompt = format_fallback_prompt(message)
        else:
            # 3. 규정 + NAS 파일 통합 검색
            results = self._search_all_knowledge_raw(message)
            if results:
                context = self._format_context(results)
                prompt = format_qa_prompt(context, message)
            else:
                prompt = format_fallback_prompt(message)

        async for token in self._llm.generate_stream(SYSTEM_PROMPT, prompt, history):
            yield token

    async def _handle_meta_query(
        self,
        message: str,
        session_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """메타 질문(인사, 기능 문의 등)을 처리합니다."""
        prompt = format_meta_prompt(message)
        answer = await self._llm.generate(META_SYSTEM_PROMPT, prompt, history)

        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
        )

    async def _handle_knowledge_query(
        self,
        message: str,
        session_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """규정 + NAS 파일을 통합 검색하여 질문에 답변합니다."""
        results = self._search_all_knowledge_raw(message)
        logger.info(f"[DEBUG] Knowledge search: {len(results)} results for '{message[:30]}'")

        if not results:
            return await self._handle_fallback_query(message, session_id, history)

        context = self._format_context(results)
        prompt = format_qa_prompt(context, message)
        answer = await self._llm.generate(SYSTEM_PROMPT, prompt, history)
        sources = self._extract_sources(results)
        logger.info(f"[DEBUG] Extracted {len(sources)} sources")

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
        )

    async def _handle_fallback_query(
        self,
        message: str,
        session_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """벡터DB에 관련 자료가 없을 때 일반 LLM으로 답변합니다."""
        prompt = format_fallback_prompt(message)
        answer = await self._llm.generate(SYSTEM_PROMPT, prompt, history)

        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
        )

    async def _handle_nas_query(
        self,
        message: str,
        session_id: str,
        history: list[dict] | None = None,
    ) -> ChatResponse:
        """NAS 파일 경로 질문을 처리합니다."""
        nas_results = self._vectorstore.search(
            NAS_PATHS_COLLECTION, message, top_k=5
        )

        if not nas_results:
            return await self._handle_knowledge_query(message, session_id, history)

        context = self._format_nas_context(nas_results)
        prompt = format_nas_prompt(context, message)
        answer = await self._llm.generate(SYSTEM_PROMPT, prompt, history)

        return ChatResponse(
            answer=answer,
            sources=[],
            session_id=session_id,
        )

    def _search_all_knowledge_raw(self, message: str) -> list[dict]:
        """규정 컬렉션과 NAS 파일 컬렉션을 모두 검색하여 원본 결과를 반환합니다."""
        all_results = []

        # 규정 검색
        reg_results = self._vectorstore.search(
            REGULATIONS_COLLECTION, message, top_k=settings.retrieval_top_k
        )
        all_results.extend(reg_results)

        # NAS 파일 내용 검색
        nas_file_results = self._vectorstore.search(
            NAS_FILES_COLLECTION, message, top_k=3
        )
        all_results.extend(nas_file_results)

        # 유사도 순 정렬
        all_results.sort(key=lambda x: x.get("similarity", 0), reverse=True)

        return all_results[:settings.retrieval_top_k]

    def _format_context(self, results: list[dict]) -> str:
        """검색 결과를 LLM 컨텍스트로 포맷팅합니다."""
        context_parts = []
        for i, result in enumerate(results, 1):
            metadata = result.get("metadata", {})
            source = metadata.get("source", "알 수 없음")
            article = metadata.get("article_title", "")
            article_num = metadata.get("article_number", "")

            header = f"[출처: {source}"
            if article_num:
                header += f", 제{article_num}조"
            if article:
                header += f" ({article})"
            header += f", 유사도: {result.get('similarity', 0):.2f}]"

            context_parts.append(f"{header}\n{result['content']}")

        return "\n\n---\n\n".join(context_parts)

    def _format_nas_context(self, results: list[dict]) -> str:
        """NAS 검색 결과를 포맷팅합니다."""
        parts = []
        for result in results:
            metadata = result.get("metadata", {})
            parts.append(
                f"- 파일명: {metadata.get('name', '')}\n"
                f"  경로: {metadata.get('path', '')}\n"
                f"  분류: {metadata.get('category', '')}\n"
                f"  설명: {metadata.get('description', '')}"
            )
        return "\n\n".join(parts)

    def _extract_sources(self, results: list[dict]) -> list[SourceReference]:
        """검색 결과에서 출처 정보를 추출합니다."""
        sources = []
        seen = set()
        for result in results:
            metadata = result.get("metadata", {})
            source_key = (
                metadata.get("source", ""),
                metadata.get("article_number", ""),
            )
            if source_key in seen:
                continue
            seen.add(source_key)

            article_str = ""
            if metadata.get("article_number"):
                article_str = f"제{metadata['article_number']}조"
                if metadata.get("article_title"):
                    article_str += f" ({metadata['article_title']})"

            sources.append(
                SourceReference(
                    document=metadata.get("source", ""),
                    article=article_str,
                    page=metadata.get("page", 0),
                    relevance_score=round(result.get("similarity", 0), 2),
                )
            )
        return sources
