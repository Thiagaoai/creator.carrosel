"""Shared visual-style definitions used across Telegram UX and generation tasks."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VisualStyle:
    """A supported visual style for the carousel workflow."""

    key: str
    label: str
    prompt_hint: str


VISUAL_STYLES: tuple[VisualStyle, ...] = (
    VisualStyle(
        key="informative_cards",
        label="Informative Cards",
        prompt_hint=(
            "bold typography, clean infographic layout, sharp hierarchy, "
            "editorial data-card feel"
        ),
    ),
    VisualStyle(
        key="anime_manga",
        label="Anime/Manga",
        prompt_hint=(
            "clean anime linework, manga contrast, speed lines, dynamic framing, "
            "expressive characters"
        ),
    ),
    VisualStyle(
        key="ultra_realistic",
        label="Ultra Realistic",
        prompt_hint=(
            "photo-real textures, realistic skin and materials, natural light, "
            "tactile detail"
        ),
    ),
    VisualStyle(
        key="cinematic",
        label="Cinematic",
        prompt_hint=(
            "dramatic lighting, movie-poster composition, depth, controlled grain, "
            "emotional framing"
        ),
    ),
    VisualStyle(
        key="modern_watercolor",
        label="Modern Watercolor",
        prompt_hint=(
            "soft watercolor blending, contemporary illustration, textured paper, "
            "elegant color bleeding"
        ),
    ),
    VisualStyle(
        key="anime_3d",
        label="Anime 3D",
        prompt_hint=(
            "stylized 3D animation, cinematic rim light, polished materials, "
            "anime-inspired faces"
        ),
    ),
    VisualStyle(
        key="cartoon",
        label="Cartoon",
        prompt_hint=(
            "flat graphic shapes, playful proportions, strong outlines, saturated "
            "palette, approachable tone"
        ),
    ),
    VisualStyle(
        key="editorial_magazine",
        label="Editorial Magazine",
        prompt_hint=(
            "fashion editorial composition, premium magazine mood, typography-aware "
            "negative space"
        ),
    ),
)

VISUAL_STYLE_BY_KEY: dict[str, VisualStyle] = {style.key: style for style in VISUAL_STYLES}

_LEGACY_STYLE_ALIASES: dict[str, str] = {
    "cinematografico": "cinematic",
    "minimalista": "informative_cards",
    "editorial": "editorial_magazine",
    "vibrante": "cartoon",
    "dark_luxury": "editorial_magazine",
    "aquarela": "modern_watercolor",
    "flat_design": "informative_cards",
    "fotorrealista": "ultra_realistic",
}


def normalize_visual_style(style_key: str | None) -> str:
    """Return a supported style key, mapping legacy keys when needed."""
    cleaned = (style_key or "").strip()
    if cleaned in VISUAL_STYLE_BY_KEY:
        return cleaned
    if cleaned in _LEGACY_STYLE_ALIASES:
        return _LEGACY_STYLE_ALIASES[cleaned]
    return "cinematic"


def visual_style_label(style_key: str | None) -> str:
    """Return the human-readable label for a style key."""
    style = VISUAL_STYLE_BY_KEY[normalize_visual_style(style_key)]
    return style.label


def visual_style_prompt_hint(style_key: str | None) -> str:
    """Return the prompt hint used by the model/image generators."""
    style = VISUAL_STYLE_BY_KEY[normalize_visual_style(style_key)]
    return style.prompt_hint
