"""Telegram Application setup and webhook bridge for FastAPI."""

from __future__ import annotations

import logging
import traceback

from telegram import Bot, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from app.config import settings
from app.state import redis_store
from app.telegram.handlers.callbacks import handle_callback
from app.telegram.handlers.commands import (
    cmd_cancelar,
    cmd_custo,
    cmd_historico,
    cmd_marca,
    cmd_novo,
    cmd_status,
)
from app.telegram.handlers.messages import handle_message
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Make PTB's own logger visible
logging.getLogger("telegram").setLevel(logging.WARNING)
logging.getLogger("telegram.ext").setLevel(logging.WARNING)


async def _error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Log all PTB handler exceptions to structlog."""
    err = context.error
    tb = "".join(traceback.format_exception(type(err), err, err.__traceback__)) if err else ""
    logger.error("ptb_handler_error", error=str(err), traceback=tb, update=str(update)[:300])

# Module-level Application instance (initialised once during lifespan)
_application: Application | None = None  # type: ignore[type-arg]


def _build_application() -> Application:  # type: ignore[type-arg]
    """Construct and register all handlers on the Application."""
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .build()
    )

    # Commands
    app.add_handler(CommandHandler("novo", cmd_novo))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("cancelar", cmd_cancelar))
    app.add_handler(CommandHandler("historico", cmd_historico))
    app.add_handler(CommandHandler("custo", cmd_custo))
    app.add_handler(CommandHandler("marca", cmd_marca))

    # Inline callbacks
    app.add_handler(CallbackQueryHandler(handle_callback))

    # Free-text fallback (non-command messages)
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Error handler — surfaces all exceptions to structlog
    app.add_error_handler(_error_handler)

    return app


async def init_bot() -> None:
    """Initialise and start the Application. Called during FastAPI lifespan startup."""
    global _application
    _application = _build_application()
    await _application.initialize()
    await _application.start()
    logger.info("telegram_bot_started")


async def shutdown_bot() -> None:
    """Stop and shut down the Application. Called during FastAPI lifespan shutdown."""
    global _application
    if _application is not None:
        await _application.stop()
        await _application.shutdown()
        _application = None
        logger.info("telegram_bot_stopped")


async def process_update(update_dict: dict[str, object]) -> None:
    """Feed a raw update dict (from the webhook endpoint) into the Application.

    This is called by the FastAPI route handler for every inbound Telegram event.
    """
    if _application is None:
        logger.error("process_update_called_before_init")
        return

    update_id = update_dict.get("update_id")
    if update_id is not None and await redis_store.is_duplicate(f"telegram-update:{update_id}"):
        logger.info("duplicate_update_ignored", update_id=update_id)
        return

    update = Update.de_json(update_dict, _application.bot)
    await _application.process_update(update)


async def set_webhook() -> None:
    """Register the webhook URL with Telegram.

    Called once at startup. Idempotent — safe to call repeatedly.
    """
    bot = Bot(token=settings.telegram_bot_token)
    await bot.set_webhook(
        url=settings.webhook_url,
        secret_token=settings.telegram_webhook_secret,
        allowed_updates=["message", "callback_query"],
    )
    logger.info("webhook_registered", url=settings.webhook_url)
