"""
cache_refresher.py
-------------------
Background asyncio task that proactively re-runs SQL queries whose cached
results are close to their TTL deadline, preventing cache cold-misses for
frequently-used BI queries.

Flow:
  1. Every CACHE_REFRESH_INTERVAL_SECONDS, scan for near-expiry keys.
  2. For each key whose elapsed time >= CACHE_REFRESH_THRESHOLD_PCT of its TTL,
     re-execute the original SQL and overwrite the cached result.
  3. Errors during refresh are logged and skipped; the old value stays until
     it expires naturally.

Started/stopped via the FastAPI lifespan context in main.py.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)

_refresh_task: asyncio.Task[None] | None = None


async def _refresh_loop() -> None:
    """Async loop that runs until cancelled."""
    logger.info(
        "Cache refresher started (interval=%ds, threshold=%.0f%%)",
        settings.CACHE_REFRESH_INTERVAL_SECONDS,
        settings.CACHE_REFRESH_THRESHOLD_PCT * 100,
    )
    while True:
        try:
            await asyncio.sleep(settings.CACHE_REFRESH_INTERVAL_SECONDS)
            await _do_refresh()
        except asyncio.CancelledError:
            logger.info("Cache refresher stopped.")
            return
        except Exception as exc:
            logger.error("Cache refresher iteration failed: %s", exc)


async def _do_refresh() -> None:
    """Scan near-expiry keys and re-execute their SQL queries."""
    # Deferred imports to avoid circular imports at module load time
    from app.cache.enhanced_query_cache import get_near_expiry_keys, set_cached_result
    from app.db.azure_sql import execute_select
    from app.text2sql.validator import validate_select_query
    from app.core.exceptions import QueryValidationError

    near_expiry = get_near_expiry_keys(settings.CACHE_REFRESH_THRESHOLD_PCT)
    if not near_expiry:
        return

    logger.info("Cache refresher: found %d near-expiry keys to refresh.", len(near_expiry))

    for entry in near_expiry:
        sql: str = entry["sql"]
        key: str = entry["cache_key"]
        original_ttl: int = entry["original_ttl"]
        try:
            safe_sql = validate_select_query(sql)
            # Run in a thread pool so we don't block the event loop
            result: dict[str, Any] = await asyncio.get_event_loop().run_in_executor(
                None, execute_select, safe_sql
            )
            payload: dict[str, Any] = {"sql": safe_sql, **result, "from_cache": False}
            set_cached_result(safe_sql, payload, ttl=original_ttl)
            logger.debug("Cache refresher: refreshed key %s (sql=%.60s…)", key, sql)
        except QueryValidationError:
            logger.warning("Cache refresher: skipping invalid SQL for key %s", key)
        except Exception as exc:
            logger.warning("Cache refresher: failed to refresh key %s: %s", key, exc)


def get_freshness_report() -> list[dict[str, Any]]:
    """
    Return freshness metadata for all near-expiry keys at the configured threshold.

    Exposed via GET /api/cache/freshness so operators can see which queries
    are about to be refreshed.
    """
    from app.cache.enhanced_query_cache import get_near_expiry_keys
    return get_near_expiry_keys(settings.CACHE_REFRESH_THRESHOLD_PCT)


async def start() -> None:
    """Start the background refresh loop (called from FastAPI lifespan)."""
    global _refresh_task
    _refresh_task = asyncio.create_task(_refresh_loop())


async def stop() -> None:
    """Cancel the background refresh loop (called from FastAPI lifespan)."""
    global _refresh_task
    if _refresh_task and not _refresh_task.done():
        _refresh_task.cancel()
        try:
            await _refresh_task
        except asyncio.CancelledError:
            pass
    _refresh_task = None
