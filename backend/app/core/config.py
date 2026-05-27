from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "Real-Time Streaming Analytics Chatbot"
    APP_VERSION: str = "0.1.0"
    APP_ENV: Literal["local", "test", "production"] = "local"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "llama-3.3-70b-versatile"

    AZURE_SQL_SERVER: str = "streaming-analytic.database.windows.net"
    AZURE_SQL_DATABASE: str = "real-time-chatbot"
    AZURE_SQL_USERNAME: str = "capstone-2"
    AZURE_SQL_PASSWORD: str = ""
    AZURE_SQL_DRIVER: str = "ODBC Driver 18 for SQL Server"
    AZURE_SQL_ENCRYPT: str = "yes"
    AZURE_SQL_TRUST_SERVER_CERTIFICATE: str = "no"
    AZURE_SQL_TIMEOUT_SECONDS: int = 30
    SQL_QUERY_TIMEOUT_SECONDS: int = 20
    SQL_MAX_ROWS: int = 500

    CACHE_BACKEND: Literal["memory"] = "memory"
    CACHE_TTL_SECONDS: int = 300
    CHAT_TTL_SECONDS: int = 86400
    CACHE_REFRESH_INTERVAL_SECONDS: int = 60
    CACHE_REFRESH_THRESHOLD_PCT: float = 0.8

    EXPORT_DIR: str = "exports"
    REPORTS_DIR: str = "reports"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def azure_sql_connection_string(self) -> str:
        return (
            f"DRIVER={{{self.AZURE_SQL_DRIVER}}};"
            f"SERVER=tcp:{self.AZURE_SQL_SERVER},1433;"
            f"DATABASE={self.AZURE_SQL_DATABASE};"
            f"UID={self.AZURE_SQL_USERNAME};"
            f"PWD={self.AZURE_SQL_PASSWORD};"
            f"Encrypt={self.AZURE_SQL_ENCRYPT};"
            f"TrustServerCertificate={self.AZURE_SQL_TRUST_SERVER_CERTIFICATE};"
            f"Connection Timeout={self.AZURE_SQL_TIMEOUT_SECONDS};"
        )

    @property
    def export_path(self) -> str:
        return self.EXPORT_DIR


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
