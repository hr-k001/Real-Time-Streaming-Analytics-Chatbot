"""
routes_data_sources.py
-----------------------
Feature 2: Spreadsheet / data source integration endpoints.

  POST   /api/upload/spreadsheet           — Upload Excel or CSV file
  GET    /api/data-sources                 — List all loaded sources
  GET    /api/data-sources/{source_id}     — Schema for one source
  DELETE /api/data-sources/{source_id}     — Remove a source
  POST   /api/data-sources/{source_id}/query — Direct query (no LLM)
"""
from typing import Any

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.data_sources.spreadsheet_handler import (
    get_schema,
    list_sources,
    load_spreadsheet,
    query_spreadsheet,
    remove_source,
)

router = APIRouter(tags=["data-sources"])


# ── Upload ─────────────────────────────────────────────────────────────────────

@router.post("/upload/spreadsheet")
async def upload_spreadsheet(file: UploadFile = File(...)) -> dict[str, Any]:
    """Upload an Excel (.xlsx/.xls) or CSV file. Returns a source_id for subsequent queries."""
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    source_id = load_spreadsheet(content, file.filename or "upload.csv")
    schema = get_schema(source_id)
    return {
        "source_id": source_id,
        "filename": file.filename,
        "row_count": schema["row_count"] if schema else 0,
        "columns": schema["columns"] if schema else [],
        "message": "Spreadsheet loaded successfully.",
    }


# ── List / inspect ─────────────────────────────────────────────────────────────

@router.get("/data-sources")
def list_data_sources() -> dict[str, Any]:
    """List all currently loaded spreadsheet sources."""
    sources = list_sources()
    return {"count": len(sources), "sources": sources}


@router.get("/data-sources/{source_id}")
def get_data_source(source_id: str) -> dict[str, Any]:
    """Return column names and dtypes for one uploaded spreadsheet."""
    schema = get_schema(source_id)
    if schema is None:
        raise HTTPException(status_code=404, detail=f"source_id '{source_id}' not found.")
    return schema


# ── Delete ─────────────────────────────────────────────────────────────────────

@router.delete("/data-sources/{source_id}")
def delete_data_source(source_id: str) -> dict[str, str]:
    """Remove an uploaded spreadsheet from the in-session registry."""
    removed = remove_source(source_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"source_id '{source_id}' not found.")
    return {"status": "removed", "source_id": source_id}


# ── Direct query (no LLM) ──────────────────────────────────────────────────────

class QueryRequest(BaseModel):
    question: str = Field("", description="Free-text keyword to search string columns.")
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Column→value filter dict (exact match, case-insensitive).",
    )
    limit: int = Field(100, ge=1, le=5000)


@router.post("/data-sources/{source_id}/query")
def query_data_source(source_id: str, request: QueryRequest) -> dict[str, Any]:
    """Query an uploaded spreadsheet directly without the LLM agent."""
    result = query_spreadsheet(
        source_id,
        question=request.question,
        filters=request.filters,
        limit=request.limit,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result
