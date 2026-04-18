"""Send Telegram messages from async contexts (FastAPI handlers and Celery tasks)."""

from __future__ import annotations

from typing import Any

from telegram import Bot, InputMediaPhoto

from app.config import settings


async def send_user_text(
    telegram_user_id: int,
    text: str,
    *,
    parse_mode: str | None = None,
    reply_markup: object | None = None,
) -> None:
    """Send a plain text (or Markdown) message to the user."""
    bot = Bot(token=settings.telegram_bot_token)
    kwargs: dict[str, Any] = {
        "chat_id": telegram_user_id,
        "text": text,
    }
    if parse_mode is not None:
        kwargs["parse_mode"] = parse_mode
    if reply_markup is not None:
        kwargs["reply_markup"] = reply_markup
    await bot.send_message(**kwargs)


async def send_user_plain_text(telegram_user_id: int, text: str) -> None:
    """Send a message without parse mode (avoids Markdown errors from LLM output)."""
    await send_user_text(telegram_user_id, text, parse_mode=None)


async def send_photo_group(
    telegram_user_id: int,
    image_urls: list[str],
) -> None:
    """Send multiple photos as one Telegram album."""
    bot = Bot(token=settings.telegram_bot_token)
    media = [InputMediaPhoto(media=url) for url in image_urls]
    await bot.send_media_group(chat_id=telegram_user_id, media=media)
