"""Async Redis wrapper for flow state, locks, rate limiting, and idempotency."""

from __future__ import annotations

import json
import uuid
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Module-level Redis connection pool (created lazily)
_redis_client: aioredis.Redis | None = None  # type: ignore[type-arg]


def get_redis() -> aioredis.Redis:  # type: ignore[type-arg]
    """Return (or create) the shared async Redis client."""
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
    return _redis_client


def reset_redis_client() -> None:
    """Discard the cached Redis client so the next call creates a fresh one.

    Must be called at the start of every Celery task before ``asyncio.run()``,
    because Celery forks the process and the previous event loop is closed.
    """
    global _redis_client
    _redis_client = None


async def close_redis() -> None:
    """Close the Redis connection (call on app shutdown)."""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.close()
        _redis_client = None


# ── Flow state ────────────────────────────────────────────────────────────────

def _flow_key(flow_id: str) -> str:
    return f"flow:{flow_id}"


def _user_flow_key(telegram_user_id: int) -> str:
    return f"flow:user:{telegram_user_id}"


def _user_default_brand_key(telegram_user_id: int) -> str:
    return f"user:{telegram_user_id}:default_brand"


async def save_flow(flow_id: str, data: dict[str, Any], ttl: int | None = None) -> None:
    """Persist full flow state as a Redis hash. Serialises complex values as JSON."""
    r = get_redis()
    key = _flow_key(flow_id)
    serialised = {
        k: json.dumps(v) if isinstance(v, (dict, list)) else str(v)
        for k, v in data.items()
    }
    async with r.pipeline() as pipe:
        pipe.hset(key, mapping=serialised)  # type: ignore[arg-type]
        effective_ttl = ttl if ttl is not None else settings.flow_ttl_active
        pipe.expire(key, effective_ttl)
        await pipe.execute()


async def load_flow(flow_id: str) -> dict[str, Any] | None:
    """Load flow state hash from Redis. Returns None if not found."""
    r = get_redis()
    raw = await r.hgetall(_flow_key(flow_id))
    if not raw:
        return None
    result: dict[str, Any] = {}
    for k, v in raw.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, TypeError):
            result[k] = v
    return result


async def delete_flow(flow_id: str) -> None:
    """Delete flow state hash from Redis."""
    r = get_redis()
    await r.delete(_flow_key(flow_id))


async def set_user_active_flow(telegram_user_id: int, flow_id: str) -> None:
    """Track the active flow_id for a user."""
    r = get_redis()
    await r.setex(_user_flow_key(telegram_user_id), settings.flow_ttl_active, flow_id)


async def get_user_active_flow(telegram_user_id: int) -> str | None:
    """Return the active flow_id for a user, or None."""
    r = get_redis()
    return await r.get(_user_flow_key(telegram_user_id))


async def clear_user_active_flow(telegram_user_id: int) -> None:
    """Remove the active flow mapping for a user."""
    r = get_redis()
    await r.delete(_user_flow_key(telegram_user_id))


async def set_user_default_brand(telegram_user_id: int, brand: str) -> None:
    """Persist the preferred brand for a Telegram user."""
    r = get_redis()
    await r.set(_user_default_brand_key(telegram_user_id), brand)


async def get_user_default_brand(telegram_user_id: int) -> str | None:
    """Load the preferred brand for a Telegram user."""
    r = get_redis()
    return await r.get(_user_default_brand_key(telegram_user_id))


# ── Distributed lock ──────────────────────────────────────────────────────────

def _lock_key(flow_id: str) -> str:
    return f"lock:flow:{flow_id}"


async def acquire_lock(flow_id: str) -> bool:
    """Try to acquire a distributed lock for a flow. Returns True on success."""
    r = get_redis()
    acquired = await r.set(_lock_key(flow_id), "1", nx=True, ex=settings.lock_ttl)
    return bool(acquired)


async def release_lock(flow_id: str) -> None:
    """Release the distributed lock for a flow."""
    r = get_redis()
    await r.delete(_lock_key(flow_id))


# ── Rate limiting (sliding-window counter) ────────────────────────────────────

def _rate_key(telegram_user_id: int, window: str = "hour") -> str:
    return f"rate:user:{telegram_user_id}:{window}"


async def check_and_increment_rate(
    telegram_user_id: int,
    limit: int,
    window_seconds: int = 3600,
    window_name: str = "hour",
) -> bool:
    """Increment rate counter and return True if under limit, False if exceeded."""
    r = get_redis()
    key = _rate_key(telegram_user_id, window_name)
    async with r.pipeline() as pipe:
        pipe.incr(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()
    count: int = results[0]
    return count <= limit


# ── Idempotency ───────────────────────────────────────────────────────────────

def _idempotency_key(message_id: int | str) -> str:
    return f"idempotency:{message_id}"


async def is_duplicate(message_id: int | str) -> bool:
    """Return True if this message_id was already processed (within TTL window)."""
    r = get_redis()
    key = _idempotency_key(message_id)
    result = await r.set(key, "1", nx=True, ex=settings.idempotency_ttl)
    return result is None  # None means the key already existed


async def ping() -> bool:
    """Return True when Redis is reachable."""
    r = get_redis()
    return bool(await r.ping())


# ── Convenience: generate a new flow_id ──────────────────────────────────────

def new_flow_id() -> str:
    """Generate a new UUID-based flow identifier."""
    return str(uuid.uuid4())
