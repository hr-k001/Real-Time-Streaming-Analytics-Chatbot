from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class DataSummarizerInput(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Tabular rows to summarize.")
    max_examples: int = Field(3, ge=1, le=10)


def summarize_data(data: list[dict[str, Any]], max_examples: int = 3) -> dict[str, Any]:
    try:
        if not data:
            return {"summary": "No rows returned.", "row_count": 0, "columns": []}

        columns = list(data[0].keys())
        numeric_stats: dict[str, dict[str, float]] = {}
        for column in columns:
            values = [row.get(column) for row in data if isinstance(row.get(column), int | float)]
            if values:
                numeric_stats[column] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": round(sum(values) / len(values), 2),
                    "total": round(sum(values), 2),
                }

        return {
            "summary": f"Returned {len(data)} rows across {len(columns)} columns.",
            "row_count": len(data),
            "columns": columns,
            "numeric_stats": numeric_stats,
            "examples": data[:max_examples],
        }
    except Exception as exc:
        return {"error": f"Data summarization failed: {exc}"}


data_summarizer_tool = StructuredTool.from_function(
    name="data_summarizer",
    description="Summarize tabular data, including row count, columns, examples, and numeric statistics.",
    func=summarize_data,
    args_schema=DataSummarizerInput,
)
