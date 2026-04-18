"""Celery task: generate carousel prompts via DeepSeek + mandatory Claude judge."""

from __future__ import annotations

import asyncio
from typing import Any

from app.integrations.supabase_client import sync_flow_snapshot_to_supabase
from app.tasks.celery_app import celery_app
from app.telegram.notify import send_user_text
from app.utils.logging import bind_flow_context, get_logger

logger = get_logger(__name__)


@celery_app.task(name="app.tasks.prompts.generate_prompts", bind=True, max_retries=3)  # type: ignore[untyped-decorator]
def generate_prompts(self: Any, flow_id: str) -> None:
    """Generate carousel prompts for a flow.

    Pipeline (SDD §4.3 + §4.4 — updated):
    1. DeepSeek V3 drafts the full carousel (story_arc + N slides).
    2. Local validator scores the draft (informational signal only).
    3. Claude Sonnet ALWAYS reviews every slide as a senior art director
       and returns a polished, FLUX-ready set. This is no longer a
       fallback; Claude is the mandatory quality gate.
    4. Persist prompts and notify the user with the approval keyboard.
    """
    from app.state.redis_store import reset_redis_client
    reset_redis_client()
    bind_flow_context(flow_id)
    logger.info("task_prompts_started", flow_id=flow_id)
    asyncio.run(_generate_prompts_async(flow_id))


async def _generate_prompts_async(flow_id: str) -> None:
    from app.brands.registry import get_preset
    from app.integrations.claude import judge_and_polish_prompts
    from app.integrations.deepseek import generate_prompts as deepseek_generate
    from app.state import machine as fsm
    from app.state.redis_store import load_flow, save_flow
    from app.telegram.keyboards import approval_keyboard
    from app.validators.prompt_validator import score_prompts
    from app.visual_styles import visual_style_label, visual_style_prompt_hint

    flow_data = await load_flow(flow_id)
    if flow_data is None:
        logger.error("flow_not_found", flow_id=flow_id)
        return

    brand = str(flow_data.get("brand", ""))
    topic_raw = flow_data.get("topic_chosen", {})
    topic: dict[str, str] = topic_raw if isinstance(topic_raw, dict) else {}
    slide_count = int(flow_data.get("slide_count", 5))
    visual_style = str(flow_data.get("visual_style", "cinematic"))
    caption_language = str(flow_data.get("caption_language", "pt-br"))
    telegram_user_id = int(flow_data.get("telegram_user_id", 0))
    theme_seed = str(topic.get("title") or topic.get("summary") or brand)

    preset = get_preset(brand)

    # ── 1. DeepSeek draft ────────────────────────────────────────────────────
    try:
        draft = await deepseek_generate(
            theme_seed=theme_seed,
            topic=topic,
            slide_count=slide_count,
            visual_style=visual_style,
            brand_name=brand,
            brand_preset=preset,
            flow_id=flow_id,
            caption_language=caption_language,
        )
    except Exception as exc:
        logger.error("prompt_generation_failed", flow_id=flow_id, error=str(exc))
        await fsm.transition(flow_id, "fail", updates={"error": str(exc)})
        await send_user_text(
            telegram_user_id,
            "Erro ao gerar prompts. Tente /novo novamente.",
        )
        return

    draft_slides: list[dict[str, Any]] = draft.get("slides", [])
    draft_story_arc: str = draft.get("story_arc", "")

    # ── 2. Local validator (signal only — never gates the flow anymore) ──────
    brand_rules = {"required_keywords": preset.get("required_keywords", [])}
    validation = score_prompts(draft_slides, brand_rules)
    validator_signal = {
        "average": validation.average,
        "scores": validation.scores,
        "problematic_slides": validation.problematic_slides,
    }
    logger.info(
        "deepseek_draft_scored",
        flow_id=flow_id,
        validator_average=validation.average,
        problematic=validation.problematic_slides,
    )

    # ── 3. Claude as mandatory design judge ──────────────────────────────────
    visual_style_payload = {
        "key": visual_style,
        "label": visual_style_label(visual_style),
        "prompt_hint": visual_style_prompt_hint(visual_style),
    }
    final_slides: list[dict[str, Any]] = draft_slides
    final_story_arc: str = draft_story_arc
    judge_status = "polished"
    try:
        polished = await judge_and_polish_prompts(
            slides=draft_slides,
            story_arc=draft_story_arc,
            theme_seed=theme_seed,
            topic=topic,
            visual_style=visual_style_payload,
            caption_language=caption_language,
            brand_name=brand,
            brand_preset=preset,
            validator_signal=validator_signal,
            flow_id=flow_id,
        )
        polished_slides = polished.get("slides", [])
        if isinstance(polished_slides, list) and polished_slides:
            final_slides = polished_slides
            final_story_arc = str(polished.get("story_arc") or draft_story_arc)
        else:
            judge_status = "empty_fallback_to_draft"
    except Exception as exc:
        # Claude failure must not break the flow — fall back to DeepSeek draft.
        judge_status = f"failed:{type(exc).__name__}"
        logger.warning("claude_judge_failed", flow_id=flow_id, error=str(exc))

    # ── 4. Persist and notify ────────────────────────────────────────────────
    merged = {
        **flow_data,
        "prompts": final_slides,
        "story_arc": final_story_arc,
        "deepseek_draft_slides": draft_slides,
        "deepseek_story_arc": draft_story_arc,
        "validator_signal": validator_signal,
        "judge_status": judge_status,
    }
    await save_flow(flow_id, merged)
    await fsm.transition(flow_id, "prompts_done")
    merged["stage"] = "PROMPTS_READY"
    sync_flow_snapshot_to_supabase(flow_id, merged)

    # Plain text: LLM output may break Telegram Markdown
    header = f"Story arc: {final_story_arc}"
    if judge_status != "polished":
        header += f"\n[judge: {judge_status}]"
    lines = [header + "\n"]
    for slide in final_slides:
        num = slide.get("slide", "?")
        role = slide.get("role", "?")
        story_text = str(slide.get("story_text", "")).strip()
        text_color = str(slide.get("text_color", "")).strip()
        text_weight = str(slide.get("text_weight", "")).strip()
        caption = str(slide.get("caption", ""))[:200]
        prompt_preview = str(slide.get("prompt", ""))[:120]
        judge_notes = str(slide.get("judge_notes", "")).strip()

        block = [f"Slide {num} ({role})"]
        if story_text:
            type_meta = " / ".join(p for p in [text_weight, text_color] if p)
            type_suffix = f"  [Montserrat {type_meta}]" if type_meta else "  [Montserrat]"
            block.append(f"In-image text: \"{story_text}\"{type_suffix}")
        block.append(f"Caption: {caption}")
        block.append(f"Prompt: {prompt_preview}...")
        if judge_notes:
            block.append(f"Judge: {judge_notes}\n")
        else:
            block[-1] = block[-1] + "\n"
        lines.append("\n".join(block))

    message = "\n".join(lines)
    await send_user_text(
        telegram_user_id,
        message,
        reply_markup=approval_keyboard(),
    )
    logger.info(
        "task_prompts_done",
        flow_id=flow_id,
        judge_status=judge_status,
        validator_average=validation.average,
    )
