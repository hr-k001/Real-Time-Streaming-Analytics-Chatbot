import hashlib
import json
from typing import Any

from app.cache.memory_cache import cache
from app.core.config import settings


def make_query_cache_key(sql: str, params: dict[str, Any] | None = None) -> str:
    normalized = " ".join(sql.split()).lower()
    payload = {"sql": normalized, "params": params or {}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    return f"query:{digest}"


def get_cached_query(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    return cache.get(make_query_cache_key(sql, params))


def set_cached_query(sql: str, value: dict[str, Any], params: dict[str, Any] | None = None) -> None:
    cache.set(make_query_cache_key(sql, params), value, settings.CACHE_TTL_SECONDS)
