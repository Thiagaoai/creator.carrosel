"""Unit tests for Telegram inline keyboards."""

from __future__ import annotations

from app.telegram.keyboards import (
    approval_keyboard,
    image_approval_keyboard,
    prompt_adjust_keyboard,
    regenerate_keyboard,
    slide_count_keyboard,
    style_keyboard,
    topics_keyboard,
)


def test_topics_keyboard_creates_one_button_per_topic() -> None:
    """Topic research results should map one-to-one to inline buttons."""
    keyboard = topics_keyboard(
        [
            {"title": "Topic 1"},
            {"title": "Topic 2"},
            {"title": "Topic 3"},
        ]
    )
    assert len(keyboard.inline_keyboard) == 3
    assert keyboard.inline_keyboard[0][0].callback_data == "topic:0"


def test_slide_count_keyboard_uses_expected_values() -> None:
    """The product only supports the documented slide-count options."""
    keyboard = slide_count_keyboard()
    labels = [button.text for button in keyboard.inline_keyboard[0]]
    assert labels == ["1", "3", "5", "7", "10"]


def test_style_keyboard_contains_eight_styles() -> None:
    """The style picker should expose all eight MVP styles."""
    keyboard = style_keyboard()
    flat_buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert len(flat_buttons) == 8


def test_prompt_adjust_keyboard_includes_back_navigation() -> None:
    """Adjust-slide menu should include slide selectors and a back button."""
    keyboard = prompt_adjust_keyboard(5)
    flat_buttons = [button for row in keyboard.inline_keyboard for button in row]
    assert any(button.callback_data == "approve:edit:5" for button in flat_buttons)
    assert flat_buttons[-1].callback_data == "approve:menu"


def test_approval_keyboard_exposes_three_core_actions() -> None:
    """Prompt approval UI should support approve, regenerate, and edit flows."""
    keyboard = approval_keyboard()
    flat_callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert flat_callbacks == ["approve:all", "approve:regen", "approve:edit_menu"]


def test_image_approval_keyboard_exposes_preview_and_recovery_actions() -> None:
    """Image review UI should match the MVP hardening requirements."""
    keyboard = image_approval_keyboard()
    flat_callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "publish:preview" in flat_callbacks
    assert "publish:now" in flat_callbacks
    assert "regen:menu" in flat_callbacks
    assert "style:change" in flat_callbacks
    assert "cancel:flow" in flat_callbacks


def test_regenerate_keyboard_builds_confirm_action() -> None:
    """Partial regeneration needs explicit confirmation."""
    keyboard = regenerate_keyboard([0, 1, 2])
    flat_callbacks = [button.callback_data for row in keyboard.inline_keyboard for button in row]
    assert "regen:0" in flat_callbacks
    assert "regen:confirm" in flat_callbacks
