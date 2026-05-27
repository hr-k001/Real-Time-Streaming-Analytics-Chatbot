"""
spreadsheet_handler.py
-----------------------
In-memory spreadsheet registry.  Loads Excel (.xlsx / .xls) and CSV files
as pandas DataFrames and exposes a LangGraph StructuredTool to query them.

Supports:
  • Free-text keyword search across all string columns
  • Explicit column=value filters
  • Row limit
"""
from __future__ import annotations

import io
import uuid
from typing import Any

import pandas as pd
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.error_handler import structured_error


class SpreadsheetRegistry:
    """Singleton that keeps all in-session uploaded DataFrames."""

    def __init__(self) -> None:
        self._frames: dict[str, pd.DataFrame] = {}
        self._names: dict[str, str] = {}   # source_id → original filename

    # ── Registration ──────────────────────────────────────────────────────────

    def load(self, file_bytes: bytes, filename: str, source_id: str | None = None) -> str:
        sid = source_id or str(uuid.uuid4())
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""

        if ext in ("xls", "xlsx"):
            df = pd.read_excel(io.BytesIO(file_bytes))
        else:
            # CSV (or unknown extension — try CSV as fallback)
            df = pd.read_csv(io.BytesIO(file_bytes))

        self._frames[sid] = df
        self._names[sid] = filename
        return sid

    def remove(self, source_id: str) -> bool:
        if source_id not in self._frames:
            return False
        del self._frames[source_id]
        del self._names[source_id]
        return True

    # ── Introspection ─────────────────────────────────────────────────────────

    def get_schema(self, source_id: str) -> dict[str, Any] | None:
        df = self._frames.get(source_id)
        if df is None:
            return None
        return {
            "source_id": source_id,
            "filename": self._names.get(source_id, ""),
            "row_count": len(df),
            "columns": [{"name": col, "dtype": str(df[col].dtype)} for col in df.columns],
        }

    def list_sources(self) -> list[dict[str, Any]]:
        return [self.get_schema(sid) for sid in self._frames]  # type: ignore[misc]

    # ── Query ─────────────────────────────────────────────────────────────────

    def query(
        self,
        source_id: str,
        question: str = "",
        filters: dict[str, Any] | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        df = self._frames.get(source_id)
        if df is None:
            return structured_error(
                tool="spreadsheet_query",
                message=f"No spreadsheet loaded with source_id='{source_id}'.",
                error_type="NotFoundError",
                suggestion="Upload a spreadsheet first via POST /api/upload/spreadsheet.",
            )

        result = df.copy()

        # Explicit column=value filters (case-insensitive string match)
        if filters:
            for col, val in filters.items():
                if col in result.columns:
                    result = result[
                        result[col].astype(str).str.lower() == str(val).lower()
                    ]

        # Free-text keyword search across string columns
        if question:
            str_cols = result.select_dtypes(include="object").columns
            if len(str_cols) > 0:
                mask = result[str_cols].apply(
                    lambda col: col.astype(str).str.lower().str.contains(
                        question.lower(), na=False
                    )
                ).any(axis=1)
                # Only narrow down if keyword actually matches anything
                if mask.any():
                    result = result[mask]

        result = result.head(limit)
        rows = result.where(pd.notnull(result), None).to_dict(orient="records")
        return {
            "source_id": source_id,
            "filename": self._names.get(source_id, ""),
            "columns": list(result.columns),
            "rows": rows,
            "row_count": len(rows),
            "question": question,
        }


# Module-level singleton
registry = SpreadsheetRegistry()


# ── Public helpers (used by routes and tests) ─────────────────────────────────

def load_spreadsheet(file_bytes: bytes, filename: str, source_id: str | None = None) -> str:
    return registry.load(file_bytes, filename, source_id)


def query_spreadsheet(
    source_id: str,
    question: str = "",
    filters: dict[str, Any] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    return registry.query(source_id, question, filters, limit)


def get_schema(source_id: str) -> dict[str, Any] | None:
    return registry.get_schema(source_id)


def list_sources() -> list[dict[str, Any]]:
    return registry.list_sources()


def remove_source(source_id: str) -> bool:
    return registry.remove(source_id)


# ── LangChain tool ────────────────────────────────────────────────────────────

class SpreadsheetQueryInput(BaseModel):
    source_id: str = Field(..., description="The source_id returned when the spreadsheet was uploaded.")
    question: str = Field("", description="Free-text keyword to search across all string columns.")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Column→value filter dict (exact match, case-insensitive). E.g. {'region': 'North'}.",
    )
    limit: int = Field(100, ge=1, le=5000, description="Maximum rows to return.")


def _query_tool(
    source_id: str,
    question: str = "",
    filters: dict[str, Any] | None = None,
    limit: int = 100,
) -> dict[str, Any]:
    return query_spreadsheet(source_id, question, filters or {}, limit)


spreadsheet_query_tool = StructuredTool.from_function(
    name="spreadsheet_query",
    description=(
        "Query an in-session uploaded spreadsheet (Excel or CSV). "
        "Pass the source_id returned by the upload endpoint, an optional "
        "keyword question to filter rows, and optional column=value filters. "
        "Returns matching rows with column names."
    ),
    func=_query_tool,
    args_schema=SpreadsheetQueryInput,
)
