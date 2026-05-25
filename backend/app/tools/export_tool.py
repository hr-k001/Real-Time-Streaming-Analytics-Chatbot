from __future__ import annotations

import csv
import json
import uuid
from pathlib import Path
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.config import settings


class ExportToolInput(BaseModel):
    data: list[dict[str, Any]] = Field(..., description="Rows to export.")
    format: Literal["csv", "json"] = "csv"
    filename_prefix: str = "analytics_export"


def export_data(
    data: list[dict[str, Any]],
    format: Literal["csv", "json"] = "csv",
    filename_prefix: str = "analytics_export",
) -> dict[str, Any]:
    try:
        if not data:
            return {"error": "No data provided for export."}

        export_dir = Path(settings.export_path)
        export_dir.mkdir(parents=True, exist_ok=True)
        safe_prefix = "".join(ch for ch in filename_prefix if ch.isalnum() or ch in ("_", "-")) or "analytics_export"
        filename = f"{safe_prefix}_{uuid.uuid4().hex[:8]}.{format}"
        path = export_dir / filename

        if format == "csv":
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(data[0].keys()))
                writer.writeheader()
                writer.writerows(data)
        else:
            with path.open("w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, default=str)

        return {"file_path": str(path), "format": format, "row_count": len(data)}
    except Exception as exc:
        return {"error": f"Export failed: {exc}"}


export_tool = StructuredTool.from_function(
    name="export_tool",
    description="Export tabular analytics results to CSV or JSON and return the generated file path.",
    func=export_data,
    args_schema=ExportToolInput,
)
