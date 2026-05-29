from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.cache.enhanced_query_cache import get_cached_result, set_cached_result
from app.core.error_handler import structured_error, with_retry
from app.core.exceptions import QueryValidationError
from app.db.azure_sql import execute_select
from app.text2sql.validator import validate_select_query

_RETRYABLE = (OSError, TimeoutError)


class SQLExecutorInput(BaseModel):
    sql: str = Field(..., description="A read-only Azure SQL Database T-SQL SELECT query.")


@with_retry(max_attempts=3, delay_seconds=0.5, retryable_exceptions=_RETRYABLE)
def _execute_with_retry(safe_sql: str) -> dict[str, Any]:
    return execute_select(safe_sql)


def run_sql_executor(sql: str) -> dict[str, Any]:
    try:
        safe_sql = validate_select_query(sql)
        cached = get_cached_result(safe_sql)
        if cached is not None:
            return cached

        result = _execute_with_retry(safe_sql)
        payload = {"sql": safe_sql, **result, "from_cache": False}
        set_cached_result(safe_sql, payload)
        return payload
    except QueryValidationError as exc:
        return structured_error(
            tool="sql_executor",
            message=str(exc),
            error_type="ValidationError",
            suggestion="Check that the query is a read-only SELECT statement with no forbidden keywords.",
        )
    except Exception as exc:
        return structured_error(
            tool="sql_executor",
            message=f"SQL execution failed: {exc}",
            error_type="DBError",
            retries_attempted=3,
            suggestion="Verify the SQL syntax and that the target table exists in the database.",
        )


sql_executor_tool = StructuredTool.from_function(
    name="sql_executor",
    description=(
        "Execute a safe read-only T-SQL SELECT query against the Azure SQL analytics database. "
        "Use this after generating SQL from the user's BI question."
    ),
    func=run_sql_executor,
    args_schema=SQLExecutorInput,
)
