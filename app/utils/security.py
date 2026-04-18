"""Security helpers: allowlist check and Telegram webhook secret validation."""

from fastapi import Header, HTTPException, status

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


def is_allowed(user_id: int) -> bool:
    """Return True if the Telegram user_id is in the configured allowlist."""
    return user_id in settings.allowed_telegram_user_ids


def require_allowed(user_id: int) -> None:
    """Raise ValueError if user_id is not in the allowlist."""
    if not is_allowed(user_id):
        logger.warning("unauthorized_user", user_id=user_id)
        raise ValueError(f"User {user_id} is not authorised")


async def verify_telegram_secret(
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
) -> None:
    """FastAPI dependency that validates the Telegram webhook secret header.

    Raises HTTP 403 if the header is missing or does not match the configured secret.
    """
    if x_telegram_bot_api_secret_token != settings.telegram_webhook_secret:
        logger.warning("invalid_webhook_secret")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid webhook secret",
        )
