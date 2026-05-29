from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.db.azure_sql import get_connection

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _ensure_tables() -> None:
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            IF OBJECT_ID('dbo.ChatSessions', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.ChatSessions (
                    chat_id NVARCHAR(64) NOT NULL PRIMARY KEY,
                    title NVARCHAR(200) NOT NULL,
                    last_message NVARCHAR(1000) NULL,
                    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                    updated_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME()
                );
            END
            """
        )
        cursor.execute(
            """
            IF OBJECT_ID('dbo.ChatMessages', 'U') IS NULL
            BEGIN
                CREATE TABLE dbo.ChatMessages (
                    id INT IDENTITY(1,1) NOT NULL PRIMARY KEY,
                    chat_id NVARCHAR(64) NOT NULL,
                    role NVARCHAR(20) NOT NULL,
                    content NVARCHAR(MAX) NOT NULL,
                    created_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME(),
                    CONSTRAINT FK_ChatMessages_ChatSessions
                        FOREIGN KEY (chat_id) REFERENCES dbo.ChatSessions(chat_id)
                        ON DELETE CASCADE
                );
                CREATE INDEX IX_ChatMessages_ChatId_Id ON dbo.ChatMessages(chat_id, id);
            END
            """
        )
        conn.commit()


def _title_from_message(message: str) -> str:
    compact = " ".join((message or "").split())
    if not compact:
        return "New chat"
    return compact[:60] + ("..." if len(compact) > 60 else "")


def _row_value(row: Any, key: str, index: int) -> Any:
    if hasattr(row, key):
        return getattr(row, key)
    return row[index]


def save_message(chat_id: str, role: str, content: str) -> None:
    if not chat_id or not role or content is None:
        return

    try:
        _ensure_tables()
        now = _utcnow()
        title = _title_from_message(content) if role == "user" else "New chat"
        last_message = " ".join(str(content).split())[:1000]

        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                UPDATE dbo.ChatSessions
                SET
                    title = CASE
                        WHEN title = 'New chat' AND ? = 'user' THEN ?
                        ELSE title
                    END,
                    last_message = ?,
                    updated_at = ?
                WHERE chat_id = ?;
                """,
                role,
                title,
                last_message,
                now,
                chat_id,
            )
            if cursor.rowcount == 0:
                cursor.execute(
                    """
                    INSERT INTO dbo.ChatSessions (chat_id, title, last_message, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?);
                    """,
                    chat_id,
                    title,
                    last_message,
                    now,
                    now,
                )

            cursor.execute(
                """
                INSERT INTO dbo.ChatMessages (chat_id, role, content, created_at)
                VALUES (?, ?, ?, ?);
                """,
                chat_id,
                role,
                str(content),
                now,
            )
            conn.commit()
    except Exception as exc:
        logger.warning("Could not persist chat message for chat_id=%s: %s", chat_id, exc)


def list_sessions(limit: int = 30) -> list[dict[str, Any]]:
    try:
        _ensure_tables()
        safe_limit = max(1, min(limit, 100))
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"""
                SELECT TOP ({safe_limit})
                    chat_id,
                    title,
                    last_message,
                    created_at,
                    updated_at
                FROM dbo.ChatSessions
                ORDER BY updated_at DESC;
                """
            )
            sessions = []
            for row in cursor.fetchall():
                created_at = _row_value(row, "created_at", 3)
                updated_at = _row_value(row, "updated_at", 4)
                sessions.append(
                    {
                        "chat_id": _row_value(row, "chat_id", 0),
                        "title": _row_value(row, "title", 1),
                        "last_message": _row_value(row, "last_message", 2),
                        "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                        "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
                    }
                )
            return sessions
    except Exception as exc:
        logger.warning("Could not load chat history: %s", exc)
        return []


def load_messages(chat_id: str) -> list[dict[str, str]]:
    try:
        _ensure_tables()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT role, content
                FROM dbo.ChatMessages
                WHERE chat_id = ?
                ORDER BY id ASC;
                """,
                chat_id,
            )
            return [
                {"role": str(_row_value(row, "role", 0)), "content": str(_row_value(row, "content", 1))}
                for row in cursor.fetchall()
            ]
    except Exception as exc:
        logger.warning("Could not load messages for chat_id=%s: %s", chat_id, exc)
        return []


def get_session(chat_id: str) -> dict[str, Any] | None:
    try:
        _ensure_tables()
        with get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT chat_id, title, last_message, created_at, updated_at
                FROM dbo.ChatSessions
                WHERE chat_id = ?;
                """,
                chat_id,
            )
            row = cursor.fetchone()
            if not row:
                return None

            created_at = _row_value(row, "created_at", 3)
            updated_at = _row_value(row, "updated_at", 4)
            return {
                "chat_id": _row_value(row, "chat_id", 0),
                "title": _row_value(row, "title", 1),
                "last_message": _row_value(row, "last_message", 2),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
                "updated_at": updated_at.isoformat() if hasattr(updated_at, "isoformat") else str(updated_at),
                "messages": load_messages(chat_id),
            }
    except Exception as exc:
        logger.warning("Could not load chat session chat_id=%s: %s", chat_id, exc)
        return None
