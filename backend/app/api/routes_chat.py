import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from app.agent.graph import run_chat
from app.schemas.chat import ChatRequest, ChatResponse
from app.streaming.sse_streamer import stream_chat_response

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse | JSONResponse:
    try:
        return ChatResponse(**run_chat(request.message, request.chat_id))
    except Exception as exc:
        logger.error("Unhandled error in POST /chat: %s", exc)
        return JSONResponse(
            status_code=500,
            content={
                "error": str(exc),
                "error_type": "InternalError",
                "tool": "chat",
                "suggestion": "Try again. If the problem persists, check server logs.",
            },
        )


@router.post("/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_response(request.message, request.chat_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
