from __future__ import annotations

import uuid
from typing import Any

from app.agent import history_store
from app.cache.memory_cache import cache
from app.core.config import settings


def new_chat_id() -> str:
    return uuid.uuid4().hex


def _key(chat_id: str) -> str:
    return f"chat:{chat_id}"


def get_chat_state(chat_id: str) -> dict[str, Any]:
    cached = cache.get(_key(chat_id))
    if cached:
        return cached

    stored_messages = history_store.load_messages(chat_id)
    state = {"messages": stored_messages[-10:], "last_result": None}
    if stored_messages:
        save_chat_state(chat_id, state)
    return state


def save_chat_state(chat_id: str, state: dict[str, Any]) -> None:
    cache.set(_key(chat_id), state, settings.CHAT_TTL_SECONDS)


def append_message(chat_id: str, role: str, content: str) -> None:
    state = get_chat_state(chat_id)
    messages = state.setdefault("messages", [])
    messages.append({"role": role, "content": content})
    state["messages"] = messages[-10:]
    save_chat_state(chat_id, state)
    history_store.save_message(chat_id, role, content)
