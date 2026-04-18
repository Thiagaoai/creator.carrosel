"""Structured JSON logging with secret redaction via structlog."""

import logging
import re
import sys
from typing import Any

import structlog
from structlog.types import EventDict, WrappedLogger

# Patterns that must never appear in logs
_SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"(sk-[A-Za-z0-9]{10,})", re.IGNORECASE),
    re.compile(r"(fal_[A-Za-z0-9]{10,})", re.IGNORECASE),
    re.compile(r"(Bearer\s+[A-Za-z0-9._\-]{10,})", re.IGNORECASE),
    re.compile(r"(eyJ[A-Za-z0-9._\-]{10,})", re.IGNORECASE),  # JWTs
    re.compile(r"(pplx-[A-Za-z0-9]{10,})", re.IGNORECASE),    # Perplexity
    re.compile(r"(ds-[A-Za-z0-9]{10,})", re.IGNORECASE),       # DeepSeek
]
_REDACTED = "[REDACTED]"


def _redact_secrets(value: str) -> str:
    """Replace known secret patterns with [REDACTED]."""
    for pattern in _SECRET_PATTERNS:
        value = pattern.sub(_REDACTED, value)
    return value


def redact_processor(
    logger: WrappedLogger, method: str, event_dict: EventDict
) -> EventDict:
    """structlog processor that redacts secrets from all string values."""
    for key, value in list(event_dict.items()):
        if isinstance(value, str):
            event_dict[key] = _redact_secrets(value)
        elif isinstance(value, dict):
            event_dict[key] = {
                k: _redact_secrets(v) if isinstance(v, str) else v
                for k, v in value.items()
            }
    return event_dict


def configure_logging(log_level: str = "INFO") -> None:
    """Configure structlog for JSON output with secret redaction.

    Call once at application startup before any logging occurs.
    """
    level = getattr(logging, log_level.upper(), logging.INFO)

    # Route stdlib logging through structlog
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=level,
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            redact_processor,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None, **initial_values: Any) -> Any:
    """Return a structlog logger, optionally with bound initial context values."""
    logger = structlog.get_logger(name)
    if initial_values:
        logger = logger.bind(**initial_values)
    return logger


def bind_flow_context(flow_id: str, **extra: Any) -> None:
    """Bind flow_id (and optional extras) to the current context variable scope.

    All subsequent log calls in the same async context will include these values.
    """
    structlog.contextvars.bind_contextvars(flow_id=flow_id, **extra)


def clear_flow_context() -> None:
    """Clear all context variables (call at the end of a request/task)."""
    structlog.contextvars.clear_contextvars()
