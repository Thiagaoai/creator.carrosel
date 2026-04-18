"""callback_query handler — routes inline button presses by prefix."""

from __future__ import annotations

import contextlib

from telegram import CallbackQuery, Update
from telegram.ext import ContextTypes

from app.state import machine as fsm
from app.state import redis_store
from app.utils.logging import bind_flow_context, get_logger
from app.utils.security import require_allowed
from app.visual_styles import normalize_visual_style, visual_style_label

logger = get_logger(__name__)


async def handle_callback(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Route all inline keyboard callbacks based on their data prefix."""
    query = update.callback_query
    if query is None or query.from_user is None:
        return

    user_id = query.from_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await query.answer("Acesso negado.")
        return

    from app.config import settings

    allowed = await redis_store.check_and_increment_rate(
        user_id,
        limit=settings.rate_limit_callbacks_per_minute,
        window_seconds=60,
        window_name="min_callbacks",
    )
    if not allowed:
        await query.answer("Muitas ações. Aguarde um momento.")
        return

    if query.id and await redis_store.is_duplicate(query.id):
        await query.answer()
        return

    await query.answer()

    flow_id = await redis_store.get_user_active_flow(user_id)
    if not flow_id:
        if query.message is not None:
            await query.edit_message_text("Fluxo não encontrado. Use /novo para começar.")
        return

    bind_flow_context(flow_id, user_id=user_id)

    data = query.data or ""
    parts = data.split(":")
    prefix = parts[0]
    payload = parts[1:]

    handler_map = {
        "topic": _on_topic,
        "count": _on_count,
        "style": _on_style,
        "approve": _on_approve,
        "regen": _on_regen,
        "publish": _on_publish,
        "cancel": _on_cancel,
    }
    handler = handler_map.get(prefix)
    if handler is None:
        logger.warning("unknown_callback_prefix", prefix=prefix, data=data)
        return

    await handler(query, flow_id, payload)


async def _on_topic(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """User selected a research topic."""
    try:
        index = int(payload[0])
    except (IndexError, ValueError):
        await query.edit_message_text("Seleção inválida.")
        return

    flow_data = await redis_store.load_flow(flow_id)
    if not flow_data:
        await query.edit_message_text("Fluxo expirado.")
        return

    topics = flow_data.get("topics", [])
    if not isinstance(topics, list) or index >= len(topics):
        await query.edit_message_text("Tópico inválido.")
        return

    chosen = topics[index]
    from app.telegram.keyboards import slide_count_keyboard

    await fsm.transition(flow_id, "select_topic", updates={"topic_chosen": chosen})
    await query.edit_message_text(
        f"Tópico selecionado: *{chosen['title']}*\n\nQuantos slides?",
        parse_mode="Markdown",
        reply_markup=slide_count_keyboard(),
    )


async def _on_count(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """User selected slide count."""
    try:
        count = int(payload[0])
    except (IndexError, ValueError):
        await query.edit_message_text("Valor inválido.")
        return

    from app.telegram.keyboards import style_keyboard

    await fsm.transition(flow_id, "select_count", updates={"slide_count": count})
    await query.edit_message_text(
        f"Slides: *{count}*. Qual estilo visual?",
        parse_mode="Markdown",
        reply_markup=style_keyboard(),
    )


async def _on_style(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """User selected or changed the visual style."""
    from app.telegram.keyboards import style_keyboard

    flow_data = await redis_store.load_flow(flow_id)
    if flow_data is None:
        await query.edit_message_text("Fluxo expirado.")
        return

    action = payload[0] if payload else ""
    if action == "change":
        await fsm.transition(flow_id, "change_style")
        await query.edit_message_text(
            "Escolha um novo estilo visual para refazer os prompts e as imagens:",
            reply_markup=style_keyboard(),
        )
        return

    style_key = normalize_visual_style(action)
    await fsm.transition(flow_id, "select_style", updates={"visual_style": style_key})
    await query.edit_message_text(
        f"Estilo: *{visual_style_label(style_key)}*. Gerando prompts...",
        parse_mode="Markdown",
    )

    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.prompts.generate_prompts", args=[flow_id])


async def _on_approve(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """Handle prompt approval, regeneration, and per-slide adjustments."""
    from app.telegram.keyboards import approval_keyboard, prompt_adjust_keyboard

    action = payload[0] if payload else ""
    flow_data = await redis_store.load_flow(flow_id)
    if flow_data is None:
        await query.edit_message_text("Fluxo expirado.")
        return

    if action == "all":
        await fsm.transition(flow_id, "approve_prompts")
        await fsm.transition(flow_id, "start_images")
        await query.edit_message_text("Prompts aprovados. Gerando imagens...")

        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.images.generate_images", args=[flow_id])
        return

    if action == "regen":
        await fsm.transition(flow_id, "regenerate_prompts")
        await query.edit_message_text("Regenerando todos os prompts...")

        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.prompts.generate_prompts", args=[flow_id])
        return

    if action == "menu":
        await query.edit_message_text("Menu de prompts:", reply_markup=approval_keyboard())
        return

    if action == "edit_menu":
        slide_count = int(flow_data.get("slide_count", 1))
        await query.edit_message_text(
            "Qual slide você quer ajustar?",
            reply_markup=prompt_adjust_keyboard(slide_count),
        )
        return

    if action == "edit":
        try:
            slide_num = int(payload[1])
        except (IndexError, ValueError):
            await query.answer("Slide inválido.")
            return

        await redis_store.save_flow(
            flow_id,
            {
                **flow_data,
                "pending_prompt_slide": slide_num,
            },
        )
        try:
            await fsm.transition(flow_id, "edit_prompts")
        except Exception as exc:
            logger.warning("edit_prompts_failed", flow_id=flow_id, error=str(exc))

        await query.edit_message_text(
            f"Envie a nova versão do prompt do slide {slide_num}.",
            reply_markup=approval_keyboard(),
        )
        return

    await query.answer("Ação não reconhecida.")


async def _on_regen(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """Handle image regeneration flows."""
    from app.telegram.keyboards import image_approval_keyboard, regenerate_keyboard

    flow_data = await redis_store.load_flow(flow_id)
    if flow_data is None:
        await query.edit_message_text("Fluxo expirado.")
        return

    action = payload[0] if payload else ""
    if action == "menu":
        prompts = flow_data.get("prompts", [])
        slide_indexes = list(range(len(prompts))) if isinstance(prompts, list) else []
        await query.edit_message_text(
            "Escolha quais slides devem ser regenerados:",
            reply_markup=regenerate_keyboard(slide_indexes),
        )
        return

    if action == "all":
        await fsm.transition(flow_id, "request_regen")
        await fsm.transition(flow_id, "regen_done")
        await query.edit_message_text("Regenerando todas as imagens...")

        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.images.generate_images", args=[flow_id])
        return

    if action == "confirm":
        regen_slides = flow_data.get("regen_slides", [])
        if not regen_slides:
            await query.edit_message_text(
                "Nenhum slide foi selecionado. Escolha ao menos um.",
                reply_markup=image_approval_keyboard(),
            )
            return
        await fsm.transition(flow_id, "request_regen")
        await fsm.transition(flow_id, "regen_done")
        await query.edit_message_text("Regenerando slides selecionados...")

        from app.tasks.celery_app import celery_app

        celery_app.send_task("app.tasks.images.generate_images", args=[flow_id])
        return

    try:
        idx = int(action)
    except ValueError:
        await query.answer("Índice inválido.")
        return

    prompts = flow_data.get("prompts", [])
    if not isinstance(prompts, list) or idx >= len(prompts):
        await query.answer("Slide inválido.")
        return

    regen_list = flow_data.get("regen_slides", [])
    selected = list(regen_list) if isinstance(regen_list, list) else []
    if idx not in selected:
        selected.append(idx)
    await redis_store.save_flow(flow_id, {**flow_data, "regen_slides": selected})
    await query.answer(f"Slide {idx + 1} marcado para regeneração.")


async def _on_publish(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """Handle preview and final publication."""
    action = payload[0] if payload else "now"
    flow_data = await redis_store.load_flow(flow_id)
    if flow_data is None:
        await query.edit_message_text("Fluxo expirado.")
        return

    telegram_user_id = int(flow_data.get("telegram_user_id", 0))
    if action == "preview":
        from app.tasks.publish import build_caption_preview
        from app.telegram.notify import send_user_text

        preview = build_caption_preview(flow_data)
        await send_user_text(telegram_user_id, preview)
        return

    await fsm.transition(flow_id, "start_publish")
    await query.edit_message_text("Publicando no Instagram...")

    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.publish.publish", args=[flow_id])


async def _on_cancel(query: CallbackQuery, flow_id: str, payload: list[str]) -> None:
    """User cancelled the flow via inline button."""
    with contextlib.suppress(Exception):
        await fsm.transition(flow_id, "cancel")

    user_id = query.from_user.id if query.from_user else 0
    await redis_store.clear_user_active_flow(user_id)
    await query.edit_message_text("Fluxo cancelado.")
