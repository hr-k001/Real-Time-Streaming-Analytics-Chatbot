"""
app/main.py
-----------
FastAPI application factory with:
  - Himanshu's original routers (US-01–07)
  - Binit's routers (US-08–16)
  - Cache TTL refresh background task (Feature 1)
  - Analytics router for anomaly detection (Feature 3)
  - Data sources router for spreadsheet integration (Feature 2)
  - Voice router for Groq Whisper transcription (Feature 5)
  - Reports router for PDF generation (Feature 4)
"""
import os
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_tools import router as tools_router
from app.api.routes_binit import router as binit_router
from app.api.routes_analytics import router as analytics_router
from app.api.routes_data_sources import router as data_sources_router
from app.api.routes_voice import router as voice_router
from app.api.routes_reports import router as reports_router
from app.cache import cache_refresher
from app.core.config import settings
from app.core.logging import configure_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    os.makedirs(settings.EXPORT_DIR, exist_ok=True)
    os.makedirs(settings.REPORTS_DIR, exist_ok=True)
    await cache_refresher.start()
    yield
    await cache_refresher.stop()


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "LLM-powered BI assistant backend with Groq, LangGraph, and Azure SQL tools.\n\n"
            "**US-01–07**: Himanshu Kumar  \n"
            "**US-08–16**: Binit Thakur  \n"
            "**Feature 1**: Cache TTL Refresh  \n"
            "**Feature 2**: Spreadsheet Integration  \n"
            "**Feature 3**: Anomaly Detection  \n"
            "**Feature 4**: PDF Report Generation  \n"
            "**Feature 5**: Voice Query (Groq Whisper)  \n"
            "**Feature 7**: Tool Error Handling"
        ),
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router,      prefix="/api")
    app.include_router(chat_router,        prefix="/api")
    app.include_router(tools_router,       prefix="/api")
    app.include_router(binit_router,       prefix="/api")
    app.include_router(analytics_router,   prefix="/api")
    app.include_router(data_sources_router, prefix="/api")
    app.include_router(voice_router,       prefix="/api")
    app.include_router(reports_router,     prefix="/api")

    return app


app = create_app()
