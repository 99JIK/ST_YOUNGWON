from __future__ import annotations

import logging
import re
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
    REGULATIONS_COLLECTION,
    VectorStore,
)
from backend.app.models.schemas import ChatResponse, SourceReference
from backend.app.services.nas_index_service import NASIndexService

logger = logging.getLogger(__name__)

# 대화 히스토리 최대 턴 수 (user+assistant 쌍 기준)
MAX_HISTORY_TURNS = 10

# NAS 경로 관련 키워드 (하나라도 포함되면 NAS 질의)
NAS_KEYWORDS = [
    # 위치/경로 질문
    "어디에 있", "어디있", "어디 있", "어디서 찾", "어디에서 찾",
    "파일 위치", "자료 위치", "문서 위치", "문서 어디", "양식 어디", "서식 어디",
    "파일이 어디", "폴더", "경로", "NAS", "nas",
    # 파일/문서 요청 (구어체 포함)
    "파일 찾", "파일찾", "파일 줘", "파일줘", "파일좀", "파일 좀",
    "자료 찾", "자료찾", "자료 줘", "자료줘", "자료좀", "자료 좀",
    "문서 찾", "문서찾", "문서 줘", "문서줘", "문서좀", "문서 좀",
    "파일 보여", "자료 보여", "문서 보여",
    "파일 있", "문서 있", "자료 있",
    # "관련 파일/문서/자료" 패턴
    "관련 파일", "관련 문서", "관련 자료",
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

# NAS 검색어 추출 시 제거할 불용어
_NAS_NOISE = {
    "파일", "파일좀", "파일들", "위치", "어디", "폴더", "경로",
    "NAS", "nas", "서버", "찾아", "있는", "알려", "주세요", "줘",
    "에서", "좀", "어디에", "어디서", "뭐", "는", "이", "가",
    "을", "를", "관련", "문서", "문서좀", "자료", "자료좀",
    "보여", "보여줘", "알려줘", "해줘", "해주세요", "찾아줘",
    "있어", "있나", "있는지", "어디에서", "어디있어",
}


class ChatService:
    """RAG 기반 채팅 서비스."""

    def __init__(
        self,
        vectorstore: Optional[VectorStore] = None,
        llm: Optional[LLMProvider] = None,
        nas_index: Optional[NASIndexService] = None,
    ):
        self._vectorstore = vectorstore or VectorStore()
        self._llm = llm or create_llm_provider()
        self._nas_index = nas_index

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

        # 2. NAS 경로 질의 처리 → NAS + 규정 통합 검색
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

        # 2. NAS 경로 질의 → NAS + 규정 통합
        if self._is_nas_query(message) and self._nas_index:
            search_query = self._extract_nas_search_query(message)
            nas_results = self._nas_index.search(search_query)
            nas_context = self._format_index_results(nas_results) if nas_results else ""

            # 규정 DB도 검색
            reg_results = self._search_all_knowledge_raw(message)
            reg_context = self._format_context(reg_results) if reg_results else ""

            context = self._merge_contexts(nas_context, reg_context)
            prompt = format_nas_prompt(context or "검색 결과 없음", message)
        elif self._is_nas_query(message):
            prompt = format_nas_prompt("검색 결과 없음 (NAS 인덱스 미설정)", message)
        else:
            # 3. 규정 검색
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
        """NAS 파일 경로 질문을 처리합니다. NAS 인덱스 + 규정 DB 통합 검색."""
        # NAS 인덱스 검색
        nas_context = ""
        if self._nas_index:
            search_query = self._extract_nas_search_query(message)
            nas_results = self._nas_index.search(search_query)
            if nas_results:
                nas_context = self._format_index_results(nas_results)

        # 규정 DB도 검색 (NAS 질의라도 규정에 관련 내용이 있을 수 있음)
        reg_results = self._search_all_knowledge_raw(message)
        reg_context = self._format_context(reg_results) if reg_results else ""
        sources = self._extract_sources(reg_results) if reg_results else []

        context = self._merge_contexts(nas_context, reg_context)

        if not context:
            context = "검색 결과 없음"

        prompt = format_nas_prompt(context, message)
        answer = await self._llm.generate(SYSTEM_PROMPT, prompt, history)

        return ChatResponse(
            answer=answer,
            sources=sources,
            session_id=session_id,
        )

    def _search_all_knowledge_raw(self, message: str) -> list[dict]:
        """규정 컬렉션을 검색하여 원본 결과를 반환합니다."""
        return self._vectorstore.search(
            REGULATIONS_COLLECTION, message, top_k=settings.retrieval_top_k
        )

    @staticmethod
    def _merge_contexts(nas_context: str, reg_context: str) -> str:
        """NAS 검색 결과와 규정 검색 결과를 합칩니다."""
        parts = []
        if nas_context:
            parts.append(f"[NAS 파일 검색 결과]\n{nas_context}")
        if reg_context:
            parts.append(f"[규정/문서 검색 결과]\n{reg_context}")
        return "\n\n---\n\n".join(parts)

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

    @staticmethod
    def _format_index_results(results: list[dict]) -> str:
        """NAS 인덱스 검색 결과를 LLM 컨텍스트로 포맷팅합니다."""
        if not results:
            return "검색 결과 없음"
        parts = []
        for r in results:
            item_type = "폴더" if r.get("is_dir") else "파일"
            size_str = ""
            if not r.get("is_dir") and r.get("size"):
                size_mb = r["size"] / (1024 * 1024)
                size_str = f"  크기: {size_mb:.1f}MB\n" if size_mb >= 1 else f"  크기: {r['size'] / 1024:.0f}KB\n"
            parts.append(
                f"- [{item_type}] {r.get('name', '')}\n"
                f"  경로: {r.get('path', '')}\n"
                f"{size_str}"
            )
        return "\n\n".join(parts)

    @staticmethod
    def _extract_nas_search_query(message: str) -> str:
        """메시지에서 NAS 검색에 적합한 키워드를 추출합니다.

        불용어를 제거하되, 핵심 키워드가 남도록 합니다.
        모든 키워드가 제거되면 원본 메시지에서 한글/영문 단어만 추출합니다.
        """
        words = re.findall(r"[가-힣a-zA-Z0-9_.-]+", message)
        # 1차: 불용어 제거 + 2글자 이상
        keywords = [w for w in words if w not in _NAS_NOISE and len(w) >= 2]

        if keywords:
            return " ".join(keywords)

        # 2차: 1글자도 포함하되 불용어만 제거 (키워드가 전부 짧은 경우)
        keywords = [w for w in words if w not in _NAS_NOISE]
        if keywords:
            return " ".join(keywords)

        # 3차: 원본에서 한글/영문 단어만 (불용어 무시)
        fallback = re.findall(r"[가-힣]{2,}|[a-zA-Z0-9_.-]{2,}", message)
        return " ".join(fallback) if fallback else message

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
