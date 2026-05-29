"""
anomaly_detector.py
--------------------
Statistical anomaly / outlier detection using Python stdlib only (math, statistics).
No external dependencies required.

Two detection methods:
  z-score  — flags values where |z| > threshold (default 3.0).
             Works best for roughly normal distributions with n >= 30.
  iqr      — flags values outside Q1 − k·IQR or Q3 + k·IQR (default k=1.5).
             Robust to skewed distributions and works well for small datasets.

Auto-selection:
  n < 30   → IQR (more robust for small samples)
  n >= 30  → Z-score
"""
from __future__ import annotations

import math
import statistics
from typing import Any, Literal

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.core.error_handler import structured_error

Method = Literal["auto", "zscore", "iqr"]


# ── Pure-Python statistical helpers ──────────────────────────────────────────

def _zscore_flags(values: list[float], threshold: float) -> list[bool]:
    if len(values) < 2:
        return [False] * len(values)
    mean = statistics.mean(values)
    stdev = statistics.pstdev(values)  # population stdev to handle small n
    if stdev == 0:
        return [False] * len(values)
    return [abs((v - mean) / stdev) >= threshold for v in values]


def _iqr_flags(values: list[float], multiplier: float) -> list[bool]:
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n < 4:
        # Not enough data for IQR — flag nothing
        return [False] * n
    # Interpolated quartiles
    q1 = _percentile(sorted_vals, 25)
    q3 = _percentile(sorted_vals, 75)
    iqr = q3 - q1
    lower = q1 - multiplier * iqr
    upper = q3 + multiplier * iqr
    return [v < lower or v > upper for v in values]


def _percentile(sorted_vals: list[float], pct: float) -> float:
    """Linear interpolation percentile on a pre-sorted list."""
    n = len(sorted_vals)
    k = (n - 1) * pct / 100
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


# ── Core detection functions ──────────────────────────────────────────────────

def detect_anomalies(
    rows: list[dict[str, Any]],
    columns: list[str],
    column: str = "",
    method: Method = "auto",
    zscore_threshold: float = 3.0,
    iqr_multiplier: float = 1.5,
) -> dict[str, Any]:
    """
    Detect statistical outliers in `rows` for the specified numeric column.

    Parameters
    ----------
    rows            : List of row dicts (as returned by sql_executor).
    columns         : Column name list (used for validation).
    column          : Numeric column to analyse. If empty, the first numeric
                      column found is used.
    method          : "auto" selects IQR for n<30, z-score otherwise.
    zscore_threshold: Flag rows where |z| > this value (default 3.0).
    iqr_multiplier  : IQR fence multiplier k (default 1.5).

    Returns a dict with:
      column          – column analysed
      method_used     – "zscore" or "iqr"
      total_rows      – number of input rows
      outlier_count   – number of flagged rows
      outlier_rows    – the flagged row dicts (with _z_score or _iqr_distance added)
      non_outlier_rows– the clean rows
      stats           – descriptive stats for the column
    """
    if not rows:
        return structured_error(
            tool="anomaly_detector",
            message="No rows provided for anomaly detection.",
            error_type="EmptyDataError",
            suggestion="Run a SQL query first and pass the result rows here.",
        )

    # Resolve which column to analyse
    numeric_cols = [
        col for col in (columns or list(rows[0].keys()))
        if all(
            isinstance(row.get(col), (int, float)) and row.get(col) == row.get(col)
            for row in rows
            if row.get(col) is not None
        )
    ]
    if not numeric_cols:
        return structured_error(
            tool="anomaly_detector",
            message="No numeric columns found in the data.",
            error_type="NoNumericColumn",
            suggestion="Ensure the SQL query returns at least one numeric (int/float) column.",
        )

    target_col = column if column in numeric_cols else numeric_cols[0]
    values: list[float] = [float(row[target_col]) for row in rows if row.get(target_col) is not None]
    n = len(values)

    # Choose method
    chosen_method: Literal["zscore", "iqr"]
    if method == "auto":
        chosen_method = "iqr" if n < 30 else "zscore"
    elif method == "zscore":
        chosen_method = "zscore"
    else:
        chosen_method = "iqr"

    # Compute flags
    if chosen_method == "zscore":
        flags = _zscore_flags(values, zscore_threshold)
        mean = statistics.mean(values)
        stdev = statistics.pstdev(values)
        extras = [
            {"_z_score": round((v - mean) / stdev, 4) if stdev else 0.0}
            for v in values
        ]
    else:
        flags = _iqr_flags(values, iqr_multiplier)
        q1 = _percentile(sorted(values), 25)
        q3 = _percentile(sorted(values), 75)
        iqr = q3 - q1
        lower = q1 - iqr_multiplier * iqr
        upper = q3 + iqr_multiplier * iqr
        extras = [
            {"_distance_from_fence": round(
                min(v - lower if v < lower else 0, upper - v if v > upper else 0) * -1, 4
            )}
            for v in values
        ]

    # Build annotated rows
    outlier_rows: list[dict[str, Any]] = []
    clean_rows: list[dict[str, Any]] = []
    for row, flag, extra in zip(rows, flags, extras):
        annotated = {**row, **extra, "_is_outlier": flag}
        if flag:
            outlier_rows.append(annotated)
        else:
            clean_rows.append(annotated)

    # Descriptive stats
    stats: dict[str, Any] = {
        "count": n,
        "mean": round(statistics.mean(values), 4),
        "stdev": round(statistics.pstdev(values), 4),
        "min": min(values),
        "max": max(values),
        "median": statistics.median(values),
    }
    if n >= 4:
        stats["q1"] = round(_percentile(sorted(values), 25), 4)
        stats["q3"] = round(_percentile(sorted(values), 75), 4)

    return {
        "column": target_col,
        "method_used": chosen_method,
        "total_rows": n,
        "outlier_count": len(outlier_rows),
        "outlier_rows": outlier_rows,
        "non_outlier_rows": clean_rows,
        "stats": stats,
    }


# ── LangChain tool ────────────────────────────────────────────────────────────

class AnomalyDetectorInput(BaseModel):
    rows: list[dict[str, Any]] = Field(
        ..., description="Tabular row dicts from a SQL query result."
    )
    columns: list[str] = Field(
        default_factory=list,
        description="Column names list. If empty, derived from the first row.",
    )
    column: str = Field(
        "",
        description="Specific numeric column to analyse for outliers. "
                    "If empty, the first numeric column is used.",
    )
    method: Method = Field(
        "auto",
        description="Detection method: 'auto' (recommended), 'zscore', or 'iqr'.",
    )
    zscore_threshold: float = Field(3.0, ge=1.0, le=10.0)
    iqr_multiplier: float = Field(1.5, ge=0.5, le=5.0)


anomaly_detection_tool = StructuredTool.from_function(
    name="anomaly_detector",
    description=(
        "Detect statistical outliers in tabular data. "
        "Pass SQL query result rows and specify which numeric column to analyse. "
        "Returns flagged outlier rows with z-score or IQR distance annotations."
    ),
    func=detect_anomalies,
    args_schema=AnomalyDetectorInput,
)
