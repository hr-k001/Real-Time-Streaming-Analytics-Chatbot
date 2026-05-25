from typing import Any

from fastapi import APIRouter

from app.text2sql.schema_registry import format_schema_for_prompt, load_database_schema
from app.tools.chart_generator import ChartGeneratorInput, generate_chart
from app.tools.data_summarizer import DataSummarizerInput, summarize_data
from app.tools.export_tool import ExportToolInput, export_data
from app.tools.rest_api_caller import RESTAPICallerInput, call_rest_api
from app.tools.sql_executor import SQLExecutorInput, run_sql_executor

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("/schema")
def schema() -> dict[str, Any]:
    database_schema = load_database_schema()
    return {"schema": database_schema, "prompt_text": format_schema_for_prompt(database_schema)}


@router.post("/sql-executor")
def sql_executor(payload: SQLExecutorInput) -> dict[str, Any]:
    return run_sql_executor(payload.sql)


@router.post("/rest-api-caller")
def rest_api_caller(payload: RESTAPICallerInput) -> dict[str, Any]:
    return call_rest_api(**payload.model_dump())


@router.post("/chart-generator")
def chart_generator(payload: ChartGeneratorInput) -> dict[str, Any]:
    return generate_chart(**payload.model_dump())


@router.post("/data-summarizer")
def data_summarizer(payload: DataSummarizerInput) -> dict[str, Any]:
    return summarize_data(**payload.model_dump())


@router.post("/export")
def export(payload: ExportToolInput) -> dict[str, Any]:
    return export_data(**payload.model_dump())
