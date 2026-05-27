"""
routes_binit.py
----------------
FastAPI routes for Binit's user stories (US-08 to US-16).
Mount under /api in main.py alongside Himanshu's existing routers.

New endpoints:
  POST /api/text2sql/generate         – US-08: NL → T-SQL
  POST /api/text2sql/validate         – US-09: Validate a SQL query
  POST /api/text2sql/advanced         – US-10: Advanced SQL builder
  POST /api/viz/chart                 – US-11/12: Smart Plotly chart
  GET  /api/conversation/{chat_id}    – US-13: Get conversation context
  POST /api/conversation/{chat_id}/reset  – US-13: Reset session context
  POST /api/chat/stream2              – US-15: True SSE streaming endpoint
  GET  /api/cache/stats               – US-16: Cache statistics
  POST /api/cache/invalidate          – US-16: Invalidate by table
  POST /api/cache/flush               – US-16: Flush all
"""
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.conversation.context_manager import (
    build_context_summary,
    get_conversation_context,
    save_conversation_context,
)
from app.cache.enhanced_query_cache import (
    get_cache_stats,
    invalidate_all,
    invalidate_by_table,
)
from app.cache.cache_refresher import get_freshness_report
from app.streaming.sse_streamer import stream_chat_response
from app.text2sql.text2sql_pipeline import text2sql_pipeline
from app.text2sql.query_validator import validate_query_report
from app.text2sql.advanced_sql import run_advanced_sql, AdvancedSQLInput
from app.visualization.plotly_integration import build_plotly_viz, PlotlyVizInput

router = APIRouter(tags=["binit"])


# ── US-08: Text2SQL ───────────────────────────────────────────────────────────

class Text2SQLRequest(BaseModel):
    question: str = Field(..., min_length=1, description="Natural language question.")
    context: str = Field("", description="Optional prior conversation context snippet.")


@router.post("/text2sql/generate")
def generate_sql(request: Text2SQLRequest) -> dict[str, Any]:
    """US-08 — Convert a natural language question to a validated T-SQL SELECT query."""
    return text2sql_pipeline.generate(request.question, request.context)


@router.post("/text2sql/refresh-schema")
def refresh_schema() -> dict[str, str]:
    """Force a live reload of the database schema used by Text2SQL."""
    text2sql_pipeline.refresh_schema()
    return {"status": "schema refreshed"}


# ── US-09: Query Validation ───────────────────────────────────────────────────

class ValidateRequest(BaseModel):
    sql: str = Field(..., description="SQL query to validate.")


@router.post("/text2sql/validate")
def validate_sql(request: ValidateRequest) -> dict[str, Any]:
    """US-09 — Run full multi-stage validation and return a detailed report."""
    return validate_query_report(request.sql)


# ── US-10: Advanced SQL ───────────────────────────────────────────────────────

@router.post("/text2sql/advanced")
def advanced_sql(payload: AdvancedSQLInput) -> dict[str, Any]:
    """US-10 — Build advanced T-SQL (aggregation, window functions, date filters)."""
    return run_advanced_sql(**payload.model_dump())


# ── US-11 / US-12: Visualization ─────────────────────────────────────────────

@router.post("/viz/chart")
def smart_chart_endpoint(payload: PlotlyVizInput) -> dict[str, Any]:
    """US-11/12 — Dynamic chart selection + themed Plotly figure generation."""
    return build_plotly_viz(**payload.model_dump())


# ── US-13 / US-14: Conversation Context ──────────────────────────────────────

@router.get("/conversation/{chat_id}")
def get_context(chat_id: str) -> dict[str, Any]:
    """US-13 — Retrieve the full conversation context for a session."""
    ctx = get_conversation_context(chat_id)
    return {
        "chat_id": chat_id,
        "turn_count": ctx.get("turn_count", 0),
        "last_sql": ctx.get("last_sql"),
        "last_columns": ctx.get("last_columns", []),
        "active_tables": ctx.get("active_tables", []),
        "last_chart_type": ctx.get("last_chart_type"),
        "message_count": len(ctx.get("messages", [])),
        "context_summary": build_context_summary(chat_id),
    }


@router.post("/conversation/{chat_id}/reset")
def reset_context(chat_id: str) -> dict[str, str]:
    """US-13 — Reset the conversation context for a session (start fresh)."""
    save_conversation_context(chat_id, {
        "messages": [],
        "last_sql": None,
        "last_columns": [],
        "last_rows": [],
        "last_chart_type": None,
        "active_tables": [],
        "turn_count": 0,
    })
    return {"status": "context reset", "chat_id": chat_id}


# ── US-15: True SSE Streaming ─────────────────────────────────────────────────

class StreamRequest(BaseModel):
    message: str = Field(..., min_length=1)
    chat_id: str | None = None


@router.post("/chat/stream2")
def chat_stream2(request: StreamRequest) -> StreamingResponse:
    """
    US-15 — True SSE streaming endpoint with:
      • Real token-by-token streaming from Groq
      • Tool lifecycle events (tool_start / tool_end)
      • Follow-up detection and context injection
    """
    return StreamingResponse(
        stream_chat_response(request.message, request.chat_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


# ── US-16: Cache Management ───────────────────────────────────────────────────

@router.get("/cache/stats")
def cache_stats() -> dict[str, Any]:
    """US-16 — Return query cache hit/miss statistics."""
    return get_cache_stats()


class InvalidateRequest(BaseModel):
    table_name: str = Field(..., description="Table whose cached queries should be cleared.")


@router.post("/cache/invalidate")
def cache_invalidate(request: InvalidateRequest) -> dict[str, Any]:
    """US-16 — Invalidate all cached query results for a specific table."""
    count = invalidate_by_table(request.table_name)
    return {"invalidated": count, "table": request.table_name}


@router.post("/cache/flush")
def cache_flush() -> dict[str, Any]:
    """US-16 — Flush the entire query result cache."""
    count = invalidate_all()
    return {"flushed": count}


# ── Feature 1: Cache TTL Refresh ─────────────────────────────────────────────

@router.get("/cache/freshness")
def cache_freshness() -> dict[str, Any]:
    """
    Feature 1 — List cache keys that are near their TTL expiry.

    Returns entries where elapsed time >= CACHE_REFRESH_THRESHOLD_PCT of the TTL.
    The background refresher will proactively re-run these queries.
    """
    entries = get_freshness_report()
    return {"near_expiry_count": len(entries), "entries": entries}


class ManualRefreshRequest(BaseModel):
    table_name: str = Field(
        "",
        description="Table name whose queries should be force-refreshed. "
                    "Leave empty to refresh all near-expiry keys.",
    )


@router.post("/cache/refresh")
async def cache_refresh(request: ManualRefreshRequest) -> dict[str, Any]:
    """
    Feature 1 — Trigger an immediate cache refresh outside the background interval.

    If table_name is provided, only queries touching that table are refreshed.
    Otherwise all near-expiry keys are refreshed.
    """
    from app.cache import cache_refresher as refresher
    await refresher._do_refresh()
    entries = get_freshness_report()
    return {
        "status": "refresh triggered",
        "table_name": request.table_name or "all",
        "remaining_near_expiry": len(entries),
    }
