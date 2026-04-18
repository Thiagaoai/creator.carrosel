"""Unit tests for Telegram bot bridge helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import app.telegram.bot as bot_module


@pytest.mark.asyncio
async def test_process_update_ignores_duplicate_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """Duplicate Telegram update IDs should be ignored before PTB processing."""
    dummy_app = SimpleNamespace(bot=object(), process_update=AsyncMock())
    monkeypatch.setattr(bot_module, "_application", dummy_app)
    monkeypatch.setattr(bot_module.redis_store, "is_duplicate", AsyncMock(return_value=True))

    await bot_module.process_update({"update_id": 42})

    dummy_app.process_update.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_update_forwards_new_update(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-duplicate updates should be forwarded to the PTB application."""
    dummy_app = SimpleNamespace(bot=object(), process_update=AsyncMock())
    monkeypatch.setattr(bot_module, "_application", dummy_app)
    monkeypatch.setattr(bot_module.redis_store, "is_duplicate", AsyncMock(return_value=False))
    monkeypatch.setattr(
        bot_module.Update,
        "de_json",
        staticmethod(lambda payload, bot: "parsed-update"),
    )

    await bot_module.process_update({"update_id": 99})

    dummy_app.process_update.assert_awaited_once_with("parsed-update")
