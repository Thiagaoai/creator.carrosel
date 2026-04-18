"""Claude vision audit — verify the typography rendered inside each image.

After FLUX generates the carousel, this module asks Claude Sonnet to look at
every image and judge whether the in-image text matches the expected
``story_text``, whether the typeface reads as Montserrat, whether contrast
and legibility are acceptable, and whether the color is close to the chosen
``text_color``. The result is attached to the flow and surfaced to the user
in the approval message so they can regenerate failing slides instead of
shipping a broken carousel.
"""

from __future__ import annotations

import asyncio
import base64
import json
import time
from typing import Any

import anthropic
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.costs import record_cost
from app.utils.logging import get_logger

logger = get_logger(__name__)

_MODEL = "claude-sonnet-4-5"
_MAX_TOKENS = 1500
_HTTP_TIMEOUT = httpx.Timeout(30.0, connect=10.0)

_AUDIT_SYSTEM = """\
You are a senior typography QA judge for an Instagram carousel rendered by
FLUX Pro Ultra. You will receive N slides; for each slide you get one image
and a metadata line describing what FLUX was supposed to render inside it:
the EXACT text, the desired text color (hex), the desired weight, and the
typeface (always Montserrat).

For each image, audit on these dimensions:

1. text_match (boolean): does the image render the EXACT expected text,
   spelled letter-for-letter (case and punctuation may be normalized but
   the words and their order must match)? Missing letters, extra letters,
   wrong words, or duplicated glyphs all count as a mismatch.
2. rendered_text_seen (string): copy out, as faithfully as you can read it,
   the actual text rendered in the image. Use "" if illegible.
3. montserrat_match (0-10): does the rendered typography read as
   Montserrat — geometric sans-serif, tall x-height, perfectly circular
   bowls (O, C), double-story 'a', single-story 'g', uniform stroke
   weight, wide apertures, modern urban grotesque feel, no serifs, no
   italics? 10 = unmistakably Montserrat-like. 0 = clearly a different
   genre (serif, slab, script, handwritten, condensed display, etc.).
4. contrast (0-10): how strong is the contrast between the text and the
   area immediately behind it? 10 = WCAG-AAA, 7 = WCAG-AA, < 5 = fails.
5. color_match (0-10): how close is the actual rendered text color to
   the desired hex? 10 = visually identical, 5 = same family different
   tone, 0 = different color.
6. legibility (0-10): can a viewer read every word at a glance on a
   phone screen?
7. verdict ("pass" | "fail"): pass requires text_match == true AND
   montserrat_match >= 7 AND contrast >= 7 AND legibility >= 7.
8. notes: ONE short sentence describing the main issue, or "OK" when
   everything passes.

Be strict. If the text has any garbled glyph, missing letter, double
letter, or wrong word, text_match is false.

OUTPUT FORMAT — respond ONLY with a single valid JSON object, no
markdown, no commentary:

{
  "audits": [
    {
      "slide": 1,
      "text_match": true,
      "rendered_text_seen": "...",
      "montserrat_match": 0,
      "contrast": 0,
      "color_match": 0,
      "legibility": 0,
      "verdict": "pass",
      "notes": "..."
    }
  ]
}
"""


async def _fetch_image_b64(url: str) -> tuple[str, str]:
    """Download an image and return ``(media_type, base64_data)``."""
    async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT, follow_redirects=True) as client:
        response = await client.get(url)
        response.raise_for_status()
        media_type = response.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if media_type not in {"image/jpeg", "image/png", "image/webp", "image/gif"}:
            media_type = "image/jpeg"
        data = base64.standard_b64encode(response.content).decode("ascii")
    return media_type, data


def _empty_audit(slides: list[dict[str, Any]], reason: str) -> list[dict[str, Any]]:
    return [
        {
            "slide": int(slide.get("slide", i + 1)),
            "text_match": False,
            "rendered_text_seen": "",
            "montserrat_match": 0,
            "contrast": 0,
            "color_match": 0,
            "legibility": 0,
            "verdict": "fail",
            "notes": f"audit_unavailable: {reason}",
        }
        for i, slide in enumerate(slides)
    ]


@retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=3, max=20))
async def audit_typography(
    image_urls: list[str],
    slides: list[dict[str, Any]],
    flow_id: str,
) -> list[dict[str, Any]]:
    """Audit the typography of every generated slide via Claude vision.

    Args:
        image_urls: CDN URLs of the generated images, in slide order.
        slides: Slide dicts (need ``story_text``, ``text_color``, ``text_weight``).
        flow_id: For cost tracking and log correlation.

    Returns:
        List of audit dicts, one per slide, in the same order as ``image_urls``.
    """
    if not image_urls or not slides:
        return []

    pairs = list(zip(image_urls, slides[: len(image_urls)], strict=False))

    # Fetch and base64-encode every image in parallel for the Anthropic payload.
    try:
        encoded = await asyncio.gather(*(_fetch_image_b64(url) for url in image_urls))
    except Exception as exc:
        logger.warning("typography_audit_fetch_failed", flow_id=flow_id, error=str(exc))
        return _empty_audit(slides, f"fetch_failed:{type(exc).__name__}")

    content: list[dict[str, Any]] = []
    for i, ((media_type, b64), (_, slide)) in enumerate(zip(encoded, pairs, strict=True), start=1):
        story_text = str(slide.get("story_text", "")).strip()
        text_color = str(slide.get("text_color", "")).strip() or "(unspecified)"
        text_weight = str(slide.get("text_weight", "Bold")).strip() or "Bold"
        meta = (
            f"Slide {i} expected: text=\"{story_text}\", "
            f"color={text_color}, weight={text_weight}, typeface=Montserrat"
        )
        content.append({"type": "text", "text": meta})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": media_type,
                    "data": b64,
                },
            }
        )

    content.append(
        {
            "type": "text",
            "text": (
                "Audit every slide above. Respond with the JSON object specified in "
                "the system instructions, with one entry per slide in the same order."
            ),
        }
    )

    client = anthropic.AsyncAnthropic(api_key=settings.anthropic_api_key)

    start = time.monotonic()
    message = await client.messages.create(
        model=_MODEL,
        max_tokens=_MAX_TOKENS,
        system=_AUDIT_SYSTEM,
        messages=[{"role": "user", "content": content}],
    )
    latency_ms = int((time.monotonic() - start) * 1000)

    usage = message.usage
    # Vision input tokens are billed at the standard input rate for Sonnet.
    cost = (usage.input_tokens * 3 + usage.output_tokens * 15) / 1_000_000
    await record_cost(
        flow_id=flow_id,
        service="anthropic_vision",
        model=_MODEL,
        tokens_input=usage.input_tokens,
        tokens_output=usage.output_tokens,
        cost_usd=cost,
        latency_ms=latency_ms,
    )

    raw = message.content[0].text  # type: ignore[union-attr]
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "typography_audit_parse_failed",
            flow_id=flow_id,
            error=str(exc),
            raw_preview=raw[:200],
        )
        return _empty_audit(slides, "parse_failed")

    audits_raw = parsed.get("audits") if isinstance(parsed, dict) else None
    if not isinstance(audits_raw, list) or not audits_raw:
        return _empty_audit(slides, "empty_response")

    # Defensive normalization so downstream code can rely on the schema.
    audits: list[dict[str, Any]] = []
    for i, item in enumerate(audits_raw):
        if not isinstance(item, dict):
            continue
        audits.append(
            {
                "slide": int(item.get("slide", i + 1)),
                "text_match": bool(item.get("text_match", False)),
                "rendered_text_seen": str(item.get("rendered_text_seen", "")),
                "montserrat_match": int(item.get("montserrat_match", 0) or 0),
                "contrast": int(item.get("contrast", 0) or 0),
                "color_match": int(item.get("color_match", 0) or 0),
                "legibility": int(item.get("legibility", 0) or 0),
                "verdict": str(item.get("verdict", "fail")).lower(),
                "notes": str(item.get("notes", "")).strip(),
            }
        )

    logger.info(
        "typography_audit_done",
        flow_id=flow_id,
        slide_count=len(audits),
        failures=sum(1 for a in audits if a.get("verdict") == "fail"),
        tokens_in=usage.input_tokens,
        tokens_out=usage.output_tokens,
        latency_ms=latency_ms,
    )
    return audits
