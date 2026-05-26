"""
app/main.py  (updated to include Binit's routes)
-------------------------------------------------
Add ONE line to Himanshu's original main.py to mount Binit's router.
Replace the original main.py with this file.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_chat import router as chat_router
from app.api.routes_health import router as health_router
from app.api.routes_tools import router as tools_router
from app.api.routes_binit import router as binit_router   # ← Binit's routes
from app.core.config import settings
from app.core.logging import configure_logging


def create_app() -> FastAPI:
    configure_logging()

    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=(
            "LLM-powered BI assistant backend with Groq, LangGraph, and Azure SQL tools.\n\n"
            "**US-01–07**: Himanshu Kumar  \n"
            "**US-08–16**: Binit Thakur"
        ),
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router, prefix="/api")
    app.include_router(chat_router,   prefix="/api")
    app.include_router(tools_router,  prefix="/api")
    app.include_router(binit_router,  prefix="/api")   # ← Binit's routes

    return app


app = create_app()
