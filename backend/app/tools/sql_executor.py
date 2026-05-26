from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.cache.enhanced_query_cache import get_cached_result, set_cached_result
from app.core.exceptions import QueryValidationError
from app.db.azure_sql import execute_select
from app.text2sql.validator import validate_select_query


class SQLExecutorInput(BaseModel):
    sql: str = Field(..., description="A read-only Azure SQL Database T-SQL SELECT query.")


def run_sql_executor(sql: str) -> dict[str, Any]:
    try:
        safe_sql = validate_select_query(sql)
        cached = get_cached_result(safe_sql)
        if cached is not None:
            return cached

        result = execute_select(safe_sql)
        payload = {"sql": safe_sql, **result, "from_cache": False}
        set_cached_result(safe_sql, payload)
        return payload
    except QueryValidationError as exc:
        return {"error": str(exc), "from_cache": False}
    except Exception as exc:
        return {"error": f"SQL execution failed: {exc}", "from_cache": False}


sql_executor_tool = StructuredTool.from_function(
    name="sql_executor",
    description=(
        "Execute a safe read-only T-SQL SELECT query against the Azure SQL analytics database. "
        "Use this after generating SQL from the user's BI question."
    ),
    func=run_sql_executor,
    args_schema=SQLExecutorInput,
)
