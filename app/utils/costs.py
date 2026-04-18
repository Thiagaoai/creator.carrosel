"""Cost tracking helper — writes API usage records to Supabase api_costs table."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Any, cast

from app.utils.logging import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)


async def record_cost(
    flow_id: str,
    service: str,
    model: str | None = None,
    tokens_input: int | None = None,
    tokens_output: int | None = None,
    images_generated: int | None = None,
    cost_usd: float | None = None,
    latency_ms: int | None = None,
) -> None:
    """Record an API call cost entry to the api_costs table in Supabase.

    Import the Supabase client lazily to avoid circular imports.
    """
    from app.integrations.supabase_client import get_supabase

    row: dict[str, Any] = {
        "flow_id": flow_id,
        "service": service,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
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
        client = get_supabase()
        client.table("api_costs").insert(cast(Any, row)).execute()
        logger.debug("cost_recorded", service=service, cost_usd=cost_usd, flow_id=flow_id)
    except Exception as exc:
        logger.warning("cost_record_failed", service=service, error=str(exc), flow_id=flow_id)
