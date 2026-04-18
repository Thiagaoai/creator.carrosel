"""Declarative FSM state and transition definitions (SDD §2.3)."""

from __future__ import annotations

# ── States ────────────────────────────────────────────────────────────────────

STATES: list[str] = [
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

TERMINAL_STATES: frozenset[str] = frozenset({"COMPLETED", "FAILED", "CANCELLED"})

# ── Transitions ───────────────────────────────────────────────────────────────
# Each entry: {"trigger": str, "source": str | list[str], "dest": str}

TRANSITIONS: list[dict[str, object]] = [
    # Normal happy path
    {"trigger": "start_research", "source": "INIT", "dest": "RESEARCHING"},
    {"trigger": "research_done", "source": "RESEARCHING", "dest": "TOPIC_SELECTED"},
    {"trigger": "select_topic", "source": "TOPIC_SELECTED", "dest": "COUNT_SELECTED"},
    {"trigger": "select_count", "source": "COUNT_SELECTED", "dest": "STYLE_SELECTED"},
    {"trigger": "select_style", "source": "STYLE_SELECTED", "dest": "STYLE_SELECTED"},
    {"trigger": "prompts_done", "source": "STYLE_SELECTED", "dest": "PROMPTS_READY"},
    {"trigger": "regenerate_prompts", "source": "PROMPTS_READY", "dest": "STYLE_SELECTED"},
    {"trigger": "approve_prompts", "source": "PROMPTS_READY", "dest": "PROMPTS_APPROVED"},
    {"trigger": "start_images", "source": "PROMPTS_APPROVED", "dest": "GENERATING_IMAGES"},
    # Single-step shortcut: avoids double lock acquisition in the approve flow
    {"trigger": "approve_and_start", "source": "PROMPTS_READY", "dest": "GENERATING_IMAGES"},
    {"trigger": "images_done", "source": "GENERATING_IMAGES", "dest": "IMAGES_APPROVED"},
    {"trigger": "start_publish", "source": "IMAGES_APPROVED", "dest": "PUBLISHING"},
    {"trigger": "publish_done", "source": "PUBLISHING", "dest": "COMPLETED"},
    {"trigger": "change_style", "source": "IMAGES_APPROVED", "dest": "STYLE_SELECTED"},
    # Re-generation path: user rejects images and asks to regenerate specific slides
    {"trigger": "request_regen", "source": "IMAGES_APPROVED", "dest": "REGENERATING"},
    {"trigger": "regen_done", "source": "REGENERATING", "dest": "GENERATING_IMAGES"},
    # Single-step shortcut: avoids double lock acquisition in the regen flow
    {"trigger": "request_and_start_regen", "source": "IMAGES_APPROVED", "dest": "GENERATING_IMAGES"},
    # Prompt editing: user edits a prompt before approval
    {"trigger": "edit_prompts", "source": "PROMPTS_READY", "dest": "PROMPTS_READY"},
    # Failure path (from any non-terminal state)
    {
        "trigger": "fail",
        "source": [
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
        "dest": "FAILED",
    },
    # Cancellation path (from any non-terminal state)
    {
        "trigger": "cancel",
        "source": [
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
        "dest": "CANCELLED",
    },
]
