"""
US-15: Streaming Response System
-----------------------------------
Implements true token-by-token SSE streaming for the chat endpoint.

Replaces Himanshu's word-split stub in routes_chat.py with a real
Groq streaming call that yields tokens as they arrive from the LLM.

SSE event format:
  event: chat_id     data: <uuid>
  event: token       data: <word or token chunk>
  event: tool_start  data: <tool_name>
  event: tool_end    data: <json result summary>
  event: done        data: [DONE]
  event: error       data: <message>
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Generator
from typing import Any

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.agent.memory import append_message, get_chat_state, new_chat_id, save_chat_state
from app.agent.prompts import build_system_prompt
from app.conversation.context_manager import (
    build_context_summary,
    prepare_question,
    update_context_after_turn,
)
from app.core.config import settings
from app.text2sql.schema_registry import format_schema_for_prompt, load_database_schema
from app.tools import REGISTERED_TOOLS

logger = logging.getLogger(__name__)


# ── SSE helpers ───────────────────────────────────────────────────────────────

def _sse(event: str, data: str) -> str:
    """Format a single SSE frame."""
    safe_data = data.replace("\n", " ")
    return f"event: {event}\ndata: {safe_data}\n\n"


def _parse_tool_content(content: str) -> dict[str, Any] | None:
    """Parse tool message content — tries JSON first, then Python literal_eval."""
    if not isinstance(content, str):
        return content if isinstance(content, dict) else None
    try:
        return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        import ast
        result = ast.literal_eval(content)
        return result if isinstance(result, dict) else None
    except Exception:
        return None


# ── Schema loader (same as graph.py) ─────────────────────────────────────────

def _schema_text() -> str:
    try:
        return format_schema_for_prompt(load_database_schema())
    except Exception:
        return ""


# ── Core streaming generator ──────────────────────────────────────────────────

def stream_chat_response(
    message: str,
    chat_id: str | None = None,
) -> Generator[str, None, None]:
    """
    Stream a chat response as SSE events.

    Yields SSE frames:
      • chat_id   – session id
      • token     – each streamed token chunk from Groq
      • tool_*    – tool lifecycle events
      • done      – final frame
      • error     – on failure
    """
    active_chat_id = chat_id or new_chat_id()
    yield _sse("chat_id", active_chat_id)

    if not settings.GROQ_API_KEY:
        yield _sse("token", "Groq is not configured. Add GROQ_API_KEY to backend/.env and restart.")
        yield _sse("done", "[DONE]")
        return

    # ── Prepare question (follow-up detection + rewrite) ──────────────────
    prepared = prepare_question(message, active_chat_id)
    question = prepared["question"]
    context_summary = prepared["context_summary"]

    if prepared["is_followup"]:
        yield _sse("meta", json.dumps({"is_followup": True, "rewritten": question}))

    # ── Build message list ────────────────────────────────────────────────
    schema = _schema_text()
    system_content = build_system_prompt(schema)
    if context_summary and context_summary != "No prior context.":
        system_content += f"\n\nConversation context:\n{context_summary}"

    state = get_chat_state(active_chat_id)
    history = state.get("messages", [])[-8:]
    lc_messages: list[Any] = [SystemMessage(content=system_content)]
    for item in history:
        if item["role"] == "user":
            lc_messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            lc_messages.append(AIMessage(content=item["content"]))
    lc_messages.append(HumanMessage(content=question))

    # ── Stream from Groq ──────────────────────────────────────────────────
    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0,
        api_key=settings.GROQ_API_KEY,
        streaming=True,
    )

    from langgraph.prebuilt import create_react_agent

    # Use non-streaming agent for tool calls (tool calls don't support token streaming),
    # then stream the final answer token-by-token.
    agent = create_react_agent(llm, REGISTERED_TOOLS)

    try:
        result = agent.invoke({"messages": lc_messages})
    except Exception as exc:
        logger.exception("Streaming agent invoke failed")
        yield _sse("error", str(exc))
        yield _sse("done", "[DONE]")
        return

    # ── Emit tool call events ─────────────────────────────────────────────
    messages = result.get("messages", [])
    tool_results: list[dict[str, Any]] = []
    last_sql: str | None = None
    last_result: dict[str, Any] | None = None
    chart_type: str | None = None

    for msg in messages:
        msg_type = getattr(msg, "type", "")
        if msg_type == "tool":
            name = getattr(msg, "name", "tool")
            content = getattr(msg, "content", "")
            yield _sse("tool_start", name)

            # Parse tool output (LangGraph may use JSON or Python repr format)
            parsed_output = _parse_tool_content(content)

            if name in ("chart_generator", "dynamic_chart", "plotly_viz"):
                # Emit full figure JSON as a dedicated chart event
                figure = None
                if isinstance(parsed_output, dict):
                    figure = parsed_output.get("figure")
                if figure:
                    yield _sse("chart", json.dumps(figure))
                chart_type = name
                summary = f"Chart type: {parsed_output.get('chart_type', 'generated') if parsed_output else 'generated'}"
            else:
                # For non-chart tools, truncate the summary
                summary = content[:300] + ("…" if len(content) > 300 else "")

            yield _sse("tool_end", json.dumps({"tool": name, "summary": summary}))

            record = {"name": name, "output": content}
            tool_results.append(record)

            # Track SQL metadata
            if name == "sql_executor":
                sql_match = re.search(r"['\"]sql['\"]:\s*['\"]([^'\"]+)", content)
                if sql_match:
                    last_sql = sql_match.group(1)
                last_result = {"content": content}

    # ── Stream the final assistant answer token-by-token ──────────────────
    final_answer = messages[-1].content if messages else "I could not generate a response."

    # Stream the final answer word-by-word in small chunks
    words = final_answer.split()
    chunk_size = 3
    for i in range(0, len(words), chunk_size):
        # The trailing space separates chunks; frontend must NOT add an extra space
        chunk = " ".join(words[i:i + chunk_size])
        if i + chunk_size < len(words):
            chunk += " "  # space between chunks, not after the last
        yield _sse("token", chunk)

    # ── Persist to memory ─────────────────────────────────────────────────
    append_message(active_chat_id, "user", message)
    append_message(active_chat_id, "assistant", final_answer)

    update_context_after_turn(
        chat_id=active_chat_id,
        user_message=message,
        assistant_answer=final_answer,
        sql=last_sql,
        result=last_result,
        chart_type=chart_type,
    )

    state = get_chat_state(active_chat_id)
    state["last_result"] = last_result
    save_chat_state(active_chat_id, state)

    yield _sse("done", "[DONE]")
