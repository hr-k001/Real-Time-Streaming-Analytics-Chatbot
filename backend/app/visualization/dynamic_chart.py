"""
US-11: Dynamic Chart Selection
--------------------------------
Analyses query results and the user's question to automatically select
the most appropriate Plotly chart type, then returns a full Plotly figure spec.

Extends Himanshu's chart_generator with intelligent chart-type detection.
"""
from __future__ import annotations

import logging
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

ChartType = Literal["bar", "line", "scatter", "pie", "area", "histogram", "heatmap", "funnel"]

# ── Detection heuristics ──────────────────────────────────────────────────────

# Keywords in the user question that suggest a chart type
QUESTION_HINTS: list[tuple[frozenset[str], ChartType]] = [
    (frozenset({"trend", "over time", "timeline", "daily", "monthly", "weekly", "hourly", "growth"}), "line"),
    (frozenset({"distribution", "spread", "histogram", "frequency"}), "histogram"),
    (frozenset({"share", "proportion", "percentage", "breakdown", "composition"}), "pie"),
    (frozenset({"correlation", "relationship", "vs", "versus", "compare", "scatter"}), "scatter"),
    (frozenset({"funnel", "conversion", "stage", "pipeline"}), "funnel"),
    (frozenset({"heatmap", "matrix", "cross", "by hour", "by day"}), "heatmap"),
    (frozenset({"area", "cumulative", "running total"}), "area"),
]


def _numeric_columns(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return [k for k, v in rows[0].items() if isinstance(v, (int, float))]


def _categorical_columns(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return [k for k, v in rows[0].items() if not isinstance(v, (int, float))]


def _looks_temporal(col_name: str) -> bool:
    tokens = {"date", "time", "month", "year", "day", "hour", "week", "period", "ts", "timestamp"}
    return any(t in col_name.lower() for t in tokens)


# ── Core selection logic ──────────────────────────────────────────────────────

def select_chart_type(
    rows: list[dict[str, Any]],
    question: str = "",
    x_col: str | None = None,
) -> ChartType:
    """
    Heuristically choose the best chart type.

    Priority:
      1. Explicit keyword hints in the user's question
      2. Data shape (temporal x-axis → line, few categories → pie, else bar)
    """
    q_lower = question.lower()

    # 1. Question keyword scan
    for hint_words, chart_type in QUESTION_HINTS:
        if any(hw in q_lower for hw in hint_words):
            return chart_type

    # 2. Data shape
    categorical = _categorical_columns(rows)
    x = x_col or (categorical[0] if categorical else "")

    if _looks_temporal(x):
        return "line"
    if len(rows) <= 6 and categorical:
        return "pie"
    return "bar"


# ── Plotly figure builder ─────────────────────────────────────────────────────

def _build_figure(
    rows: list[dict[str, Any]],
    chart_type: ChartType,
    x_col: str,
    y_col: str,
    title: str,
    color_col: str | None,
) -> dict[str, Any]:
    """Construct a Plotly-compatible figure dict."""
    labels = [row.get(x_col) for row in rows]
    values = [row.get(y_col) for row in rows]
    colors = [row.get(color_col) for row in rows] if color_col else None

    layout: dict[str, Any] = {
        "title": {"text": title, "font": {"size": 18}},
        "template": "plotly_white",
        "xaxis": {"title": x_col},
        "yaxis": {"title": y_col},
        "legend": {"orientation": "h"},
    }

    if chart_type == "pie":
        trace: dict[str, Any] = {
            "type": "pie",
            "labels": labels,
            "values": values,
            "hole": 0.3,        # donut style — more readable for BI
            "textinfo": "percent+label",
        }
        layout.pop("xaxis", None)
        layout.pop("yaxis", None)

    elif chart_type == "histogram":
        trace = {"type": "histogram", "x": values, "name": y_col}

    elif chart_type == "scatter":
        trace = {
            "type": "scatter",
            "mode": "markers",
            "x": labels,
            "y": values,
            "marker": {"size": 10, "color": colors or "royalblue"},
        }

    elif chart_type == "area":
        trace = {
            "type": "scatter",
            "mode": "lines",
            "fill": "tozeroy",
            "x": labels,
            "y": values,
            "line": {"color": "royalblue"},
        }

    elif chart_type == "funnel":
        trace = {"type": "funnel", "y": labels, "x": values}
        layout.pop("xaxis", None)
        layout.pop("yaxis", None)

    elif chart_type == "heatmap":
        # Pivot first two categorical + first numeric columns
        trace = {
            "type": "heatmap",
            "z": [values],
            "x": labels,
            "colorscale": "Blues",
        }

    else:  # bar or line
        trace = {
            "type": "bar" if chart_type == "bar" else "scatter",
            "x": labels,
            "y": values,
            "name": y_col,
        }
        if chart_type == "line":
            trace["mode"] = "lines+markers"

    return {"data": [trace], "layout": layout}


# ── Main entry point ──────────────────────────────────────────────────────────

def smart_chart(
    data: list[dict[str, Any]],
    question: str = "",
    x: str | None = None,
    y: str | None = None,
    chart_type: str = "auto",
    title: str = "Analytics Result",
    color_col: str | None = None,
) -> dict[str, Any]:
    """
    Intelligently select a chart type and produce a Plotly figure spec.

    Returns:
        {"chart_type": str, "figure": {...plotly figure dict...}}
        or {"error": str}
    """
    try:
        if not data:
            return {"error": "No data provided for chart generation."}

        numeric = _numeric_columns(data)
        categorical = _categorical_columns(data)
        x_col = x or (categorical[0] if categorical else next(iter(data[0].keys())))
        y_col = y or (numeric[0] if numeric else None)

        if not y_col and chart_type not in ("histogram",):
            return {"error": "No numeric column found for the y-axis / values."}

        # Resolve chart type
        if chart_type == "auto":
            resolved: ChartType = select_chart_type(data, question, x_col)
        else:
            resolved = chart_type  # type: ignore[assignment]

        figure = _build_figure(data, resolved, x_col, y_col or x_col, title, color_col)
        return {"chart_type": resolved, "figure": figure}

    except Exception as exc:
        logger.exception("smart_chart failed")
        return {"error": f"Chart generation failed: {exc}"}


# ── LangChain StructuredTool ──────────────────────────────────────────────────

class DynamicChartInput(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Tabular query result rows.")
    question: str = Field("", description="Original user question to help infer chart type.")
    x: str | None = Field(None, description="X-axis / label column.")
    y: str | None = Field(None, description="Y-axis / value column.")
    chart_type: str = Field("auto", description="Force a chart type or use 'auto' to detect.")
    title: str = Field("Analytics Result", description="Chart title.")
    color_col: str | None = Field(None, description="Optional column to use for marker colour.")


dynamic_chart_tool = StructuredTool.from_function(
    name="dynamic_chart",
    description=(
        "Intelligently select a Plotly chart type from the data shape and the user's question, "
        "then return a full Plotly figure spec. "
        "Supports: bar, line, scatter, pie, area, histogram, heatmap, funnel. "
        "Use chart_type='auto' (default) for automatic selection."
    ),
    func=smart_chart,
    args_schema=DynamicChartInput,
)
