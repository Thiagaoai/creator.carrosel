"""Inline keyboard builders for the Telegram carousel workflow."""

from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup

from app.visual_styles import VISUAL_STYLES

SLIDE_COUNTS: list[int] = [1, 3, 5, 7, 10]


def topics_keyboard(topics: list[dict[str, str]]) -> InlineKeyboardMarkup:
    """Build a keyboard with one button per research topic.

    Each button callback_data: ``topic:<index>``
    """
    buttons = [
        [InlineKeyboardButton(text=f"{i + 1}. {t['title']}", callback_data=f"topic:{i}")]
        for i, t in enumerate(topics)
    ]
    return InlineKeyboardMarkup(buttons)


def slide_count_keyboard() -> InlineKeyboardMarkup:
    """Build a single-row keyboard for choosing the number of slides."""
    row = [
        InlineKeyboardButton(text=str(n), callback_data=f"count:{n}")
        for n in SLIDE_COUNTS
    ]
    return InlineKeyboardMarkup([row])


def style_keyboard() -> InlineKeyboardMarkup:
    """Build a 2-column keyboard for choosing the visual style."""
    buttons: list[list[InlineKeyboardButton]] = []
    for i in range(0, len(VISUAL_STYLES), 2):
        row = [
            InlineKeyboardButton(text=style.label, callback_data=f"style:{style.key}")
            for style in VISUAL_STYLES[i : i + 2]
        ]
        buttons.append(row)
    return InlineKeyboardMarkup(buttons)


def prompt_adjust_keyboard(slide_count: int) -> InlineKeyboardMarkup:
    """Build a keyboard for selecting which prompt slide to adjust."""
    rows: list[list[InlineKeyboardButton]] = []
    current_row: list[InlineKeyboardButton] = []
    for slide_number in range(1, slide_count + 1):
        current_row.append(
            InlineKeyboardButton(
                text=f"Slide {slide_number}",
                callback_data=f"approve:edit:{slide_number}",
            )
        )
        if len(current_row) == 3:
            rows.append(current_row)
            current_row = []
    if current_row:
        rows.append(current_row)
    rows.append([InlineKeyboardButton(text="Voltar", callback_data="approve:menu")])
    return InlineKeyboardMarkup(rows)


def approval_keyboard() -> InlineKeyboardMarkup:
    """Build the prompt approval keyboard for the MVP flow."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Aprovar tudo", callback_data="approve:all"),
                InlineKeyboardButton(text="Regenerar tudo", callback_data="approve:regen"),
            ],
            [InlineKeyboardButton(text="Ajustar slide", callback_data="approve:edit_menu")],
        ]
    )


def image_approval_keyboard() -> InlineKeyboardMarkup:
    """Build the image approval keyboard with publish and recovery options."""
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(text="Ver preview", callback_data="publish:preview"),
                InlineKeyboardButton(text="Publicar", callback_data="publish:now"),
            ],
            [
                InlineKeyboardButton(text="Regenerar tudo", callback_data="regen:all"),
                InlineKeyboardButton(text="Regenerar slide", callback_data="regen:menu"),
            ],
            [
                InlineKeyboardButton(text="Trocar estilo", callback_data="style:change"),
                InlineKeyboardButton(text="Descartar tudo", callback_data="cancel:flow"),
            ],
        ]
    )


def regenerate_keyboard(slide_indexes: list[int]) -> InlineKeyboardMarkup:
    """Build a keyboard for selecting which specific slides to regenerate.

    Args:
        slide_indexes: Zero-based list of slide indices available for regeneration.

    Each button callback_data: ``regen:<index>``
    """
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for idx in slide_indexes:
        row.append(
            InlineKeyboardButton(
                text=f"Slide {idx + 1}", callback_data=f"regen:{idx}"
            )
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append(
        [InlineKeyboardButton(text="Confirmar regeneração", callback_data="regen:confirm")]
    )
    buttons.append([InlineKeyboardButton(text="Voltar", callback_data="regen:menu")])
    return InlineKeyboardMarkup(buttons)


def cancel_keyboard() -> InlineKeyboardMarkup:
    """Build a simple cancel button."""
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(text="Cancelar", callback_data="cancel:flow")]]
    )
