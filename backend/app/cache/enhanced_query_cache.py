"""
US-16: Query Result Caching — enhanced layer
----------------------------------------------
Builds on Himanshu's query_cache.py to add:
  • Cache statistics (hits, misses, evictions)
  • Selective invalidation by table name
  • Cache warm-up for a list of known frequent queries
  • TTL-based auto-invalidation already handled by MemoryCache
  • A LangChain StructuredTool the agent can call to flush stale results
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any

from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from app.cache.memory_cache import cache
from app.core.config import settings

logger = logging.getLogger(__name__)

# ── Stats tracking ────────────────────────────────────────────────────────────

@dataclass
class CacheStats:
    hits: int = 0
    misses: int = 0
    sets: int = 0
    invalidations: int = 0
    _start: float = field(default_factory=time.time)

    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return round(self.hits / total, 4) if total else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "sets": self.sets,
            "invalidations": self.invalidations,
            "hit_rate_pct": round(self.hit_rate() * 100, 1),
            "uptime_seconds": round(time.time() - self._start),
        }


_stats = CacheStats()

# ── Index of active cache keys (for invalidation by table) ───────────────────
# key: cache_key  value: list of table names referenced in the SQL
_key_table_index: dict[str, list[str]] = {}

# key: cache_key  value: original SQL string (used by the background refresher)
_key_sql_index: dict[str, str] = {}

# key: cache_key  value: TTL used when the entry was stored
_key_ttl_index: dict[str, int] = {}


# ── Key generation ────────────────────────────────────────────────────────────

def _normalize_sql(sql: str) -> str:
    """Collapse whitespace and lowercase for cache key hashing."""
    return " ".join(sql.split()).lower()


def make_cache_key(sql: str, params: dict[str, Any] | None = None) -> str:
    normalized = _normalize_sql(sql)
    payload = {"sql": normalized, "params": params or {}}
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return f"qcache:{digest}"


def _extract_tables(sql: str) -> list[str]:
    """Pull table names from FROM / JOIN clauses."""
    matches = re.findall(r"\bFROM\s+([\w.]+)|\bJOIN\s+([\w.]+)", sql, re.IGNORECASE)
    return [t.lower() for pair in matches for t in pair if t]


# ── Core cache operations ─────────────────────────────────────────────────────

def get_cached_result(sql: str, params: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """
    Look up a cached query result.
    Returns the cached dict (with from_cache=True injected) or None on miss.
    """
    key = make_cache_key(sql, params)
    value = cache.get(key)
    if value is None:
        _stats.misses += 1
        logger.debug("Cache MISS: %s", key)
        return None
    _stats.hits += 1
    logger.debug("Cache HIT:  %s", key)
    return {**value, "from_cache": True}


def set_cached_result(
    sql: str,
    value: dict[str, Any],
    params: dict[str, Any] | None = None,
    ttl: int | None = None,
) -> None:
    """Store a query result in the cache and update all indexes."""
    key = make_cache_key(sql, params)
    effective_ttl = ttl if ttl is not None else settings.CACHE_TTL_SECONDS
    cache.set(key, value, effective_ttl)
    _key_table_index[key] = _extract_tables(sql)
    _key_sql_index[key] = sql
    _key_ttl_index[key] = effective_ttl
    _stats.sets += 1
    logger.debug("Cache SET:  %s (ttl=%ds)", key, effective_ttl)


def get_near_expiry_keys(threshold_pct: float = 0.8) -> list[dict[str, Any]]:
    """
    Return metadata for cache keys whose TTL is more than `threshold_pct` consumed.

    For example, with threshold_pct=0.8 and a 300s TTL, a key is "near expiry"
    when fewer than 60s remain (i.e. 80% of the TTL has elapsed).

    Returns a list of dicts with keys: cache_key, sql, remaining_seconds, original_ttl.
    """
    near_expiry: list[dict[str, Any]] = []
    for key, sql in list(_key_sql_index.items()):
        info = cache.get_expiry_info(key)
        if info is None:
            # Key already expired — clean up indexes
            _key_table_index.pop(key, None)
            _key_sql_index.pop(key, None)
            _key_ttl_index.pop(key, None)
            continue
        original_ttl = _key_ttl_index.get(key, settings.CACHE_TTL_SECONDS)
        elapsed_pct = 1.0 - (info["remaining_seconds"] / original_ttl)
        if elapsed_pct >= threshold_pct:
            near_expiry.append({
                "cache_key": key,
                "sql": sql,
                "remaining_seconds": round(info["remaining_seconds"], 1),
                "original_ttl": original_ttl,
                "elapsed_pct": round(elapsed_pct * 100, 1),
            })
    return near_expiry


def invalidate_by_table(table_name: str) -> int:
    """
    Delete all cached queries that touched a specific table.

    Returns the number of entries invalidated.
    """
    table_lower = table_name.lower().strip()
    to_delete = [k for k, tables in _key_table_index.items() if table_lower in tables]
    for key in to_delete:
        cache.delete(key)
        _key_table_index.pop(key, None)
        _key_sql_index.pop(key, None)
        _key_ttl_index.pop(key, None)
        _stats.invalidations += 1
    if to_delete:
        logger.info("Invalidated %d cache entries for table '%s'", len(to_delete), table_name)
    return len(to_delete)


def invalidate_all() -> int:
    """Flush the entire query result cache."""
    count = len(_key_table_index)
    for key in list(_key_table_index.keys()):
        cache.delete(key)
    _key_table_index.clear()
    _key_sql_index.clear()
    _key_ttl_index.clear()
    _stats.invalidations += count
    logger.info("Cache fully flushed (%d entries removed)", count)
    return count


def get_cache_stats() -> dict[str, Any]:
    """Return current cache performance statistics."""
    return {
        **_stats.to_dict(),
        "active_keys": len(_key_table_index),
    }


# ── Warm-up helper ────────────────────────────────────────────────────────────

def warm_up_cache(queries: list[str]) -> dict[str, Any]:
    """
    Pre-warm the cache by running a list of SQL queries immediately.
    Useful at startup for frequently used BI queries.

    Requires the sql_executor to be importable (avoids circular import at module load).
    """
    from app.tools.sql_executor import run_sql_executor  # deferred import

    results: dict[str, str] = {}
    for sql in queries:
        try:
            result = run_sql_executor(sql)
            if "error" not in result:
                results[sql[:60]] = "warmed"
            else:
                results[sql[:60]] = f"error: {result['error']}"
        except Exception as exc:
            results[sql[:60]] = f"exception: {exc}"
    return {"warmed": results}


# ── LangChain tool (agent can flush or inspect the cache) ────────────────────

class CacheManagementInput(BaseModel):
    action: str = Field(
        ...,
        description="Action to perform: 'stats', 'invalidate_table', 'flush_all'.",
    )
    table_name: str = Field(
        "",
        description="Table name for 'invalidate_table' action.",
    )


def manage_cache(action: str, table_name: str = "") -> dict[str, Any]:
    """Agent-accessible cache management tool."""
    if action == "stats":
        return get_cache_stats()
    elif action == "invalidate_table":
        if not table_name:
            return {"error": "table_name is required for invalidate_table."}
        count = invalidate_by_table(table_name)
        return {"invalidated": count, "table": table_name}
    elif action == "flush_all":
        count = invalidate_all()
        return {"flushed": count}
    else:
        return {"error": f"Unknown action '{action}'. Use: stats, invalidate_table, flush_all."}


cache_management_tool = StructuredTool.from_function(
    name="cache_management",
    description=(
        "Manage the query result cache. "
        "Use action='stats' to see hit rate and active keys, "
        "'invalidate_table' (+ table_name) to clear stale results for a table, "
        "'flush_all' to wipe the entire cache."
    ),
    func=manage_cache,
    args_schema=CacheManagementInput,
)
