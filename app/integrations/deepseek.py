"""DeepSeek V3 integration for prompt generation (SDD §4.3)."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.costs import record_cost
from app.utils.logging import get_logger
from app.visual_styles import visual_style_label, visual_style_prompt_hint

logger = get_logger(__name__)

DEEPSEEK_API_URL = "https://api.deepseek.com/chat/completions"
_TIMEOUT = httpx.Timeout(120.0, connect=10.0)

_SYSTEM_PROMPT_TEMPLATE = """\
You are a prompt engineer specialising in viral Instagram carousels with
storytelling typography rendered INSIDE each image.

INPUT: theme seed, selected topic, number of slides (N), visual style, brand,
caption_language, brand_palette.

OUTPUT: valid JSON with:
- story_arc (1 sentence describing the narrative across all N slides)
- slides: array with EXACTLY N objects

Each slide object MUST have these fields:
- slide (int, 1..N)
- role (hook | dev1 | dev2 | ... | cta)
- story_text (string, IN {caption_language}, 3-12 words, ALL CAPS or Title Case;
  this is the headline/storytelling line that will be RENDERED INSIDE the image)
- text_color (hex string like "#FFFFFF"; MUST come from brand_palette OR be a
  neutral chosen for maximum legibility against the scene described in `prompt`)
- text_weight ("Bold" | "SemiBold" | "Regular"; default "Bold" for hooks/CTA)
- prompt (string in ENGLISH, 90-170 words, fed directly to FLUX Pro Ultra)
- caption ({caption_language}, 40-80 words; this is the Instagram caption,
  NOT the in-image text)

STORYTELLING ARC (mandatory):
- Slide 1 = impactful visual HOOK + provocative one-line story_text
- Middle slides = progressive narrative beats (problem → insight → twist →
  evidence) — each story_text must advance the story
- Slide N = CTA or conclusion that closes the arc

IN-IMAGE TYPOGRAPHY RULES (mandatory inside every `prompt`):
- Explicitly instruct FLUX to render the EXACT text:
  rendered_text: "<story_text>"
- Force the typeface "Montserrat" (Bold/SemiBold/Regular per text_weight),
  high-quality kerning, crisp letterforms, no spelling mistakes
- Specify the text color using BOTH the hex value (e.g. "#0A0A0A") and a
  short descriptive name (e.g. "deep charcoal")
- Describe a clear contrast strategy with the underlying scene (e.g. "dark
  text on a soft cream backdrop", "white text over a dimmed bottom gradient")
- Reserve clear negative space for the text (top third, bottom third, or a
  semi-transparent band) so the typography is fully legible
- The text color MUST harmonize with the brand_palette and contrast against
  the dominant area of the image (WCAG AA-like legibility)

HARD RULES:
- Recurring visual elements in >= 60% of slides
- Never identical or near-identical prompts
- Always include aspect ratio 4:5 in the prompt
- Incorporate the brand palette (provided in context)
- The selected topic and theme seed define the subject matter of every image
- The visual style only controls aesthetics, composition, textures, lighting,
  and art direction
- Never create generic prompts that mention only style; describe scenes,
  objects, people, context, and actions that clearly belong to the selected
  topic
- Keep all slides semantically aligned with the theme seed, the selected topic
  title, and the selected topic summary
- Write ALL captions and story_text strictly in {caption_language}; never mix
  languages
- The English `prompt` field may quote the {caption_language} story_text
  verbatim inside quotes — that quoted text is what FLUX must render

RESPOND ONLY WITH JSON. NO MARKDOWN. NO EXPLANATIONS."""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
async def generate_prompts(
    theme_seed: str,
    topic: dict[str, str],
    slide_count: int,
    visual_style: str,
    brand_name: str,
    brand_preset: dict[str, Any],
    flow_id: str,
    caption_language: str = "pt-br",
) -> dict[str, Any]:
    """Generate a set of image prompts for an Instagram carousel via DeepSeek V3.

    Returns a dict with keys: story_arc (str), slides (list[dict]).
    """
    palette = brand_preset.get("palette", {})
    voice = brand_preset.get("voice", {})

    # Build system message: brand-specific prompt (from .md file) as context prefix,
    # then the engineering rules with the chosen caption language.
    brand_system = str(brand_preset.get("system_prompt", "")).strip()
    base_prompt = _SYSTEM_PROMPT_TEMPLATE.format(caption_language=caption_language)
    system_content = f"{brand_system}\n\n---\n\n{base_prompt}" if brand_system else base_prompt

    user_content = json.dumps(
        {
            "brand": brand_name,
            "theme_seed": theme_seed,
            "selected_topic": topic,
            "slide_count": slide_count,
            "visual_style": {
                "key": visual_style,
                "label": visual_style_label(visual_style),
                "prompt_hint": visual_style_prompt_hint(visual_style),
            },
            "caption_language": caption_language,
            "brand_palette": palette,
            "brand_voice": voice,
            "generation_focus": {
                "subject_priority": [
                    "theme_seed",
                    "selected_topic.title",
                    "selected_topic.summary",
                ],
                "style_priority": [
                    "visual_style",
                    "brand_palette",
                ],
                "instruction": (
                    "Build image prompts around the selected subject first, then express it "
                    "through the requested visual style."
                ),
            },
        },
        ensure_ascii=False,
    )

    payload: dict[str, Any] = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_content},
            {"role": "user", "content": user_content},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.7,
        "max_tokens": 3000,
    }

    headers = {
        "Authorization": f"Bearer {settings.deepseek_api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(DEEPSEEK_API_URL, json=payload, headers=headers)
        response.raise_for_status()

    latency_ms = int((time.monotonic() - start) * 1000)
    data = response.json()

    usage = data.get("usage", {})
    await record_cost(
        flow_id=flow_id,
        service="deepseek",
        model="deepseek-chat",
        tokens_input=usage.get("prompt_tokens"),
        tokens_output=usage.get("completion_tokens"),
        latency_ms=latency_ms,
    )

    content = data["choices"][0]["message"]["content"]
    result: dict[str, Any] = json.loads(content)
    logger.info(
        "prompts_generated",
        flow_id=flow_id,
        brand=brand_name,
        slide_count=slide_count,
        caption_language=caption_language,
    )
    return result
