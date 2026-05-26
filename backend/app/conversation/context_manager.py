"""
US-13: Multi-Turn Context Management
US-14: Follow-Up Query Handling
---------------------------------------
Builds on Himanshu's memory.py (chat state in MemoryCache) to add:

  US-13 - Rich conversation context:
    • Tracks last SQL query, last result set, last chart, active tables
    • Provides a formatted context summary for the agent system prompt
    • Sliding window of last N turns with role + content

  US-14 - Follow-up query resolution:
    • Detects pronouns / references ("that", "those rows", "the same table")
    • Rewrites ambiguous follow-up questions into self-contained questions
    • Injects prior SQL result schema for accurate column references
"""
from __future__ import annotations

import logging
import re
from typing import Any

from app.cache.memory_cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Constants ─────────────────────────────────────────────────────────────────

CONTEXT_WINDOW = 10          # max messages kept per session
SUMMARY_PREVIEW_ROWS = 3     # rows shown in context summary

# Follow-up trigger patterns
FOLLOWUP_PATTERNS = [
    re.compile(r"\b(those|these|that|them|it|the result|the data|same|above|previous|prior|last)\b", re.IGNORECASE),
    re.compile(r"\b(show more|more details|break.?down|drill.?down|filter|sort|order by|group by)\b", re.IGNORECASE),
    re.compile(r"^(and|but|also|what about|how about|now|can you)\b", re.IGNORECASE),
]


# ── Context state helpers ─────────────────────────────────────────────────────

def _ctx_key(chat_id: str) -> str:
    return f"ctx:{chat_id}"


def get_conversation_context(chat_id: str) -> dict[str, Any]:
    """Load the full conversation context for a session."""
    return cache.get(_ctx_key(chat_id)) or {
        "messages": [],
        "last_sql": None,
        "last_columns": [],
        "last_rows": [],
        "last_chart_type": None,
        "active_tables": [],
        "turn_count": 0,
    }


def save_conversation_context(chat_id: str, ctx: dict[str, Any]) -> None:
    cache.set(_ctx_key(chat_id), ctx, settings.CHAT_TTL_SECONDS)


def update_context_after_turn(
    chat_id: str,
    user_message: str,
    assistant_answer: str,
    sql: str | None = None,
    result: dict[str, Any] | None = None,
    chart_type: str | None = None,
) -> None:
    """
    Called at the end of every chat turn to keep the context state current.

    Args:
        chat_id:          Session identifier
        user_message:     What the user asked
        assistant_answer: What the assistant replied
        sql:              The T-SQL query that was run (if any)
        result:           The execute_select() dict (columns, rows, row_count…)
        chart_type:       The chart type chosen (if any)
    """
    ctx = get_conversation_context(chat_id)

    # Sliding message window
    messages = ctx.setdefault("messages", [])
    messages.append({"role": "user",      "content": user_message})
    messages.append({"role": "assistant", "content": assistant_answer})
    ctx["messages"] = messages[-CONTEXT_WINDOW:]

    # Track SQL + result
    if sql:
        ctx["last_sql"] = sql
        # Extract table names from FROM / JOIN
        tables = re.findall(r"\bFROM\s+([\w.]+)|\bJOIN\s+([\w.]+)", sql, re.IGNORECASE)
        ctx["active_tables"] = list({t for pair in tables for t in pair if t})

    if result:
        ctx["last_columns"] = result.get("columns", [])
        ctx["last_rows"]    = result.get("rows", [])[:SUMMARY_PREVIEW_ROWS]

    if chart_type:
        ctx["last_chart_type"] = chart_type

    ctx["turn_count"] = ctx.get("turn_count", 0) + 1
    save_conversation_context(chat_id, ctx)


# ── Context summary for agent prompt ─────────────────────────────────────────

def build_context_summary(chat_id: str) -> str:
    """
    Return a compact natural-language summary of the conversation context
    to inject into the agent's system prompt for follow-up awareness.
    """
    ctx = get_conversation_context(chat_id)
    parts: list[str] = []

    if ctx["turn_count"]:
        parts.append(f"This is turn #{ctx['turn_count'] + 1} of the conversation.")

    if ctx["last_sql"]:
        parts.append(f"Last SQL executed:\n```sql\n{ctx['last_sql']}\n```")

    if ctx["last_columns"]:
        cols = ", ".join(ctx["last_columns"])
        parts.append(f"Last result columns: {cols}")

    if ctx["last_rows"]:
        rows_preview = "; ".join(str(r) for r in ctx["last_rows"])
        parts.append(f"Last result sample (up to {SUMMARY_PREVIEW_ROWS} rows): {rows_preview}")

    if ctx["active_tables"]:
        tables = ", ".join(ctx["active_tables"])
        parts.append(f"Active tables: {tables}")

    if ctx["last_chart_type"]:
        parts.append(f"Last chart rendered: {ctx['last_chart_type']}")

    # Recent dialogue
    recent = ctx.get("messages", [])[-4:]
    if recent:
        dialogue = "\n".join(f"  [{m['role'].upper()}]: {m['content'][:200]}" for m in recent)
        parts.append(f"Recent dialogue:\n{dialogue}")

    return "\n\n".join(parts) if parts else "No prior context."


# ── US-14: Follow-up detection & rewriting ────────────────────────────────────

def is_followup_question(question: str) -> bool:
    """
    Return True if the question appears to reference prior context
    (pronouns, "those rows", "same table", etc.).
    """
    return any(p.search(question) for p in FOLLOWUP_PATTERNS)


def rewrite_followup_question(question: str, chat_id: str) -> str:
    """
    Resolve a follow-up question into a self-contained question by
    substituting context references with concrete values from the session.

    Examples:
        "Sort those by revenue"        → "Sort the results of <last_sql> by revenue"
        "Filter them to last 7 days"   → "Filter <active_table> results to the last 7 days"
        "Show me a pie chart of that"  → "Show me a pie chart of the previous query result"
    """
    if not is_followup_question(question):
        return question   # Nothing to rewrite

    ctx = get_conversation_context(chat_id)
    rewritten = question

    # Replace "those/these/them/it/the result/the data" with last result reference
    if ctx["last_sql"]:
        rewritten = re.sub(
            r"\b(those|these|them|it|the result|the data|that|the same)\b",
            "the results of the previous query",
            rewritten,
            flags=re.IGNORECASE,
        )

    # Append column context so LLM knows what columns are available
    if ctx["last_columns"]:
        cols = ", ".join(ctx["last_columns"])
        rewritten += f" [Available columns from last query: {cols}]"

    # Append table context
    if ctx["active_tables"]:
        tables = ", ".join(ctx["active_tables"])
        rewritten += f" [Active tables: {tables}]"

    if ctx["last_sql"]:
        rewritten += f" [Last SQL: {ctx['last_sql']}]"

    logger.debug("Follow-up rewrite: %r → %r", question, rewritten)
    return rewritten


# ── Convenience: full pipeline step ──────────────────────────────────────────

def prepare_question(question: str, chat_id: str) -> dict[str, Any]:
    """
    Prepare a question for the agent by:
      1. Detecting if it's a follow-up
      2. Rewriting it if necessary
      3. Returning the context summary to inject into the prompt

    Returns:
        {
            "question":        str  – rewritten (or original) question
            "is_followup":     bool
            "context_summary": str  – for injection into system prompt
        }
    """
    is_fu = is_followup_question(question)
    rewritten = rewrite_followup_question(question, chat_id) if is_fu else question
    summary = build_context_summary(chat_id)

    return {
        "question": rewritten,
        "is_followup": is_fu,
        "context_summary": summary,
    }
