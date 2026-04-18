"""Telegram command handlers: /novo /status /cancelar /historico /custo /marca."""

from __future__ import annotations

import contextlib
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from app.config import VALID_BRANDS, settings
from app.state import machine as fsm
from app.state import redis_store
from app.utils.logging import get_logger
from app.utils.security import require_allowed

logger = get_logger(__name__)


async def cmd_novo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Start a new carousel flow and immediately research current topics."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    explicit_brand = ctx.args[0].lower() if ctx.args else None
    stored_default_brand = await redis_store.get_user_default_brand(user_id)
    brand = explicit_brand or stored_default_brand or "thiagaoai"
    if brand not in VALID_BRANDS:
        valid = ", ".join(sorted(VALID_BRANDS))
        await update.message.reply_text(f"Marca inválida: {brand}.\nMarcas disponíveis: {valid}")
        return

    existing = await redis_store.get_user_active_flow(user_id)
    if existing:
        await update.message.reply_text(
            f"Você já tem um fluxo ativo ({existing[:8]}...). Use /cancelar antes de iniciar outro."
        )
        return

    allowed = await redis_store.check_and_increment_rate(
        user_id,
        limit=settings.rate_limit_carousels_per_hour,
        window_seconds=3600,
        window_name="hour_carousels",
    )
    if not allowed:
        await update.message.reply_text("Limite de carrosséis por hora atingido. Tente mais tarde.")
        return

    flow_id = await fsm.start_flow(telegram_user_id=user_id, brand=brand)
    logger.info("cmd_novo", flow_id=flow_id, user_id=user_id, brand=brand)

    await update.message.reply_text(
        (
            f"Novo fluxo iniciado para *{brand}*.\n\n"
            "Qual o *tópico* do carrossel? Envie em uma mensagem o assunto "
            "(ex.: \"lançamentos de IA generativa\", \"dicas de café especial\", "
            "\"novidades do mercado de docks\"...).\n\n"
            "Vou buscar *10 opções atuais* dentro do tópico para você escolher."
        ),
        parse_mode="Markdown",
    )


async def cmd_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show current flow status for the calling user."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    flow_id = await redis_store.get_user_active_flow(user_id)
    if not flow_id:
        await update.message.reply_text("Nenhum fluxo ativo no momento.")
        return

    data = await redis_store.load_flow(flow_id)
    if not data:
        await update.message.reply_text("Fluxo expirado ou não encontrado.")
        return

    stage = str(data.get("stage", "?"))
    brand = str(data.get("brand", "?"))
    topic = data.get("topic_chosen")
    topic_title = topic.get("title") if isinstance(topic, dict) else None
    lines = [
        f"Fluxo: `{flow_id[:8]}...`",
        f"Marca: *{brand}*",
        f"Estágio: `{stage}`",
    ]
    if topic_title:
        lines.append(f"Tópico: {topic_title}")
    await update.message.reply_text("\n".join(lines), parse_mode="Markdown")


async def cmd_cancelar(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Cancel the active carousel flow."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    flow_id = await redis_store.get_user_active_flow(user_id)
    if not flow_id:
        await update.message.reply_text("Nenhum fluxo ativo para cancelar.")
        return

    with contextlib.suppress(Exception):
        await fsm.transition(flow_id, "cancel")

    await redis_store.clear_user_active_flow(user_id)
    logger.info("flow_cancelled", flow_id=flow_id, user_id=user_id)
    await update.message.reply_text("Fluxo cancelado.")


async def cmd_historico(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the last 10 completed carousels for this user."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    try:
        from app.integrations.supabase_client import list_completed_flows

        rows = list_completed_flows(user_id, limit=10)
    except Exception as exc:
        logger.warning("historico_error", error=str(exc), user_id=user_id)
        await update.message.reply_text("Erro ao buscar histórico.")
        return

    if not rows:
        await update.message.reply_text("Nenhum carrossel encontrado.")
        return

    lines = ["Últimos 10 carrosséis:\n"]
    for row in rows:
        created_at = str(row.get("created_at", "?"))[:10]
        brand = row.get("brand", "?")
        link = row.get("instagram_permalink") or "sem link"
        lines.append(f"• {created_at} | {brand} | {link}")
    await update.message.reply_text("\n".join(lines))


async def cmd_custo(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """Show the current-month cost summary for the calling user."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    try:
        from app.integrations.supabase_client import monthly_cost_breakdown

        rows = monthly_cost_breakdown(user_id)
    except Exception as exc:
        logger.warning("custo_error", error=str(exc), user_id=user_id)
        await update.message.reply_text("Erro ao buscar custos.")
        return

    if not rows:
        await update.message.reply_text("Sem dados de custo neste mês.")
        return

    totals_by_service: dict[str, float] = defaultdict(float)
    total_cost = 0.0
    for row in rows:
        service = str(row.get("service", "unknown"))
        cost = float(row.get("cost_usd") or 0.0)
        totals_by_service[service] += cost
        total_cost += cost

    lines = ["Custos do mês atual:\n"]
    for service, cost in sorted(totals_by_service.items()):
        lines.append(f"• {service}: ${cost:.4f}")
    lines.append(f"\nTotal: ${total_cost:.4f}")
    await update.message.reply_text("\n".join(lines))


async def cmd_marca(update: Update, ctx: ContextTypes.DEFAULT_TYPE) -> None:
    """List brands or persist the user's default brand."""
    if update.effective_user is None or update.message is None:
        return

    user_id = update.effective_user.id
    try:
        require_allowed(user_id)
    except ValueError:
        await update.message.reply_text("Acesso negado.")
        return

    if not ctx.args:
        current_default = await redis_store.get_user_default_brand(user_id) or "thiagaoai"
        lines = [f"Marca padrão atual: `{current_default}`\n", "Marcas disponíveis:"]
        for brand in sorted(VALID_BRANDS):
            lines.append(f"• `{brand}`")
        lines.append("\nUso: /marca <nome>")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")
        return

    brand = ctx.args[0].lower()
    if brand not in VALID_BRANDS:
        valid = ", ".join(sorted(VALID_BRANDS))
        await update.message.reply_text(f"Marca inválida: {brand}.\nMarcas disponíveis: {valid}")
        return

    await redis_store.set_user_default_brand(user_id, brand)
    await update.message.reply_text(
        f"Marca padrão atualizada para *{brand}*. Agora `/novo` vai usar essa marca.",
        parse_mode="Markdown",
    )
