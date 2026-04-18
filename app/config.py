"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

VALID_BRANDS = frozenset(
    {"dockplus", "roberts", "flamma", "capecodder", "granite", "cheesebread", "thiagaoai"}
)

_PLACEHOLDER_MARKERS = ("your_", "replace", "example", "<", "changeme")


class Settings(BaseSettings):
    """All configuration is read from environment variables / .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str
    telegram_webhook_secret: str
    allowed_telegram_user_ids: set[int] = set()
    public_webhook_url: str = "https://hermes.dockplusai.com"

    # ── External APIs ─────────────────────────────────────────────────────────
    perplexity_api_key: str = ""
    deepseek_api_key: str = ""
    anthropic_api_key: str = ""
    fal_key: str = ""
    postforme_api_key: str = ""
    # Post for Me social account id (spc_… / sa_…) when brand preset has none
    postforme_default_social_account_id: str = ""

    # ── Supabase ──────────────────────────────────────────────────────────────
    supabase_url: str = ""
    supabase_service_key: str = ""
    supabase_schema: str = "public"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Application ───────────────────────────────────────────────────────────
    log_level: str = "INFO"
    # Set to false in local dev (no public URL available)
    register_webhook: bool = True

    # Rate limiting (per user, per window)
    rate_limit_carousels_per_hour: int = 10
    rate_limit_callbacks_per_minute: int = 60

    # TTLs (seconds)
    flow_ttl_active: int = 3600        # 1 hour for active flows
    flow_ttl_terminal: int = 86400     # 24 hours for completed/failed/cancelled
    lock_ttl: int = 30
    idempotency_ttl: int = 300         # 5 minutes
    max_cost_per_carousel_usd: float = 1.50

    @field_validator("allowed_telegram_user_ids", mode="before")
    @classmethod
    def parse_user_ids(cls, v: object) -> set[int]:
        """Parse comma-separated string of user IDs into a set of ints.

        pydantic-settings v2 may JSON-decode the env value before calling
        this validator, so the value can arrive as int, str, list, or set.
        """
        if isinstance(v, set):
            return {int(i) for i in v}
        if isinstance(v, int):
            return {v}
        if isinstance(v, str):
            return {int(uid.strip()) for uid in v.split(",") if uid.strip()}
        if isinstance(v, (list, tuple)):
            return {int(uid) for uid in v}
        return set()

    @field_validator("telegram_bot_token", "telegram_webhook_secret")
    @classmethod
    def validate_required_secret(cls, value: str) -> str:
        """Reject blank or obviously placeholder secrets for required settings."""
        cleaned = value.strip()
        lowered = cleaned.lower()
        if not cleaned:
            raise ValueError("Required secret cannot be empty")
        if any(marker in lowered for marker in _PLACEHOLDER_MARKERS):
            raise ValueError("Required secret looks like a placeholder value")
        return cleaned

    @model_validator(mode="after")
    def validate_runtime_configuration(self) -> "Settings":
        """Validate cross-field runtime settings."""
        if self.register_webhook and not self.public_webhook_url.startswith(
            ("https://", "http://localhost")
        ):
            raise ValueError(
                "PUBLIC_WEBHOOK_URL must be HTTPS in webhook mode, "
                "except for localhost development."
            )
        return self

    @property
    def webhook_path(self) -> str:
        """FastAPI path for the Telegram webhook endpoint."""
        return "/webhook/telegram"

    @property
    def webhook_url(self) -> str:
        """Full public URL for the Telegram webhook."""
        return f"{self.public_webhook_url.rstrip('/')}{self.webhook_path}"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()  # type: ignore[call-arg]


settings: Settings = get_settings()
