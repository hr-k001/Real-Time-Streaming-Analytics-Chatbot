"""
routes_reports.py
------------------
Feature 4: Natural Language Report Generation endpoints.

  POST /api/reports/generate       — Generate a PDF report for a chat session
  GET  /api/reports/{report_id}    — Download a previously generated PDF
"""
import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.core.config import settings
from app.reports.report_generator import generate_report

router = APIRouter(prefix="/reports", tags=["reports"])


class GenerateReportRequest(BaseModel):
    chat_id: str = Field(..., description="The chat session ID to generate a report for.")
    title: str = Field("", description="Optional report title. Defaults to 'Analytics Report — <chat_id>'.")


@router.post("/generate")
def generate_report_endpoint(request: GenerateReportRequest) -> dict[str, Any]:
    """
    Generate a PDF report for the given chat session.

    The report includes the conversation transcript, last SQL query,
    last data result preview, and chart metadata.
    Returns a report_id and download URL.
    """
    result = generate_report(request.chat_id, request.title)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return {
        "report_id": result["report_id"],
        "title": result["title"],
        "download_url": f"/api/reports/{result['report_id']}",
    }


@router.get("/{report_id}")
def download_report(report_id: str) -> FileResponse:
    """Download a previously generated PDF report by its report_id."""
    reports_dir = getattr(settings, "REPORTS_DIR", "reports")
    path = os.path.join(reports_dir, f"{report_id}.pdf")
    if not os.path.isfile(path):
        raise HTTPException(
            status_code=404,
            detail=f"Report '{report_id}' not found. Generate it first via POST /api/reports/generate.",
        )
    return FileResponse(
        path=path,
        media_type="application/pdf",
        filename=f"report_{report_id}.pdf",
    )
