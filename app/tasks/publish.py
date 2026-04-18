"""Celery task: publish carousel to Instagram via Post for Me."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from app.integrations.supabase_client import sync_flow_snapshot_to_supabase
from app.tasks.celery_app import celery_app
from app.telegram.notify import send_user_text
from app.utils.logging import bind_flow_context, get_logger

logger = get_logger(__name__)


def _build_hashtags(preset: dict[str, Any], topic: dict[str, Any]) -> list[str]:
    """Return a short hashtag list from brand defaults plus topic keywords."""
    hashtags = [
        str(tag).strip()
        for tag in preset.get("voice", {}).get("hashtags", [])
        if str(tag).strip()
    ]
    seen = {tag.lower() for tag in hashtags}
    for token in str(topic.get("title", "")).replace(",", " ").split():
        normalized = "".join(ch for ch in token if ch.isalnum())
        if len(normalized) < 4:
            continue
        candidate = f"#{normalized}"
        if candidate.lower() in seen:
            continue
        hashtags.append(candidate)
        seen.add(candidate.lower())
        if len(hashtags) >= 12:
            break
    return hashtags[:12]


def build_final_caption(flow_data: dict[str, Any]) -> str:
    """Build the final Instagram caption from flow data and brand preset."""
    from app.brands.registry import get_preset

    brand = str(flow_data.get("brand", ""))
    preset = get_preset(brand)
    slides_raw = flow_data.get("prompts", [])
    slides: list[dict[str, Any]] = slides_raw if isinstance(slides_raw, list) else []
    story_arc = str(flow_data.get("story_arc", "")).strip()
    topic = flow_data.get("topic_chosen", {})

    hook_caption = str(slides[0].get("caption", "")).strip() if slides else ""
    if hook_caption and story_arc:
        body = f"{hook_caption}\n\n{story_arc}"
    elif hook_caption:
        body = hook_caption
    elif story_arc:
        body = story_arc
    else:
        body = f"New post from {brand}"

    hashtags = _build_hashtags(preset, topic if isinstance(topic, dict) else {})
    caption = f"{body}\n\n{' '.join(hashtags)}".strip() if hashtags else body
    caption_template = str(preset.get("caption_template", "{caption}"))
    return caption_template.replace("{caption}", caption)


def build_caption_preview(flow_data: dict[str, Any]) -> str:
    """Return a Telegram-friendly caption preview before publishing."""
    topic = flow_data.get("topic_chosen", {})
    topic_title = topic.get("title") if isinstance(topic, dict) else "Sem tópico"
    caption = build_final_caption(flow_data)
    return f"Preview da publicação:\n\nTópico: {topic_title}\n\n{caption[:1800]}"


@celery_app.task(name="app.tasks.publish.publish", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def publish(self: Any, flow_id: str) -> None:
    """Publish the approved carousel to Instagram."""
    from app.state.redis_store import reset_redis_client

    reset_redis_client()
    bind_flow_context(flow_id)
    logger.info("task_publish_started", flow_id=flow_id)
    asyncio.run(_publish_async(flow_id))


async def _publish_async(flow_id: str) -> None:
    import httpx

    from app.brands.registry import get_preset
    from app.integrations.postforme import (
        format_error_response,
        resolve_postforme_social_account_ids,
    )
    from app.integrations.postforme import publish as postforme_publish
    from app.state import machine as fsm
    from app.state.redis_store import clear_user_active_flow, delete_flow, load_flow

    flow_data = await load_flow(flow_id)
    if flow_data is None:
        logger.error("flow_not_found", flow_id=flow_id)
        return

    brand = str(flow_data.get("brand", ""))
    telegram_user_id = int(flow_data.get("telegram_user_id", 0))
    image_urls_raw = flow_data.get("image_urls", [])
    image_urls: list[str] = image_urls_raw if isinstance(image_urls_raw, list) else []

    preset = get_preset(brand)
    final_caption = build_final_caption(flow_data)
    social_ids = resolve_postforme_social_account_ids(preset)

    try:
        result = await postforme_publish(
            social_account_ids=social_ids,
            media_urls=image_urls,
            caption=final_caption,
            flow_id=flow_id,
        )
    except ValueError as exc:
        logger.error("publish_failed_validation", flow_id=flow_id, error=str(exc))
        await fsm.transition(
            flow_id,
            "fail",
            updates={"error": str(exc), "caption": final_caption},
        )
        sync_flow_snapshot_to_supabase(
            flow_id,
            {
                **flow_data,
                "error": str(exc),
                "caption": final_caption,
                "stage": "FAILED",
                "status": "failed",
            },
        )
        await send_user_text(telegram_user_id, f"Publicação não configurada: {exc}")
        return
    except httpx.HTTPStatusError as exc:
        detail = format_error_response(exc.response)
        err = f"{exc.response.status_code}: {detail}"
        logger.error("publish_failed_http", flow_id=flow_id, error=err)
        await fsm.transition(
            flow_id,
            "fail",
            updates={"error": err, "caption": final_caption},
        )
        sync_flow_snapshot_to_supabase(
            flow_id,
            {
                **flow_data,
                "error": err,
                "caption": final_caption,
                "stage": "FAILED",
                "status": "failed",
            },
        )
        await send_user_text(
            telegram_user_id,
            "Post for Me recusou a publicação. Confira API key, IDs das contas e URLs das imagens. "
            f"Resposta: {detail[:400]}",
        )
        return
    except Exception as exc:
        logger.error("publish_failed", flow_id=flow_id, error=str(exc))
        await fsm.transition(
            flow_id,
            "fail",
            updates={"error": str(exc), "caption": final_caption},
        )
        sync_flow_snapshot_to_supabase(
            flow_id,
            {
                **flow_data,
                "error": str(exc),
                "caption": final_caption,
                "stage": "FAILED",
                "status": "failed",
            },
        )
        await send_user_text(
            telegram_user_id,
            "Erro ao publicar. Verifique Post for Me (api.postforme.dev) e tente novamente.",
        )
        return

    completed_at = datetime.now(UTC).isoformat()
    await fsm.transition(
        flow_id,
        "publish_done",
        updates={
            "postforme_post_id": result.post_id,
            "instagram_permalink": result.permalink or "",
            "status": "completed",
            "completed_at": completed_at,
            "caption": final_caption,
        },
    )
    sync_flow_snapshot_to_supabase(
        flow_id,
        {
            **flow_data,
            "postforme_post_id": result.post_id,
            "instagram_permalink": result.permalink or "",
            "status": "completed",
            "completed_at": completed_at,
            "caption": final_caption,
            "stage": "COMPLETED",
        },
    )

    await clear_user_active_flow(telegram_user_id)
    await delete_flow(flow_id)

    link = result.permalink or "Instagram"
    await send_user_text(telegram_user_id, f"Carrossel publicado com sucesso!\n{link}")
    logger.info("task_publish_done", flow_id=flow_id, post_id=result.post_id)
