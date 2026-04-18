"""Unit tests for application settings validation."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_settings_parse_allowed_user_ids_from_csv() -> None:
    """CSV user IDs should become a set of integers."""
    settings = Settings(
        telegram_bot_token="telegram-test-token",
        telegram_webhook_secret="webhook-secret",
        allowed_telegram_user_ids="1, 2,3",
        register_webhook=False,
    )
    assert settings.allowed_telegram_user_ids == {1, 2, 3}


def test_settings_reject_placeholder_required_secret() -> None:
    """Required secrets should not accept obvious placeholder values."""
    with pytest.raises(ValueError):
        Settings(
            telegram_bot_token="replace-with-your-token",
            telegram_webhook_secret="webhook-secret",
            register_webhook=False,
        )


def test_settings_require_https_webhook_url_in_webhook_mode() -> None:
    """Webhook mode should reject non-HTTPS public URLs."""
    with pytest.raises(ValueError):
        Settings(
            telegram_bot_token="telegram-test-token",
            telegram_webhook_secret="webhook-secret",
            public_webhook_url="http://example.com",
            register_webhook=True,
        )
