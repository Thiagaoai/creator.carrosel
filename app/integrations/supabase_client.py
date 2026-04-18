"""Supabase client singleton and domain helpers (SDD §3.1)."""

from __future__ import annotations

import functools
from datetime import UTC, datetime
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Columns on carousel_autoposter.flows that may be updated from Redis snapshots
_FLOW_PROGRESS_COLUMNS: frozenset[str] = frozenset(
    {
        "stage",
        "topic_chosen",
        "slide_count",
        "visual_style",
        "prompts",
        "image_urls",
        "caption",
        "postforme_post_id",
        "instagram_permalink",
        "cost_breakdown",
        "total_cost_usd",
        "completed_at",
        "status",
    }
)


@functools.lru_cache(maxsize=1)
def get_supabase() -> Client:
    """Return the cached Supabase client singleton."""
    options = SyncClientOptions(schema=settings.supabase_schema)
    return create_client(settings.supabase_url, settings.supabase_service_key, options=options)


def _table(table_name: str) -> Any:
    """Return a table builder bound to the configured schema."""
    return get_supabase().schema(settings.supabase_schema).table(table_name)


def insert_flow(
    flow_id: str,
    telegram_user_id: int,
    brand: str,
    stage: str = "INIT",
) -> dict[str, Any]:
    """Insert a new row into carousel_autoposter.flows. Returns inserted row."""
    result = (
        _table("flows")
        .insert(
            {
                "id": flow_id,
                "telegram_user_id": telegram_user_id,
                "brand": brand,
                "stage": stage,
                "status": "active",
            }
        )
        .execute()
    )
    return result.data[0] if result.data else {}


def update_flow(flow_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Update fields on an existing flow row."""
    result = (
        _table("flows")
        .update(updates)
        .eq("id", flow_id)
        .execute()
    )
    return result.data[0] if result.data else {}


def sync_flow_snapshot_to_supabase(flow_id: str, data: dict[str, Any]) -> None:
    """Best-effort push of Redis flow fields that map to ``flows`` table columns."""
    if not settings.supabase_url or not settings.supabase_service_key:
        return
    patch: dict[str, Any] = {
        k: data[k] for k in _FLOW_PROGRESS_COLUMNS if k in data and data[k] is not None
    }
    if not patch:
        return
    try:
        update_flow(flow_id, patch)
    except Exception as exc:
        logger.warning("sync_flow_snapshot_failed", flow_id=flow_id, error=str(exc))


def load_brand_preset(brand: str) -> dict[str, Any] | None:
    """Fetch a brand preset row from brand_presets table."""
    result = (
        _table("brand_presets")
        .select("*")
        .eq("brand", brand)
        .limit(1)
        .execute()
    )
    if result.data:
        return dict(result.data[0])
    logger.warning("brand_preset_not_found", brand=brand)
    return None


def record_cost_sync(
    flow_id: str,
    service: str,
    model: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    images_generated: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
) -> None:
    """Synchronous cost record insertion (for use in Celery tasks)."""
    row: dict[str, Any] = {"flow_id": flow_id, "service": service}
    if model is not None:
        row["model"] = model
    if tokens_input is not None:
        row["tokens_input"] = tokens_input
    if tokens_output is not None:
        row["tokens_output"] = tokens_output
    if images_generated is not None:
        row["images_generated"] = images_generated
    if cost_usd is not None:
        row["cost_usd"] = cost_usd
    if latency_ms is not None:
        row["latency_ms"] = latency_ms

    try:
        _table("api_costs").insert(row).execute()
    except Exception as exc:
        logger.warning("cost_record_failed_sync", service=service, error=str(exc))


def list_completed_flows(telegram_user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    """Return recent completed flows for the given Telegram user."""
    result = (
        _table("flows")
        .select("id, brand, stage, created_at, completed_at, instagram_permalink")
        .eq("telegram_user_id", telegram_user_id)
        .eq("status", "completed")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )
    return list(result.data or [])


def monthly_cost_breakdown(
    telegram_user_id: int,
    reference: datetime | None = None,
) -> list[dict[str, Any]]:
    """Return current-month cost rows for the user's flows."""
    now = reference or datetime.now(UTC)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    flows_result = (
        _table("flows")
        .select("id")
        .eq("telegram_user_id", telegram_user_id)
        .execute()
    )
    flow_ids = [row["id"] for row in (flows_result.data or []) if row.get("id")]
    if not flow_ids:
        return []

    result = (
        _table("api_costs")
        .select("service, model, cost_usd, latency_ms, created_at")
        .in_("flow_id", flow_ids)
        .gte("created_at", month_start)
        .order("created_at", desc=True)
        .execute()
    )
    return list(result.data or [])


def ping_supabase() -> bool:
    """Return True when the configured schema is reachable."""
    result = _table("brand_presets").select("brand").limit(1).execute()
    return isinstance(result.data, list)
