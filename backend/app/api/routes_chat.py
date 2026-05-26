from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.graph import run_chat
from app.schemas.chat import ChatRequest, ChatResponse
from app.streaming.sse_streamer import stream_chat_response

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(**run_chat(request.message, request.chat_id))


@router.post("/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    return StreamingResponse(
        stream_chat_response(request.message, request.chat_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
