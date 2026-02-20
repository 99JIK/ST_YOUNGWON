from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from backend.app.dependencies import get_chat_service, get_current_user
from backend.app.models.schemas import ChatRequest, ChatResponse
from backend.app.services.chat_service import ChatService

router = APIRouter()


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    _user: dict = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """채팅 메시지를 처리하고 답변을 반환합니다."""
    history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
    return await chat_service.answer(
        message=request.message,
        session_id=request.session_id or "",
        history=history,
    )


@router.post("/api/chat/stream")
async def chat_stream(
    request: ChatRequest,
    _user: dict = Depends(get_current_user),
    chat_service: ChatService = Depends(get_chat_service),
):
    """스트리밍 방식으로 채팅 답변을 반환합니다 (Server-Sent Events)."""

    async def event_generator():
        try:
            history = [{"role": m.role, "content": m.content} for m in request.history] if request.history else None
            async for token in chat_service.answer_stream(
                message=request.message,
                session_id=request.session_id or "",
                history=history,
            ):
                data = json.dumps({"token": token}, ensure_ascii=False)
                yield f"data: {data}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            error = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
