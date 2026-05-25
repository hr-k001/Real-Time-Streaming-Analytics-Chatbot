from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.agent.graph import run_chat
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    return ChatResponse(**run_chat(request.message, request.chat_id))


@router.post("/stream")
def chat_stream(request: ChatRequest) -> StreamingResponse:
    def event_stream():
        result = run_chat(request.message, request.chat_id)
        yield f"event: chat_id\ndata: {result['chat_id']}\n\n"
        for word in result["answer"].split():
            yield f"event: token\ndata: {word} \n\n"
        yield "event: done\ndata: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
