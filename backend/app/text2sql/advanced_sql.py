"""
US-10: Advanced SQL Support
-----------------------------
Provides helpers for complex T-SQL patterns:
  - Multi-table JOINs
  - Aggregations (GROUP BY, HAVING, window functions)
  - Subquery / CTE rewriting
  - Date-range sugar for common analytics windows
  - LangChain StructuredTool for agent use
"""
from __future__ import annotations

import logging
import re
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.text2sql.query_validator import query_validator
from app.core.exceptions import QueryValidationError

logger = logging.getLogger(__name__)

# ── Date range helpers ────────────────────────────────────────────────────────

DATE_WINDOWS: dict[str, str] = {
    "today":        "CAST(GETDATE() AS DATE) = CAST({col} AS DATE)",
    "yesterday":    "CAST(DATEADD(day,-1,GETDATE()) AS DATE) = CAST({col} AS DATE)",
    "last_7_days":  "{col} >= DATEADD(day,-7,GETDATE())",
    "last_30_days": "{col} >= DATEADD(day,-30,GETDATE())",
    "this_month":   "MONTH({col})=MONTH(GETDATE()) AND YEAR({col})=YEAR(GETDATE())",
    "last_month":   "MONTH({col})=MONTH(DATEADD(month,-1,GETDATE())) AND YEAR({col})=YEAR(DATEADD(month,-1,GETDATE()))",
    "this_year":    "YEAR({col})=YEAR(GETDATE())",
    "last_year":    "YEAR({col})=YEAR(GETDATE())-1",
}


def build_date_filter(column: str, window: str) -> str:
    """
    Return a T-SQL WHERE fragment for a named time window.

    >>> build_date_filter("order_date", "last_7_days")
    'order_date >= DATEADD(day,-7,GETDATE())'
    """
    template = DATE_WINDOWS.get(window)
    if template is None:
        supported = ", ".join(DATE_WINDOWS.keys())
        raise ValueError(f"Unknown date window '{window}'. Supported: {supported}")
    return template.format(col=column)


# ── Aggregation builder ───────────────────────────────────────────────────────

AggFunc = Literal["SUM", "COUNT", "AVG", "MIN", "MAX", "COUNT_DISTINCT"]


def build_aggregation_query(
    table: str,
    metric_col: str,
    agg_func: AggFunc,
    group_by_cols: list[str],
    where_clause: str = "",
    having_clause: str = "",
    top_n: int = 100,
    order_desc: bool = True,
) -> str:
    """
    Build a GROUP BY aggregation query without touching raw SQL strings directly.

    Args:
        table:          Fully qualified table name, e.g. 'dbo.orders'
        metric_col:     Column to aggregate, e.g. 'revenue'
        agg_func:       Aggregation function
        group_by_cols:  List of columns to group by
        where_clause:   Optional raw WHERE condition (will be validated)
        having_clause:  Optional raw HAVING condition
        top_n:          Row limit (injected via TOP)
        order_desc:     Sort the metric descending

    Returns:
        A validated T-SQL SELECT query string.
    """
    if agg_func == "COUNT_DISTINCT":
        agg_expr = f"COUNT(DISTINCT {metric_col})"
    else:
        agg_expr = f"{agg_func}({metric_col})"

    alias = f"{agg_func.lower()}_{metric_col.replace('.', '_')}"
    select_cols = ", ".join(group_by_cols) + f", {agg_expr} AS {alias}"
    group_by = ", ".join(group_by_cols)
    order_dir = "DESC" if order_desc else "ASC"

    parts = [
        f"SELECT TOP {top_n} {select_cols}",
        f"FROM {table}",
    ]
    if where_clause:
        parts.append(f"WHERE {where_clause}")
    parts.append(f"GROUP BY {group_by}")
    if having_clause:
        parts.append(f"HAVING {having_clause}")
    parts.append(f"ORDER BY {alias} {order_dir}")

    sql = "\n".join(parts)
    return query_validator.validate_or_raise(sql)


# ── Window function builder ───────────────────────────────────────────────────

def build_window_function_query(
    table: str,
    metric_col: str,
    partition_cols: list[str],
    order_col: str,
    window_func: Literal["ROW_NUMBER", "RANK", "DENSE_RANK", "LAG", "LEAD", "SUM", "AVG"] = "ROW_NUMBER",
    top_n: int = 200,
) -> str:
    """
    Build a T-SQL query with an OVER() window function.

    Example output:
        SELECT TOP 200 region, sale_date, revenue,
               SUM(revenue) OVER (PARTITION BY region ORDER BY sale_date) AS window_sum
        FROM dbo.sales
    """
    partition = ", ".join(partition_cols)
    alias = f"{window_func.lower()}_result"

    if window_func in ("ROW_NUMBER", "RANK", "DENSE_RANK"):
        over_expr = (
            f"{window_func}() OVER (PARTITION BY {partition} ORDER BY {order_col})"
        )
    else:
        over_expr = (
            f"{window_func}({metric_col}) OVER (PARTITION BY {partition} ORDER BY {order_col})"
        )

    select_cols = ", ".join(partition_cols) + f", {order_col}, {metric_col}, {over_expr} AS {alias}"
    sql = f"SELECT TOP {top_n} {select_cols}\nFROM {table}\nORDER BY {', '.join(partition_cols)}, {order_col}"
    return query_validator.validate_or_raise(sql)


# ── CTE builder ───────────────────────────────────────────────────────────────

def build_cte_query(cte_name: str, cte_body: str, outer_query: str) -> str:
    """
    Wrap a subquery as a CTE and combine with an outer SELECT.

    Args:
        cte_name:    Name for the CTE (e.g. 'ranked_sales')
        cte_body:    The inner SELECT without WITH/AS wrapper
        outer_query: The main SELECT that references the CTE
    """
    # Strip leading SELECT from cte_body if present — it's already implied
    sql = f"WITH {cte_name} AS (\n{cte_body.strip()}\n)\n{outer_query.strip()}"
    return query_validator.validate_or_raise(sql)


# ── JOIN builder ──────────────────────────────────────────────────────────────

JoinType = Literal["INNER", "LEFT", "RIGHT", "FULL OUTER"]


def build_join_query(
    base_table: str,
    joins: list[dict[str, str]],
    select_cols: list[str],
    where_clause: str = "",
    top_n: int = 200,
) -> str:
    """
    Build a multi-table JOIN query.

    Args:
        base_table:  Main table, e.g. 'dbo.orders o'
        joins:       List of dicts with keys: type, table, on
                     e.g. [{"type": "LEFT", "table": "dbo.customers c", "on": "o.customer_id = c.id"}]
        select_cols: Columns to project
        where_clause: Optional WHERE fragment
        top_n:       Row cap
    """
    select_str = ", ".join(select_cols)
    join_str = "\n".join(
        f"{j['type']} JOIN {j['table']} ON {j['on']}" for j in joins
    )
    parts = [f"SELECT TOP {top_n} {select_str}", f"FROM {base_table}", join_str]
    if where_clause:
        parts.append(f"WHERE {where_clause}")
    sql = "\n".join(parts)
    return query_validator.validate_or_raise(sql)


# ── LangChain StructuredTool ──────────────────────────────────────────────────

class AdvancedSQLInput(BaseModel):
    mode: Literal["aggregation", "window", "date_filter", "join"] = Field(
        ..., description="Which SQL helper to invoke."
    )
    table: str = Field("", description="Fully qualified table name (e.g. dbo.orders).")
    metric_col: str = Field("", description="Column to aggregate or apply window function to.")
    agg_func: str = Field("SUM", description="Aggregation function: SUM, COUNT, AVG, MIN, MAX, COUNT_DISTINCT.")
    group_by_cols: list[str] = Field(default_factory=list, description="GROUP BY columns.")
    partition_cols: list[str] = Field(default_factory=list, description="PARTITION BY columns for window functions.")
    order_col: str = Field("", description="ORDER BY column inside OVER() clause.")
    window_func: str = Field("ROW_NUMBER", description="Window function: ROW_NUMBER, RANK, SUM, AVG, LAG, LEAD.")
    date_column: str = Field("", description="Date column for date filter mode.")
    date_window: str = Field("last_7_days", description="Named time window (e.g. last_7_days, this_month).")
    where_clause: str = Field("", description="Optional raw WHERE condition.")
    having_clause: str = Field("", description="Optional raw HAVING condition.")
    top_n: int = Field(100, ge=1, le=500)


def run_advanced_sql(
    mode: str,
    table: str = "",
    metric_col: str = "",
    agg_func: str = "SUM",
    group_by_cols: list[str] | None = None,
    partition_cols: list[str] | None = None,
    order_col: str = "",
    window_func: str = "ROW_NUMBER",
    date_column: str = "",
    date_window: str = "last_7_days",
    where_clause: str = "",
    having_clause: str = "",
    top_n: int = 100,
) -> dict[str, Any]:
    """Dispatch to the appropriate advanced SQL builder."""
    try:
        if mode == "aggregation":
            sql = build_aggregation_query(
                table=table,
                metric_col=metric_col,
                agg_func=agg_func,  # type: ignore[arg-type]
                group_by_cols=group_by_cols or [],
                where_clause=where_clause,
                having_clause=having_clause,
                top_n=top_n,
            )
        elif mode == "window":
            sql = build_window_function_query(
                table=table,
                metric_col=metric_col,
                partition_cols=partition_cols or [],
                order_col=order_col,
                window_func=window_func,  # type: ignore[arg-type]
                top_n=top_n,
            )
        elif mode == "date_filter":
            fragment = build_date_filter(date_column, date_window)
            sql = f"SELECT TOP {top_n} *\nFROM {table}\nWHERE {fragment}"
            sql = query_validator.validate_or_raise(sql)
        else:
            return {"error": f"Unknown mode '{mode}'. Use: aggregation, window, date_filter."}

        return {"sql": sql, "mode": mode}
    except (QueryValidationError, ValueError) as exc:
        return {"error": str(exc)}
    except Exception as exc:
        logger.exception("advanced_sql_tool failed")
        return {"error": f"Advanced SQL failed: {exc}"}


advanced_sql_tool = StructuredTool.from_function(
    name="advanced_sql",
    description=(
        "Build complex T-SQL queries: GROUP BY aggregations, window functions (ROW_NUMBER, LAG, LEAD, SUM OVER), "
        "and date-range filters. Returns a validated, ready-to-run T-SQL SELECT statement."
    ),
    func=run_advanced_sql,
    args_schema=AdvancedSQLInput,
)
