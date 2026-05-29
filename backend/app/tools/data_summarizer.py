from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field


class DataSummarizerInput(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Tabular rows to summarize.")
    max_examples: int = Field(3, ge=1, le=10)


def summarize_data(data: list[dict[str, Any]], max_examples: int = 3) -> dict[str, Any]:
    from app.core.error_handler import structured_error

    try:
        if not data:
            return {"summary": "No rows returned.", "row_count": 0, "columns": []}

        # Filter out completely None/empty rows before processing
        valid_rows = [row for row in data if isinstance(row, dict)]
        if not valid_rows:
            return {"summary": "All rows were malformed (not dicts).", "row_count": 0, "columns": []}

        columns = list(valid_rows[0].keys())
        numeric_stats: dict[str, dict[str, float]] = {}
        for column in columns:
            # Exclude None, NaN-like strings, and non-numeric values
            values = [
                row.get(column)
                for row in valid_rows
                if isinstance(row.get(column), (int, float))
                and row.get(column) == row.get(column)  # NaN check (NaN != NaN)
            ]
            if values:
                numeric_stats[column] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": round(sum(values) / len(values), 2),
                    "total": round(sum(values), 2),
                    "non_null_count": len(values),
                }

        null_counts = {
            col: sum(1 for row in valid_rows if row.get(col) is None)
            for col in columns
        }

        return {
            "summary": f"Returned {len(valid_rows)} rows across {len(columns)} columns.",
            "row_count": len(valid_rows),
            "columns": columns,
            "numeric_stats": numeric_stats,
            "null_counts": {col: n for col, n in null_counts.items() if n > 0},
            "examples": valid_rows[:max_examples],
        }
    except Exception as exc:
        return structured_error(
            tool="data_summarizer",
            message=f"Data summarization failed: {exc}",
            error_type="SummaryError",
            suggestion="Ensure the input data is a list of dicts with consistent keys.",
        )


data_summarizer_tool = StructuredTool.from_function(
    name="data_summarizer",
    description="Summarize tabular data, including row count, columns, examples, and numeric statistics.",
    func=summarize_data,
    args_schema=DataSummarizerInput,
)
