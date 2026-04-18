"""Celery task: research trending topics for a brand via Perplexity."""

from __future__ import annotations

import asyncio
from typing import Any

from app.integrations.supabase_client import sync_flow_snapshot_to_supabase
from app.tasks.celery_app import celery_app
from app.telegram.notify import send_user_text
from app.utils.logging import bind_flow_context, get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.research.research_topics", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def research_topics(self: Any, flow_id: str) -> None:
    """Fetch 10 current sub-topic options for the user-provided topic.

    On success, saves topics to Redis + Supabase and sends Telegram keyboard.
    On failure, marks flow as FAILED and notifies the user.
    """
    from app.state.redis_store import reset_redis_client
    reset_redis_client()
    bind_flow_context(flow_id)
    logger.info("task_research_started", flow_id=flow_id)

    asyncio.run(_research_topics_async(flow_id))


async def _research_topics_async(flow_id: str) -> None:
    from app.integrations.perplexity import search_topics
    from app.state import machine as fsm
    from app.state.redis_store import load_flow, save_flow
    from app.telegram.keyboards import topics_keyboard

    flow_data = await load_flow(flow_id)
    if flow_data is None:
        logger.error("flow_not_found", flow_id=flow_id)
        return

    brand = str(flow_data.get("brand", ""))
    telegram_user_id = int(flow_data.get("telegram_user_id", 0))
    user_topic = str(flow_data.get("user_topic", "")).strip()

    if not user_topic:
        logger.error("user_topic_missing", flow_id=flow_id)
        await fsm.transition(flow_id, "fail", updates={"error": "user_topic missing"})
        await send_user_text(
            telegram_user_id,
            "Tópico não informado. Use /novo e envie o tópico em uma mensagem.",
        )
        return

    from app.brands.registry import get_preset

    preset = get_preset(brand)
    voice = preset.get("voice", {})
    tone: str = voice.get("tone", "professional")
    brand_context = f"{brand} — {tone}"
    # Align FSM: INIT → RESEARCHING before calling external APIs
    stage = str(flow_data.get("stage", "INIT"))
    if stage == "INIT":
        await fsm.transition(flow_id, "start_research")
        flow_data = await load_flow(flow_id) or flow_data

    try:
        topics = await search_topics(
            brand_name=brand,
            brand_context=brand_context,
            user_topic=user_topic,
            flow_id=flow_id,
        )
    except Exception as exc:
        logger.error("research_failed", flow_id=flow_id, error=str(exc))
        await fsm.transition(flow_id, "fail", updates={"error": str(exc)})
        await send_user_text(
            telegram_user_id,
            "Erro ao buscar tópicos. Tente /novo novamente.",
        )
        return

    merged = {**flow_data, "topics": topics}
    await save_flow(flow_id, merged)
    sync_flow_snapshot_to_supabase(flow_id, merged)
    await fsm.transition(flow_id, "research_done")

    keyboard = topics_keyboard(topics)
    message = (
        f"Escolha uma das *{len(topics)} opções* dentro do tópico "
        f"_{user_topic}_:\n\n"
        + "\n".join(f"{i + 1}. {t['title']}" for i, t in enumerate(topics))
    )
    await send_user_text(telegram_user_id, message, parse_mode="Markdown", reply_markup=keyboard)
    logger.info("task_research_done", flow_id=flow_id, topic_count=len(topics))
