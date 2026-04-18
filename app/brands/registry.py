"""Brand preset registry — loads brand configs from Supabase with in-memory cache."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.config import VALID_BRANDS
from app.utils.logging import get_logger
from app.visual_styles import normalize_visual_style

logger = get_logger(__name__)

_PROMPTS_DIR = Path(__file__).parent / "prompts"

# In-memory cache: brand → preset dict
_cache: dict[str, dict[str, Any]] = {}

# Minimal fallback presets used when the DB row does not exist yet
_FALLBACK_PRESETS: dict[str, dict[str, Any]] = {
    brand: {
        "brand": brand,
        "palette": {"primary": "#000000", "secondary": "#ffffff", "accent": "#888888"},
        "voice": {"tone": "professional", "topics": "", "forbidden_phrases": [], "hashtags": []},
        "default_style": "cinematic",
        "system_prompt": f"You are creating content for the {brand} brand.",
        "instagram_handle": f"@{brand}",
        "caption_template": "{caption}",
        "required_keywords": [],
    }
    for brand in VALID_BRANDS
}

# Override fallback for thiagaoai with explicit AI/tech context
_FALLBACK_PRESETS["thiagaoai"] = {
    "brand": "thiagaoai",
    "palette": {"primary": "#0f0f1a", "secondary": "#1a1a2e", "accent": "#7c3aed"},
    "voice": {
        "tone": "tech-forward, informativo, direto",
        "topics": (
            "inteligencia artificial, LLMs, OpenAI, Anthropic, Google DeepMind, Meta AI, "
            "startups de IA, automacao, agentes de IA, modelos de linguagem, machine learning"
        ),
        "forbidden_phrases": ["incrivel", "revolucionario"],
        "hashtags": [
            "#AI",
            "#InteligenciaArtificial",
            "#MachineLearning",
            "#LLM",
            "#OpenAI",
            "#Tech",
        ],
    },
    "default_style": "editorial_magazine",
    "system_prompt": (
        "Voce e especialista em criar conteudo viral sobre inteligencia artificial para Instagram. "
        "A marca thiagaoai cobre: OpenAI, Anthropic, Google DeepMind, Meta AI, startups de IA, "
        "LLMs, agentes de IA, automacao inteligente e tendencias de tech. "
        "Tom: informativo, direto, sem hype excessivo."
    ),
    "instagram_handle": "@thiagaoai",
    # Post for Me social account ID for @thiagaoai (Instagram user_id: 17841400194457065)
    "postforme_social_account_id": "spc_yHK48v31utAg7B7hphu4",
    "caption_template": "{caption}",
    "required_keywords": [],
}


def get_preset(brand: str) -> dict[str, Any]:
    """Return the brand preset dict, loading from Supabase or cache.

    Falls back to a minimal default if the brand is not found in the database.
    """
    if brand in _cache:
        return _cache[brand]

    # Try loading from Supabase
    try:
        from app.integrations.supabase_client import load_brand_preset

        row = load_brand_preset(brand)
        if row:
            # Enrich with per-brand system prompt from file (if present)
            prompt_file = _PROMPTS_DIR / f"{brand}.md"
            if prompt_file.exists():
                row["system_prompt"] = prompt_file.read_text(encoding="utf-8")

            row["default_style"] = normalize_visual_style(str(row.get("default_style", "")))
            _cache[brand] = row
            logger.info("brand_preset_loaded", brand=brand, source="supabase")
            return row
    except Exception as exc:
        logger.warning("brand_preset_load_error", brand=brand, error=str(exc))

    # Fall back to built-in defaults
    preset = dict(_FALLBACK_PRESETS.get(brand, _FALLBACK_PRESETS["thiagaoai"]))

    # Try loading system prompt file even for fallback
    prompt_file = _PROMPTS_DIR / f"{brand}.md"
    if prompt_file.exists():
        preset["system_prompt"] = prompt_file.read_text(encoding="utf-8")

    preset["default_style"] = normalize_visual_style(str(preset.get("default_style", "")))
    _cache[brand] = preset
    logger.info("brand_preset_loaded", brand=brand, source="fallback")
    return preset


def invalidate_cache(brand: str | None = None) -> None:
    """Clear cached presets.  Pass brand=None to clear all."""
    if brand is None:
        _cache.clear()
    else:
        _cache.pop(brand, None)
