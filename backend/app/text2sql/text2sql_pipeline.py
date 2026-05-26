"""
US-08: Schema-Aware Text2SQL Pipeline
--------------------------------------
Converts natural language questions into Azure SQL T-SQL SELECT queries
by injecting the live database schema into the prompt and calling Groq LLM.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_groq import ChatGroq

from app.core.config import settings
from app.text2sql.schema_registry import format_schema_for_prompt, load_database_schema
from app.text2sql.validator import validate_select_query

logger = logging.getLogger(__name__)

# ── Prompt templates ──────────────────────────────────────────────────────────

TEXT2SQL_SYSTEM_PROMPT = """
You are an expert Azure SQL Database query generator for a real-time streaming analytics platform.

RULES:
- Output ONLY a valid T-SQL SELECT query — no explanation, no markdown, no code fences.
- Use T-SQL syntax: TOP instead of LIMIT, GETDATE() for current timestamp, ISNULL() not COALESCE.
- Only generate read-only SELECT queries. Never INSERT, UPDATE, DELETE, DROP, ALTER, or EXEC.
- Always qualify table names with their schema (e.g. dbo.orders, not just orders).
- When filtering dates use DATEADD and GETDATE() (e.g. DATEADD(day, -7, GETDATE())).
- When aggregating add a GROUP BY for all non-aggregated columns in SELECT.
- For pagination use OFFSET … ROWS FETCH NEXT … ROWS ONLY or TOP.
- If the question is ambiguous choose the most likely interpretation from the schema.

DATABASE SCHEMA:
{schema}
"""

TEXT2SQL_USER_PROMPT = """
Generate a T-SQL SELECT query for the following question:
{question}

Context from prior conversation (if any):
{context}
"""


# ── Core pipeline ─────────────────────────────────────────────────────────────

class Text2SQLPipeline:
    """
    Schema-aware pipeline that turns a natural language question into
    a validated, executable T-SQL SELECT query.
    """

    def __init__(self) -> None:
        self._schema_text: str | None = None

    # ── Schema helpers ────────────────────────────────────────────────────────

    def _get_schema(self) -> str:
        """Load (and cache in process) the live database schema."""
        if self._schema_text is None:
            try:
                schema = load_database_schema()
                self._schema_text = format_schema_for_prompt(schema)
                logger.info("Text2SQL: loaded schema (%d tables)", len(schema))
            except Exception as exc:
                logger.warning("Text2SQL: could not load schema: %s", exc)
                self._schema_text = "Schema unavailable — write generic T-SQL."
        return self._schema_text

    def refresh_schema(self) -> None:
        """Force a schema reload on the next call (e.g. after DDL changes)."""
        self._schema_text = None

    # ── SQL extraction ────────────────────────────────────────────────────────

    @staticmethod
    def _extract_sql(raw: str) -> str:
        """
        Strip markdown code fences or prose around the SQL that the LLM
        sometimes wraps the query in, even when asked not to.
        """
        # Remove ```sql ... ``` or ``` ... ```
        fenced = re.search(r"```(?:sql)?\s*([\s\S]+?)```", raw, re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        # Grab the first SELECT statement if there's surrounding prose
        select_match = re.search(r"(SELECT[\s\S]+)", raw, re.IGNORECASE)
        if select_match:
            return select_match.group(1).strip()
        return raw.strip()

    # ── Main entry point ──────────────────────────────────────────────────────

    def generate(
        self,
        question: str,
        context: str = "",
    ) -> dict[str, Any]:
        """
        Generate and validate a T-SQL SELECT query from a natural language question.

        Returns:
            {
                "sql":     str   – validated, ready-to-run query
                "raw":     str   – raw LLM output before extraction
                "schema":  str   – schema snapshot used
                "error":   str | None
            }
        """
        if not settings.GROQ_API_KEY:
            return {
                "sql": None,
                "raw": None,
                "schema": None,
                "error": "GROQ_API_KEY is not configured.",
            }

        schema_text = self._get_schema()

        system_msg = SystemMessage(
            content=TEXT2SQL_SYSTEM_PROMPT.format(schema=schema_text)
        )
        user_msg = HumanMessage(
            content=TEXT2SQL_USER_PROMPT.format(
                question=question,
                context=context or "None",
            )
        )

        try:
            llm = ChatGroq(
                model=settings.GROQ_MODEL,
                temperature=0,
                api_key=settings.GROQ_API_KEY,
            )
            response = llm.invoke([system_msg, user_msg])
            raw_sql = response.content.strip()
        except Exception as exc:
            logger.error("Text2SQL LLM call failed: %s", exc)
            return {"sql": None, "raw": None, "schema": schema_text, "error": str(exc)}

        extracted = self._extract_sql(raw_sql)

        try:
            validated_sql = validate_select_query(extracted)
        except Exception as exc:
            logger.warning("Text2SQL validation failed: %s | sql=%s", exc, extracted)
            return {
                "sql": None,
                "raw": raw_sql,
                "schema": schema_text,
                "error": f"Generated SQL failed validation: {exc}",
            }

        logger.info("Text2SQL: generated SQL: %s", validated_sql)
        return {
            "sql": validated_sql,
            "raw": raw_sql,
            "schema": schema_text,
            "error": None,
        }


# Module-level singleton
text2sql_pipeline = Text2SQLPipeline()
