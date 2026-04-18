"""fal.ai FLUX Pro Ultra integration for image generation (SDD §4.5)."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import fal_client
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.costs import record_cost
from app.utils.logging import get_logger
from app.visual_styles import visual_style_prompt_hint

logger = get_logger(__name__)

FAL_MODEL = "fal-ai/flux-pro/v1.1-ultra"

# fal-ai/flux-pro/v1.1-ultra accepts these aspect_ratio values (see model schema on fal.ai).
# 4:5 is not listed; 3:4 is the closest portrait ratio for Instagram-style carousels.
_DEFAULT_ASPECT_RATIO = "3:4"


def _ensure_fal_credentials() -> None:
    """fal_client reads ``FAL_KEY`` from the environment — set it from Settings."""
    if not settings.fal_key:
        raise ValueError(
            "FAL_KEY is not configured. Set the fal.ai API key in the environment (FAL_KEY)."
        )
    os.environ["FAL_KEY"] = settings.fal_key


def _fal_output_dict(result: object) -> dict[str, Any]:
    """Normalize queue/result JSON to the dict that contains ``images``."""
    if not isinstance(result, dict):
        raise TypeError(f"fal result must be a dict, got {type(result)}")

    if "images" in result:
        return result

    for key in ("output", "data", "result"):
        inner = result.get(key)
        if isinstance(inner, dict) and "images" in inner:
            return inner

    raise KeyError(
        "fal response has no 'images' field",
    )


def _first_image_url(images_block: dict[str, Any]) -> str:
    images = images_block.get("images")
    if not isinstance(images, list) or not images:
        raise KeyError("fal 'images' list is missing or empty")
    first = images[0]
    if not isinstance(first, dict):
        raise TypeError("fal image entry is not an object")
    url = first.get("url")
    if not url or not isinstance(url, str):
        raise KeyError("fal image entry has no string 'url'")
    return str(url)


def _slide_prompt_text(slide: dict[str, Any], index: int) -> str:
    raw = slide.get("prompt") or slide.get("image_prompt") or ""
    text = str(raw).strip()
    if not text:
        raise ValueError(f"Slide {index + 1} has no 'prompt' text for image generation")
    return text


# Visual fingerprint of Montserrat — given to FLUX so it has concrete features
# to chase instead of just a font name (which it tends to ignore).
_MONTSERRAT_FINGERPRINT = (
    "geometric sans-serif typeface, Montserrat, Bauhaus-inspired urban grotesque, "
    "tall x-height, perfectly circular 'O' and 'C', double-story 'a' with a "
    "horizontal terminal, single-story 'g' with an open tail, even uniform "
    "stroke contrast (almost monolinear), wide letter apertures, slightly "
    "extended proportions, modern signage feel, crisp vector-clean letterforms, "
    "perfect kerning, no italics, no serifs, no ligature artifacts, no double "
    "letters, no garbled glyphs, no spelling mistakes"
)

_TYPOGRAPHY_DIRECTIVE = (
    f"Typography: render the in-image text using a {_MONTSERRAT_FINGERPRINT}. "
    "Reserve clear negative space (top band, bottom band, or a soft "
    "semi-transparent overlay) so the text is fully legible. The typography "
    "must visually harmonize with the colors and mood of the underlying image."
)


def build_flux_prompt(slide: dict[str, Any], style: str) -> str:
    """Assemble the FLUX prompt for a single slide.

    Promotes ``story_text``, ``text_color`` and ``text_weight`` to a hard
    top-line directive so the model cannot ignore them, then appends the
    descriptive scene prompt and the Montserrat typography contract.
    """
    base_prompt = str(slide.get("prompt") or slide.get("image_prompt") or "").strip()
    if not base_prompt:
        raise ValueError("Slide has no 'prompt' text for image generation")

    story_text = str(slide.get("story_text", "")).strip()
    text_color = str(slide.get("text_color", "")).strip()
    text_weight = str(slide.get("text_weight", "")).strip() or "Bold"

    text_directive_lines: list[str] = []
    if story_text:
        text_directive_lines.append(
            f"RENDER THIS EXACT TEXT INSIDE THE IMAGE, spelled letter-for-letter: "
            f"\"{story_text}\""
        )
        text_directive_lines.append(
            f"Typeface: Montserrat {text_weight}, geometric sans-serif, "
            "tall x-height, circular bowls, even stroke weight, crisp letterforms, "
            "perfect kerning, no spelling mistakes, no garbled glyphs, no extra letters."
        )
        if text_color:
            text_directive_lines.append(
                f"Text color: {text_color} (hex), high contrast against the scene, "
                "WCAG-AA legibility."
            )
        text_directive_lines.append(
            "Reserve clear negative space (top band, bottom band, or soft "
            "semi-transparent overlay) so the text is fully legible."
        )

    text_directive = "\n".join(text_directive_lines)

    parts = [
        text_directive,
        base_prompt,
        f"Art direction: {visual_style_prompt_hint(style)}. "
        "Instagram portrait composition, premium carousel cover quality.",
        _TYPOGRAPHY_DIRECTIVE,
    ]
    return "\n\n".join(part for part in parts if part)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
async def generate_one(prompt: str, style: str, flow_id: str, slide_index: int) -> str:
    """Generate a single image via fal.ai FLUX Pro Ultra.

    ``prompt`` should already be the full FLUX-ready string (built via
    :func:`build_flux_prompt` when the caller has the slide dict).
    ``style`` is reserved for future style-specific tuning; the v1.1-ultra schema
    does not expose guidance / step controls like older FLUX endpoints.

    Returns the CDN URL of the generated image.
    """
    _ensure_fal_credentials()

    start = time.monotonic()
    # If the caller already built the prompt via build_flux_prompt, it contains
    # the typography directive. If not (legacy call site), append it for safety.
    if "Montserrat" in prompt:
        styled_prompt = prompt.strip()
    else:
        styled_prompt = (
            f"{prompt.strip()}\n\n"
            f"Art direction: {visual_style_prompt_hint(style)}. "
            "Instagram portrait composition, premium carousel cover quality.\n\n"
            f"{_TYPOGRAPHY_DIRECTIVE}"
        )
    # Only arguments supported by fal-ai/flux-pro/v1.1-ultra (see fal.ai model API).
    arguments: dict[str, Any] = {
        "prompt": styled_prompt,
        "aspect_ratio": _DEFAULT_ASPECT_RATIO,
        "num_images": 1,
        "output_format": "jpeg",
        "safety_tolerance": "3",
    }

    result = await fal_client.subscribe_async(
        FAL_MODEL,
        arguments,
        client_timeout=600.0,
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    payload = _fal_output_dict(result)
    url = _first_image_url(payload)
    logger.info(
        "image_generated",
        flow_id=flow_id,
        slide_index=slide_index,
        style=style,
        latency_ms=latency_ms,
    )
    return url


async def generate_carousel(
    prompts: list[dict[str, Any]],
    style: str,
    flow_id: str,
) -> list[str]:
    """Generate all carousel images in parallel using asyncio.gather.

    Args:
        prompts: List of slide dicts with a ``prompt`` (or ``image_prompt``) field.
        style: Visual style key (passed through for logging / future use).
        flow_id: Used for cost tracking and logging.

    Returns:
        Ordered list of CDN image URLs.
    """
    if not prompts:
        raise ValueError("Cannot generate images: empty prompts list")

    # Surface a clean error if any slide is missing its prompt text.
    for i, slide in enumerate(prompts):
        _slide_prompt_text(slide, i)

    flux_prompts = [build_flux_prompt(p, style) for p in prompts]

    start = time.monotonic()
    tasks = [
        generate_one(flux_prompts[i], style, flow_id, i) for i in range(len(flux_prompts))
    ]
    urls: list[str] = await asyncio.gather(*tasks)
    total_ms = int((time.monotonic() - start) * 1000)

    cost = 0.05 * len(urls)
    await record_cost(
        flow_id=flow_id,
        service="fal_ai",
        model=FAL_MODEL,
        images_generated=len(urls),
        cost_usd=cost,
        latency_ms=total_ms,
    )

    logger.info(
        "carousel_generated",
        flow_id=flow_id,
        image_count=len(urls),
        total_ms=total_ms,
    )
    return list(urls)
