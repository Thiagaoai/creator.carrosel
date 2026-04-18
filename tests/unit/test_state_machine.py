"""Unit tests for the transitions-based state machine."""

from __future__ import annotations

import pytest
from transitions import MachineError

from app.state.machine import StateMachine
from app.state.transitions import STATES, TERMINAL_STATES


def test_state_catalog_matches_expected_contract() -> None:
    """The workflow states should stay aligned with the documented contract."""
    assert STATES == [
        "INIT",
        "RESEARCHING",
        "TOPIC_SELECTED",
        "COUNT_SELECTED",
        "STYLE_SELECTED",
        "PROMPTS_READY",
        "PROMPTS_APPROVED",
        "GENERATING_IMAGES",
        "IMAGES_APPROVED",
        "REGENERATING",
        "PUBLISHING",
        "COMPLETED",
        "FAILED",
        "CANCELLED",
    ]
    assert {"COMPLETED", "FAILED", "CANCELLED"} == TERMINAL_STATES


def test_happy_path_reaches_completed() -> None:
    """The primary MVP flow should reach COMPLETED without invalid transitions."""
    sm = StateMachine("happy-path")

    sm.trigger("start_research")
    sm.trigger("research_done")
    sm.trigger("select_topic")
    sm.trigger("select_count")
    sm.trigger("select_style")
    sm.trigger("prompts_done")
    sm.trigger("approve_prompts")
    sm.trigger("start_images")
    sm.trigger("images_done")
    sm.trigger("start_publish")
    sm.trigger("publish_done")

    assert sm.state == "COMPLETED"
    assert sm.is_terminal()


def test_prompt_regeneration_path_returns_to_prompts_ready() -> None:
    """Prompt regeneration should move back through STYLE_SELECTED before ready."""
    sm = StateMachine("prompt-regen", initial_state="PROMPTS_READY")

    sm.trigger("regenerate_prompts")
    assert sm.state == "STYLE_SELECTED"

    sm.trigger("select_style")
    sm.trigger("prompts_done")
    assert sm.state == "PROMPTS_READY"


def test_image_regeneration_path_returns_to_images_approved() -> None:
    """Image regeneration should route through REGENERATING and back."""
    sm = StateMachine("image-regen", initial_state="IMAGES_APPROVED")

    sm.trigger("request_regen")
    assert sm.state == "REGENERATING"

    sm.trigger("regen_done")
    assert sm.state == "GENERATING_IMAGES"

    sm.trigger("images_done")
    assert sm.state == "IMAGES_APPROVED"


def test_change_style_path_goes_back_to_style_selected() -> None:
    """Changing style after image review should reopen the style phase."""
    sm = StateMachine("change-style", initial_state="IMAGES_APPROVED")

    sm.trigger("change_style")
    assert sm.state == "STYLE_SELECTED"


@pytest.mark.parametrize(
    "start_state",
    [
        "INIT",
        "RESEARCHING",
        "TOPIC_SELECTED",
        "COUNT_SELECTED",
        "STYLE_SELECTED",
        "PROMPTS_READY",
        "PROMPTS_APPROVED",
        "GENERATING_IMAGES",
        "IMAGES_APPROVED",
        "REGENERATING",
        "PUBLISHING",
    ],
)
def test_cancel_is_valid_from_every_non_terminal_state(start_state: str) -> None:
    """Cancellation must remain available across the whole active workflow."""
    sm = StateMachine(f"cancel-{start_state}", initial_state=start_state)
    sm.trigger("cancel")
    assert sm.state == "CANCELLED"


@pytest.mark.parametrize(
    "start_state",
    [
        "RESEARCHING",
        "TOPIC_SELECTED",
        "COUNT_SELECTED",
        "STYLE_SELECTED",
        "PROMPTS_READY",
        "PROMPTS_APPROVED",
        "GENERATING_IMAGES",
        "IMAGES_APPROVED",
        "REGENERATING",
        "PUBLISHING",
    ],
)
def test_fail_is_valid_from_every_non_terminal_runtime_state(start_state: str) -> None:
    """Operational failures should stop the workflow cleanly."""
    sm = StateMachine(f"fail-{start_state}", initial_state=start_state)
    sm.trigger("fail")
    assert sm.state == "FAILED"


def test_invalid_transition_raises_machine_error() -> None:
    """Invalid triggers must remain explicit failures for safety."""
    sm = StateMachine("invalid")
    with pytest.raises(MachineError):
        sm.trigger("publish_done")


def test_can_trigger_reflects_current_state() -> None:
    """The helper should expose valid next actions."""
    sm = StateMachine("can-trigger", initial_state="PROMPTS_READY")
    assert sm.can_trigger("approve_prompts")
    assert sm.can_trigger("regenerate_prompts")
    assert sm.can_trigger("edit_prompts")
    assert not sm.can_trigger("publish_done")
