"""Celery task: generate carousel images via fal.ai (parallel)."""

from __future__ import annotations

import asyncio
from typing import Any

from app.integrations.supabase_client import sync_flow_snapshot_to_supabase
from app.tasks.celery_app import celery_app
from app.telegram.keyboards import image_approval_keyboard
from app.telegram.notify import send_photo_group, send_user_text
from app.utils.logging import bind_flow_context, get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.images.generate_images", bind=True, max_retries=2)  # type: ignore[untyped-decorator]
def generate_images(self: Any, flow_id: str) -> None:
    """Generate all carousel images for a flow.

    Respects the regen_slides list if present (partial regeneration).
    Sends a Telegram media_group with approval keyboard on completion.
    """
    from app.state.redis_store import reset_redis_client
    reset_redis_client()
    bind_flow_context(flow_id)
    logger.info("task_images_started", flow_id=flow_id)
    asyncio.run(_generate_images_async(flow_id))


def _slide_at(slides: list[dict[str, Any]], index: int) -> dict[str, Any]:
    if index < 0 or index >= len(slides):
        raise IndexError(f"slide index {index} out of range")
    slide = slides[index]
    text = str(slide.get("prompt") or slide.get("image_prompt") or "").strip()
    if not text:
        raise ValueError(f"Slide {index + 1} has no prompt text")
    return slide


async def _generate_images_async(flow_id: str) -> None:
    from app.integrations.claude_vision import audit_typography
    from app.integrations.fal_client import build_flux_prompt, generate_carousel, generate_one
    from app.state import machine as fsm
    from app.state.redis_store import load_flow, save_flow

    flow_data = await load_flow(flow_id)
    if flow_data is None:
        logger.error("flow_not_found", flow_id=flow_id)
        return

    slides_raw = flow_data.get("prompts", [])
    slides: list[dict[str, Any]] = slides_raw if isinstance(slides_raw, list) else []
    visual_style = str(flow_data.get("visual_style", "cinematic"))
    telegram_user_id = int(flow_data.get("telegram_user_id", 0))
    regen_raw = flow_data.get("regen_slides", [])
    regen_slides: list[int] = regen_raw if isinstance(regen_raw, list) else []
    urls_raw = flow_data.get("image_urls", [])
    existing_urls: list[str] = urls_raw if isinstance(urls_raw, list) else []

    if not slides:
        logger.error("generate_images_no_prompts", flow_id=flow_id)
        await fsm.transition(flow_id, "fail", updates={"error": "No prompts in flow"})
        await send_user_text(
            telegram_user_id,
            "Não há prompts para gerar imagens. Volte e gere os prompts novamente.",
        )
        return

    try:
        if regen_slides and existing_urls:
            # Partial regeneration: only regenerate selected slide indexes
            valid_idxs = [i for i in regen_slides if i < len(slides)]
            tasks = [
                generate_one(
                    build_flux_prompt(_slide_at(slides, i), visual_style),
                    visual_style,
                    flow_id,
                    i,
                )
                for i in valid_idxs
            ]
            new_urls = await asyncio.gather(*tasks)
            for idx, url in zip(valid_idxs, new_urls, strict=True):
                if idx < len(existing_urls):
                    existing_urls[idx] = url
                else:
                    existing_urls.append(url)
            image_urls = existing_urls
        else:
            image_urls = await generate_carousel(
                prompts=slides,
                style=visual_style,
                flow_id=flow_id,
            )
    except Exception as exc:
        logger.error("image_generation_failed", flow_id=flow_id, error=str(exc))
        await fsm.transition(flow_id, "fail", updates={"error": str(exc)})
        await send_user_text(
            telegram_user_id,
            "Erro ao gerar imagens. Tente /novo novamente.",
        )
        return

    # ── Claude vision: audit typography on every generated image ─────────────
    audit: list[dict[str, Any]] = []
    audit_status = "ok"
    try:
        audit = await audit_typography(
            image_urls=image_urls,
            slides=slides,
            flow_id=flow_id,
        )
    except Exception as exc:
        audit_status = f"failed:{type(exc).__name__}"
        logger.warning("typography_audit_failed", flow_id=flow_id, error=str(exc))

    merged = {
        **flow_data,
        "image_urls": image_urls,
        "regen_slides": [],
        "typography_audit": audit,
        "typography_audit_status": audit_status,
    }
    await save_flow(flow_id, merged)
    await fsm.transition(flow_id, "images_done")
    merged["stage"] = "IMAGES_APPROVED"
    sync_flow_snapshot_to_supabase(flow_id, merged)

    await send_photo_group(telegram_user_id, image_urls)

    audit_summary = _format_audit_summary(audit, audit_status)
    intro = "Imagens geradas. Revise o preview, publique, regenere ou troque o estilo."
    body = f"{intro}\n\n{audit_summary}" if audit_summary else intro
    await send_user_text(
        telegram_user_id,
        body,
        reply_markup=image_approval_keyboard(),
    )
    logger.info(
        "task_images_done",
        flow_id=flow_id,
        image_count=len(image_urls),
        audit_status=audit_status,
        audit_failures=sum(1 for a in audit if a.get("verdict") == "fail"),
    )


def _format_audit_summary(
    audit: list[dict[str, Any]],
    audit_status: str,
) -> str:
    """Render the typography audit as a short Telegram message block."""
    if audit_status != "ok":
        return f"[Auditoria de tipografia: {audit_status}]"
    if not audit:
        return ""
    lines = ["Auditoria de tipografia (Claude vision):"]
    for item in audit:
        slide = item.get("slide", "?")
        verdict = str(item.get("verdict", "?")).upper()
        text_match = "✓" if item.get("text_match") else "✗"
        m_score = item.get("montserrat_match", "?")
        leg = item.get("legibility", "?")
        notes = str(item.get("notes", "")).strip()
        lines.append(
            f"Slide {slide} [{verdict}] text={text_match} "
            f"Montserrat={m_score}/10 legibilidade={leg}/10"
        )
        if notes:
            lines.append(f"  → {notes}")
    fails = [a.get("slide") for a in audit if a.get("verdict") == "fail"]
    if fails:
        lines.append("")
        lines.append(
            "Slides com problema: " + ", ".join(str(s) for s in fails)
            + ". Use 'Regenerar' para refazer só esses."
        )
    return "\n".join(lines)
