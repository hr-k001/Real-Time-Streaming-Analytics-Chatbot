"""
routes_analytics.py
--------------------
Feature 3: Anomaly Detection endpoints.

POST /api/analytics/anomaly  — detect statistical outliers in tabular data.
"""
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.analytics.anomaly_detector import Method, detect_anomalies

router = APIRouter(prefix="/analytics", tags=["analytics"])


class AnomalyRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(
        ..., description="Row dicts from a SQL query result (or any tabular source)."
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Column names. If empty, derived from the first row.",
    )
    column: str = Field(
        "",
        description="Numeric column to analyse. If empty, first numeric column is used.",
    )
    method: Method = Field(
        "auto",
        description="'auto' selects IQR for n<30 and z-score for n>=30.",
    )
    zscore_threshold: float = Field(3.0, ge=1.0, le=10.0)
    iqr_multiplier: float = Field(1.5, ge=0.5, le=5.0)


@router.post("/anomaly")
def detect_anomaly(request: AnomalyRequest) -> dict[str, Any]:
    """
    Feature 3 — Detect statistical outliers in tabular data.

    Supported methods:
      auto    — IQR for n<30, z-score otherwise (recommended)
      zscore  — Flag rows where |z| > zscore_threshold
      iqr     — Flag rows outside Q1±k·IQR and Q3±k·IQR fences

    Returns flagged rows annotated with _is_outlier and either
    _z_score or _distance_from_fence, plus descriptive statistics.
    """
    return detect_anomalies(
        rows=request.rows,
        columns=request.columns,
        column=request.column,
        method=request.method,
        zscore_threshold=request.zscore_threshold,
        iqr_multiplier=request.iqr_multiplier,
    )
