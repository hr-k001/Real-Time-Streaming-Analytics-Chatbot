"""
US-12: Plotly Visualization Integration
-----------------------------------------
Provides server-side Plotly figure helpers and a FastAPI route that
returns ready-to-render Plotly JSON consumed by the React frontend.

Also exposes a LangChain tool so the agent can request richer figures.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.visualization.dynamic_chart import smart_chart, _numeric_columns, _categorical_columns
from app.visualization.data_shapes import coerce_rows

logger = logging.getLogger(__name__)

# ── Color palettes ────────────────────────────────────────────────────────────

PALETTES: dict[str, list[str]] = {
    "default":  ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A", "#19D3F3", "#FF6692"],
    "blue":     ["#1f77b4", "#aec7e8", "#4393c3", "#2166ac", "#053061"],
    "green":    ["#2ca02c", "#98df8a", "#41ab5d", "#238b45", "#005a32"],
    "warm":     ["#d62728", "#ff9896", "#e6550d", "#fd8d3c", "#fdae6b"],
    "pastel":   ["#AED6F1", "#A9DFBF", "#F9E79F", "#F1948A", "#D7BDE2"],
}


def apply_theme(
    figure: dict[str, Any],
    palette: str = "default",
    dark_mode: bool = False,
) -> dict[str, Any]:
    """
    Apply a colour palette and optional dark-mode background to a Plotly figure.
    Mutates and returns the figure dict.
    """
    colors = PALETTES.get(palette, PALETTES["default"])
    layout = figure.setdefault("layout", {})

    if dark_mode:
        layout["paper_bgcolor"] = "#1e1e2e"
        layout["plot_bgcolor"]  = "#1e1e2e"
        layout["font"] = {"color": "#cdd6f4"}
    else:
        layout["paper_bgcolor"] = "white"
        layout["plot_bgcolor"]  = "white"

    layout["colorway"] = colors
    layout.setdefault("margin", {"l": 60, "r": 30, "t": 60, "b": 60})
    layout.setdefault("hovermode", "x unified")

    return figure


def figure_to_json(figure: dict[str, Any]) -> str:
    """Serialise a Plotly figure dict to a compact JSON string."""
    return json.dumps(figure, default=str)


# ── Grouped/multi-series builder ──────────────────────────────────────────────

def build_multi_series_figure(
    rows: list[dict[str, Any]],
    x_col: str,
    y_cols: list[str],
    chart_type: Literal["bar", "line", "scatter"] = "bar",
    title: str = "Multi-Series Chart",
    palette: str = "default",
    dark_mode: bool = False,
) -> dict[str, Any]:
    """
    Build a Plotly figure with multiple Y series (one trace per y_col).

    Useful for comparing metrics like 'revenue vs profit vs cost' in one chart.
    """
    colors = PALETTES.get(palette, PALETTES["default"])
    labels = [row.get(x_col) for row in rows]
    traces: list[dict[str, Any]] = []

    for i, col in enumerate(y_cols):
        values = [row.get(col) for row in rows]
        trace: dict[str, Any] = {
            "name": col,
            "x": labels,
            "y": values,
            "marker": {"color": colors[i % len(colors)]},
        }
        if chart_type == "bar":
            trace["type"] = "bar"
        elif chart_type == "line":
            trace["type"] = "scatter"
            trace["mode"] = "lines+markers"
        else:
            trace["type"] = "scatter"
            trace["mode"] = "markers"
        traces.append(trace)

    layout: dict[str, Any] = {
        "title": {"text": title, "font": {"size": 18}},
        "barmode": "group" if chart_type == "bar" else None,
        "xaxis": {"title": x_col},
        "yaxis": {"title": "Value"},
        "template": "plotly_white",
        "legend": {"orientation": "h", "y": -0.2},
        "hovermode": "x unified",
    }
    # Remove None values
    layout = {k: v for k, v in layout.items() if v is not None}

    figure = {"data": traces, "layout": layout}
    return apply_theme(figure, palette, dark_mode)


# ── LangChain StructuredTool ──────────────────────────────────────────────────

class PlotlyVizInput(BaseModel):
    data: Any = Field(..., description="Tabular rows or a SQL result object containing rows.")
    question: str = Field("", description="User question to aid chart type selection.")
    x: str | None = Field(None, description="X-axis column.")
    y_cols: list[str] | None = Field(None, description="One or more Y-axis columns (multi-series if >1). Optional — auto-detected if omitted.")
    chart_type: str = Field("auto", description="Chart type or 'auto'.")
    title: str = Field("Analytics Result", description="Chart title.")
    palette: str = Field("default", description="Color palette: default, blue, green, warm, pastel.")
    dark_mode: bool = Field(False, description="Use dark background.")


def build_plotly_viz(
    data: Any,
    question: str = "",
    x: str | None = None,
    y_cols: list[str] | None = None,
    chart_type: str = "auto",
    title: str = "Analytics Result",
    palette: str = "default",
    dark_mode: bool = False,
) -> dict[str, Any]:
    """
    Build a Plotly visualization with theming.

    - If y_cols has >1 entry, builds a multi-series chart.
    - Otherwise delegates to smart_chart for automatic type selection.
    """
    try:
        rows = coerce_rows(data)
        if not data:
            return {"error": "No data provided."}
        if not rows:
            return {"error": "Visualization data must be rows or a SQL result object containing rows."}

        if y_cols and len(y_cols) > 1:
            numeric = _numeric_columns(rows)
            categorical = _categorical_columns(rows)
            x_col = x or (categorical[0] if categorical else next(iter(rows[0].keys())))
            ct: Literal["bar", "line", "scatter"] = (
                "line" if chart_type in ("line", "area") else
                "scatter" if chart_type == "scatter" else "bar"
            )
            figure = build_multi_series_figure(
                rows=rows, x_col=x_col, y_cols=y_cols,
                chart_type=ct, title=title, palette=palette, dark_mode=dark_mode,
            )
            return {"chart_type": ct, "multi_series": True, "figure": figure}

        # Single series via smart_chart
        y = y_cols[0] if y_cols else None
        result = smart_chart(data=rows, question=question, x=x, y=y,
                             chart_type=chart_type, title=title)
        if "error" in result:
            return result

        result["figure"] = apply_theme(result["figure"], palette, dark_mode)
        result["multi_series"] = False
        return result

    except Exception as exc:
        logger.exception("build_plotly_viz failed")
        return {"error": f"Plotly visualization failed: {exc}"}


plotly_viz_tool = StructuredTool.from_function(
    name="plotly_viz",
    description=(
        "Build a fully themed Plotly.js figure (single or multi-series). "
        "Supports bar, line, scatter, pie, area, histogram, heatmap, funnel. "
        "Returns a Plotly figure JSON spec ready for the frontend React component."
    ),
    func=build_plotly_viz,
    args_schema=PlotlyVizInput,
)
