from __future__ import annotations

from typing import Any

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_groq import ChatGroq
from langgraph.prebuilt import create_react_agent

from app.agent.memory import append_message, get_chat_state, new_chat_id, save_chat_state
from app.agent.prompts import build_system_prompt
from app.conversation.context_manager import prepare_question, update_context_after_turn
from app.core.config import settings
from app.text2sql.schema_registry import format_schema_for_prompt, load_database_schema
from app.tools import REGISTERED_TOOLS


def _load_schema_text() -> str:
    try:
        return format_schema_for_prompt(load_database_schema())
    except Exception:
        return ""


def _to_lc_messages(chat_id: str, message: str, context_summary: str = "") -> list[Any]:
    state = get_chat_state(chat_id)
    history = state.get("messages", [])[-8:]
    system_content = build_system_prompt(_load_schema_text())
    if context_summary and context_summary != "No prior context.":
        system_content += f"\n\nConversation context:\n{context_summary}"
    lc_messages: list[Any] = [SystemMessage(content=system_content)]
    for item in history:
        if item["role"] == "user":
            lc_messages.append(HumanMessage(content=item["content"]))
        elif item["role"] == "assistant":
            lc_messages.append(AIMessage(content=item["content"]))
    lc_messages.append(HumanMessage(content=message))
    return lc_messages


def run_chat(message: str, chat_id: str | None = None) -> dict[str, Any]:
    active_chat_id = chat_id or new_chat_id()
    prepared = prepare_question(message, active_chat_id)
    question = prepared["question"]

    if not settings.GROQ_API_KEY:
        return {
            "chat_id": active_chat_id,
            "answer": "Groq is not configured yet. Add GROQ_API_KEY to backend/.env and restart the API.",
            "tool_calls": [],
            "chart": None,
            "data": None,
            "from_cache": False,
        }

    llm = ChatGroq(
        model=settings.GROQ_MODEL,
        temperature=0,
        api_key=settings.GROQ_API_KEY,
    )
    agent = create_react_agent(llm, REGISTERED_TOOLS)
    result = agent.invoke({"messages": _to_lc_messages(active_chat_id, question, prepared["context_summary"])})

    messages = result.get("messages", [])
    answer = messages[-1].content if messages else "I could not generate a response."
    tool_calls: list[dict[str, Any]] = []
    chart = None
    data = None
    from_cache = False
    last_sql = None
    last_result = None
    chart_type = None

    for item in messages:
        if getattr(item, "type", "") == "tool":
            name = getattr(item, "name", "tool")
            content = getattr(item, "content", "")
            record = {"name": name, "input": {}, "output": {"content": content}, "error": None}
            tool_calls.append(record)
            if name in ("chart_generator", "dynamic_chart", "plotly_viz"):
                chart = {"content": content}
                chart_type = name
            if name == "sql_executor":
                data = {"content": content}
                last_result = data
                from_cache = "from_cache" in content and "True" in content
                sql_marker = "'sql': '"
                if sql_marker in content:
                    last_sql = content.split(sql_marker, 1)[1].split("'", 1)[0]

    append_message(active_chat_id, "user", message)
    append_message(active_chat_id, "assistant", answer)
    update_context_after_turn(
        chat_id=active_chat_id,
        user_message=message,
        assistant_answer=answer,
        sql=last_sql,
        result=last_result,
        chart_type=chart_type,
    )
    state = get_chat_state(active_chat_id)
    state["last_result"] = data
    save_chat_state(active_chat_id, state)

    return {
        "chat_id": active_chat_id,
        "answer": answer,
        "tool_calls": tool_calls,
        "chart": chart,
        "data": data,
        "from_cache": from_cache,
    }
