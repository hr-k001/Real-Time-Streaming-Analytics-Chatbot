"""
error_handler.py
-----------------
Shared retry decorator and structured error helper for all tools.

Uses only Python stdlib (time, functools, logging) — no extra dependencies.
"""
from __future__ import annotations

import logging
import time
from functools import wraps
from typing import Any, Callable, Type

logger = logging.getLogger(__name__)


def with_retry(
    max_attempts: int = 3,
    delay_seconds: float = 1.0,
    backoff_factor: float = 2.0,
    retryable_exceptions: tuple[Type[Exception], ...] = (Exception,),
) -> Callable:
    """
    Retry decorator with exponential backoff for transient failures.

    Only retries on exceptions listed in `retryable_exceptions`.
    If all attempts are exhausted the last exception is re-raised.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: Exception | None = None
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as exc:
                    last_exc = exc
                    if attempt < max_attempts:
                        wait = delay_seconds * (backoff_factor ** (attempt - 1))
                        logger.warning(
                            "[%s] attempt %d/%d failed: %s — retrying in %.1fs",
                            func.__name__, attempt, max_attempts, exc, wait,
                        )
                        time.sleep(wait)
                    else:
                        logger.error(
                            "[%s] failed after %d attempts: %s",
                            func.__name__, max_attempts, exc,
                        )
            raise last_exc  # type: ignore[misc]
        return wrapper
    return decorator


def structured_error(
    tool: str,
    message: str,
    error_type: str = "ToolError",
    retries_attempted: int = 0,
    suggestion: str = "",
) -> dict[str, Any]:
    """
    Return a standardised error dict that every tool and the agent can rely on.

    Keys:
      error            – human-readable description of what went wrong
      error_type       – category tag (e.g. "DBError", "NetworkError")
      tool             – name of the tool that failed
      retries_attempted – how many retry attempts were made before giving up
      suggestion       – actionable hint for the user or the LLM
    """
    return {
        "error": message,
        "error_type": error_type,
        "tool": tool,
        "retries_attempted": retries_attempted,
        "suggestion": suggestion,
    }
