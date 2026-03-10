"""Contextual logger for billing journal.

TODO: Update all logger usages in the project in separate PR to use this contextual
logger and remove the old logging import.
"""

import contextvars
import logging
from typing import Any

_log_context: contextvars.ContextVar[list[str]] = contextvars.ContextVar(
    "log_context",
)


class ContextLogger(logging.LoggerAdapter):
    """LoggerAdapter that prepends contextvars-based context to messages."""

    def process(self, msg: str, kwargs: Any) -> tuple[str, Any]:
        """Prepend context values to the log message if context exists."""
        ctx = _log_context.get([])
        if ctx:
            context_str = " ".join(str(context_id) for context_id in ctx)
            msg = f"{context_str} - {msg}"
        return msg, kwargs


def get_logger(name: str) -> ContextLogger:
    """Drop-in replacement for logging.getLogger with context support."""
    return ContextLogger(logging.getLogger(name), {})


def set_log_context(*context_ids: str) -> None:
    """Add string values to the current log context."""
    ctx = list(_log_context.get([]))
    ctx.extend(context_ids)
    _log_context.set(ctx)


def clear_log_context(*context_ids: str) -> None:
    """Remove string values from the current log context."""
    ctx = list(_log_context.get([]))
    for context_id in context_ids:
        if context_id in ctx:
            ctx.remove(context_id)
    _log_context.set(ctx)
