"""Handler for free-text messages (fallback and prompt editing)."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from app.state import machine as fsm
from app.state import redis_store
from app.utils.logging import get_logger
from app.utils.security import require_allowed

logger = get_logger(__name__)

HELP_TEXT = (
    "Comandos disponíveis:\n"
    "/novo <marca> — Iniciar novo carrossel\n"
    "/status — Ver status do fluxo atual\n"
    "/cancelar — Cancelar fluxo ativo\n"
    "/historico — Últimos carrosséis criados\n"
    "/custo — Custos do mês atual\n"
    "/marca [nome] — Ver ou trocar a marca padrão"
)


async def handle_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle plain text messages for prompt adjustments or fallback help."""
    if update.effective_user is None or update.message is None or update.message.text is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    flow_id = await redis_store.get_user_active_flow(user_id)
    if not flow_id:
        await update.message.reply_text(HELP_TEXT)
        return

    flow_data = await redis_store.load_flow(flow_id)
    if not flow_data:
        await update.message.reply_text("Fluxo expirado. Use /novo para recomeçar.")
        return

    stage = str(flow_data.get("stage", ""))
    if stage == "INIT":
        await _handle_topic_input(update, flow_id, flow_data, update.message.text)
        return

    if stage == "PROMPTS_READY":
        await _handle_prompt_edit(update, flow_id, flow_data, update.message.text)
        return

    await update.message.reply_text(
        f"Estágio atual: `{stage}`. {HELP_TEXT}",
        parse_mode="Markdown",
    )


async def _handle_topic_input(
    update: Update,
    flow_id: str,
    flow_data: dict[str, object],
    text: str,
) -> None:
    """Save the user-provided topic and dispatch the research task."""
    if update.message is None:
        return

    user_topic = text.strip()
    if len(user_topic) < 3:
        await update.message.reply_text(
            "Tópico curto demais. Envie um assunto com pelo menos 3 caracteres."
        )
        return
    if len(user_topic) > 300:
        await update.message.reply_text(
            "Tópico longo demais (máx 300 caracteres). Resuma um pouco e tente de novo."
        )
        return

    await redis_store.save_flow(
        flow_id,
        {**flow_data, "user_topic": user_topic},
    )

    from app.tasks.celery_app import celery_app

    celery_app.send_task("app.tasks.research.research_topics", args=[flow_id])
    logger.info("topic_input_received", flow_id=flow_id, topic_len=len(user_topic))

    await update.message.reply_text(
        f"Tópico recebido: *{user_topic}*\n\nBuscando *10 opções atuais* dentro desse tema...",
        parse_mode="Markdown",
    )


async def _handle_prompt_edit(
    update: Update,
    flow_id: str,
    flow_data: dict[str, object],
    text: str,
) -> None:
    """Update one prompt using either pending slide selection or inline syntax."""
    if update.message is None:
        return

    pending_prompt_slide = flow_data.get("pending_prompt_slide")
    if isinstance(pending_prompt_slide, int):
        slide_num = pending_prompt_slide
        new_prompt_text = text.strip()
    else:
        parts = text.strip().split(" ", 1)
        if len(parts) != 2:
            await update.message.reply_text(
                "Formato: `<número do slide> <novo prompt>`\nExemplo: `3 A stunning sunset...`",
                parse_mode="Markdown",
            )
            return
        try:
            slide_num = int(parts[0])
        except ValueError:
            await update.message.reply_text("Número do slide inválido.")
            return
        new_prompt_text = parts[1].strip()

    if len(new_prompt_text) < 20:
        await update.message.reply_text(
            "O novo prompt está curto demais. Envie um texto mais específico."
        )
        return

    prompts: list[dict[str, object]] = flow_data.get("prompts", [])  # type: ignore[assignment]
    if slide_num < 1 or slide_num > len(prompts):
        await update.message.reply_text(f"Slide {slide_num} não existe. Há {len(prompts)} slides.")
        return

    prompts[slide_num - 1]["prompt"] = new_prompt_text
    await redis_store.save_flow(
        flow_id,
        {
            **flow_data,
            "prompts": prompts,
            "pending_prompt_slide": None,
        },
    )

    try:
        await fsm.transition(flow_id, "edit_prompts")
    except Exception as exc:
        logger.warning("edit_prompts_transition_failed", flow_id=flow_id, error=str(exc))

    logger.info("prompt_edited", flow_id=flow_id, slide=slide_num)
    await update.message.reply_text(
        f"Slide {slide_num} atualizado. Use os botões para aprovar, "
        "regenerar ou ajustar outro slide."
    )
