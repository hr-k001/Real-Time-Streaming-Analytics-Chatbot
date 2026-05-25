from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Iterator

import pyodbc

from app.core.config import settings


@contextmanager
def get_connection() -> Iterator[pyodbc.Connection]:
    conn = pyodbc.connect(settings.azure_sql_connection_string, timeout=settings.AZURE_SQL_TIMEOUT_SECONDS)
    try:
        yield conn
    finally:
        conn.close()


def execute_select(sql: str, max_rows: int | None = None) -> dict[str, Any]:
    row_limit = max_rows or settings.SQL_MAX_ROWS
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(sql)
        columns = [column[0] for column in cursor.description or []]
        rows = cursor.fetchmany(row_limit + 1)
        truncated = len(rows) > row_limit
        safe_rows = rows[:row_limit]
        return {
            "columns": columns,
            "rows": [dict(zip(columns, row)) for row in safe_rows],
            "row_count": len(safe_rows),
            "truncated": truncated,
        }
