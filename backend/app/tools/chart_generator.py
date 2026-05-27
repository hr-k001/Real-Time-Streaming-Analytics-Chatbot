from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

ChartType = Literal["auto", "bar", "line", "scatter", "pie"]


class ChartGeneratorInput(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Tabular query result rows.")
    x: str | None = Field(None, description="Column to use for the x-axis or labels.")
    y: str | None = Field(None, description="Column to use for the y-axis or values.")
    chart_type: ChartType = "auto"
    title: str = "Analytics Result"


def _numeric_columns(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return [key for key, value in rows[0].items() if isinstance(value, int | float)]


def _categorical_columns(rows: list[dict[str, Any]]) -> list[str]:
    if not rows:
        return []
    return [key for key, value in rows[0].items() if not isinstance(value, int | float)]


def generate_chart(
    data: list[dict[str, Any]],
    x: str | None = None,
    y: str | None = None,
    chart_type: ChartType = "auto",
    title: str = "Analytics Result",
) -> dict[str, Any]:
    from app.core.error_handler import structured_error

    try:
        if not data:
            return structured_error(
                tool="chart_generator",
                message="No data provided for chart generation.",
                error_type="EmptyDataError",
                suggestion="Ensure the SQL query returns at least one row before generating a chart.",
            )

        numeric = _numeric_columns(data)
        categorical = _categorical_columns(data)
        x_col = x or (categorical[0] if categorical else next(iter(data[0].keys())))
        y_col = y or (numeric[0] if numeric else None)
        if not y_col:
            return structured_error(
                tool="chart_generator",
                message="No numeric column found for chart values.",
                error_type="NoNumericColumn",
                suggestion="Make sure the query result includes at least one numeric (int/float) column.",
                retries_attempted=0,
            )

        selected = chart_type
        if selected == "auto":
            if len(data) <= 6 and x_col in categorical:
                selected = "pie"
            elif any(token in x_col.lower() for token in ["date", "month", "year", "time"]):
                selected = "line"
            else:
                selected = "bar"

        labels = [row.get(x_col) for row in data]
        values = [row.get(y_col) for row in data]

        if selected == "pie":
            traces = [{"type": "pie", "labels": labels, "values": values}]
        else:
            traces = [{"type": selected, "x": labels, "y": values, "mode": "markers" if selected == "scatter" else None}]
            traces[0] = {key: value for key, value in traces[0].items() if value is not None}

        return {
            "chart_type": selected,
            "figure": {
                "data": traces,
                "layout": {
                    "title": title,
                    "xaxis": {"title": x_col},
                    "yaxis": {"title": y_col},
                    "template": "plotly_white",
                },
            },
        }
    except Exception as exc:
        return structured_error(
            tool="chart_generator",
            message=f"Chart generation failed: {exc}",
            error_type="RenderError",
            suggestion="Try specifying explicit x and y column names, or use the data_summarizer tool to inspect the data shape first.",
        )


chart_generator_tool = StructuredTool.from_function(
    name="chart_generator",
    description="Generate a Plotly.js figure spec from tabular data with automatic chart type selection.",
    func=generate_chart,
    args_schema=ChartGeneratorInput,
)
