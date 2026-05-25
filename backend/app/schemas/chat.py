from typing import Any

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    chat_id: str | None = None


class ToolCallRecord(BaseModel):
    name: str
    input: dict[str, Any]
    output: dict[str, Any] | None = None
    error: str | None = None


class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    tool_calls: list[ToolCallRecord] = []
    chart: dict[str, Any] | None = None
    data: dict[str, Any] | None = None
    from_cache: bool = False
