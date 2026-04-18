"""FastAPI application entrypoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.config import settings
from app.integrations.supabase_client import ping_supabase
from app.state.redis_store import close_redis
from app.state.redis_store import ping as ping_redis
from app.telegram.bot import init_bot, process_update, set_webhook, shutdown_bot
from app.utils.logging import configure_logging, get_logger
from app.utils.security import verify_telegram_secret

configure_logging(settings.log_level)
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """FastAPI lifespan: startup and shutdown hooks."""
    logger.info("app_startup")
    await init_bot()
    if settings.register_webhook:
        await set_webhook()
    else:
        logger.info("webhook_registration_skipped", reason="REGISTER_WEBHOOK=false")
    yield
    logger.info("app_shutdown")
    await shutdown_bot()
    await close_redis()


app = FastAPI(
    title="carousel-autoposter",
    version="0.1.0",
    description="Instagram carousel autoposter via Telegram",
    lifespan=lifespan,
)


@app.get("/live", status_code=status.HTTP_200_OK)
async def liveness() -> dict[str, str]:
    """Liveness endpoint — proves the process is running."""
    return {"status": "ok"}


@app.get("/ready")
async def readiness() -> JSONResponse:
    """Readiness endpoint — validates critical dependencies."""
    redis_ok = False
    supabase_ok = False
    try:
        redis_ok = await ping_redis()
    except Exception as exc:
        logger.warning("redis_readiness_failed", error=str(exc))
    try:
        if settings.supabase_url and settings.supabase_service_key:
            supabase_ok = ping_supabase()
        else:
            supabase_ok = True
    except Exception as exc:
        logger.warning("supabase_readiness_failed", error=str(exc))

    ready = redis_ok and supabase_ok
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(
        status_code=status_code,
        content={
            "status": "ok" if ready else "degraded",
            "checks": {
                "redis": "ok" if redis_ok else "failed",
                "supabase": "ok" if supabase_ok else "failed",
            },
        },
    )


@app.get("/health")
async def health() -> JSONResponse:
    """Compatibility health endpoint mapped to readiness."""
    return await readiness()


@app.post(
    settings.webhook_path,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_telegram_secret)],
)
async def telegram_webhook(request: Request) -> dict[str, str]:
    """Receive Telegram updates and dispatch to the bot application.

    The ``verify_telegram_secret`` dependency validates the
    ``X-Telegram-Bot-Api-Secret-Token`` header before the body is parsed.
    """
    update_dict: dict[str, Any] = await request.json()
    await process_update(update_dict)
    return {"ok": "true"}


@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Log unhandled exceptions and return a generic 500 response."""
    logger.exception("unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal server error"},
    )
