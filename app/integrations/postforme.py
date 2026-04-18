"""postforme.dev (Post for Me) integration — Instagram publishing.

Official API: https://api.postforme.dev/docs (OpenAPI).

Create post: ``POST /v1/social-posts`` with JSON body
``{ caption, social_accounts: [<PostForMe account id>], media: [{url}, ...] }``.

``social_accounts`` must be Post for Me **social account IDs** (e.g. ``spc_…``, ``sa_…``)
from the dashboard — **not** the Meta / Instagram Graph numeric user id.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx
from tenacity import retry, retry_if_exception, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

POSTFORME_CREATE_POST_URL = "https://api.postforme.dev/v1/social-posts"


def resolve_postforme_social_account_ids(brand_preset: dict[str, Any]) -> list[str]:
    """Resolve Post for Me ``social_accounts`` ids from DB preset and optional env default.

    Prefer ``postforme_social_account_ids`` (list or comma-separated string), then
    ``instagram_account_id`` (historical column name — store the Post For Me id there),
    then ``POSTFORME_DEFAULT_SOCIAL_ACCOUNT_ID``.
    """

    def split_csv(s: str) -> list[str]:
        return [p.strip() for p in s.split(",") if p.strip()]

    raw = brand_preset.get("postforme_social_account_ids")
    if isinstance(raw, list):
        out = [str(x).strip() for x in raw if str(x).strip()]
        if out:
            return out
    if isinstance(raw, str) and raw.strip():
        return split_csv(raw)

    single = brand_preset.get("postforme_social_account_id")
    if single is not None and str(single).strip():
        return split_csv(str(single))

    ig_col = brand_preset.get("instagram_account_id")
    if ig_col is not None and str(ig_col).strip():
        return split_csv(str(ig_col))

    default = (settings.postforme_default_social_account_id or "").strip()
    if default:
        return split_csv(default)

    return []


_TIMEOUT = httpx.Timeout(120.0, connect=15.0)

_INSTAGRAM_CAPTION_MAX = 2200


def _retryable_http_error(exc: BaseException) -> bool:
    """Retry only on transport failures or 5xx (not on 4xx validation errors)."""
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, httpx.WriteTimeout)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


def _truncate_caption(text: str, max_len: int = _INSTAGRAM_CAPTION_MAX) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 1] + "…"


def _extract_permalink(data: dict[str, Any]) -> str | None:
    """Best-effort URL to the live post from various response shapes."""
    direct = data.get("permalink") or data.get("url") or data.get("platform_url")
    if isinstance(direct, str) and direct.startswith("http"):
        return direct

    for key in ("platform_posts", "results", "social_post_results"):
        items = data.get(key)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            url = item.get("platform_url") or item.get("url")
            if isinstance(url, str) and url.startswith("http"):
                return url
            pdata = item.get("platform_data")
            if isinstance(pdata, dict):
                u = pdata.get("url")
                if isinstance(u, str) and u.startswith("http"):
                    return u
    return None


def format_error_response(response: httpx.Response) -> str:
    """Turn error HTTP body into a short log/user-safe string."""
    try:
        body = response.json()
    except Exception:
        return (response.text or "")[:500]
    if isinstance(body, dict):
        if "error" in body:
            err = body["error"]
            if isinstance(err, list):
                return "; ".join(str(x) for x in err)[:500]
            return str(err)[:500]
        if "message" in body:
            return str(body["message"])[:500]
    return str(body)[:500]


@dataclass
class PostResult:
    """Result returned after Post for Me accepts a social post."""

    post_id: str
    permalink: str | None = None
    status: str = "submitted"


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=3, max=45),
    retry=retry_if_exception(_retryable_http_error),
    reraise=True,
)
async def publish(
    social_account_ids: list[str],
    media_urls: list[str],
    caption: str,
    flow_id: str,
) -> PostResult:
    """Publish a carousel to Instagram via Post for Me.

    Args:
        social_account_ids: Post for Me social account IDs (from their dashboard).
        media_urls: Public HTTPS URLs of images (e.g. fal.ai CDN), in carousel order.
        caption: Instagram caption (truncated to platform max if needed).
        flow_id: Correlation id for logs.

    Raises:
        ValueError: Missing API key, accounts, or media.
        httpx.HTTPStatusError: API returned an error response.
    """
    if not settings.postforme_api_key:
        raise ValueError("POSTFORME_API_KEY is not configured")

    ids = [s.strip() for s in social_account_ids if s and str(s).strip()]
    if not ids:
        raise ValueError(
            "No Post for Me social account IDs. Set instagram_account_id in "
            "brand_presets to your Post for Me id (e.g. spc_…), or "
            "POSTFORME_DEFAULT_SOCIAL_ACCOUNT_ID in .env."
        )

    urls = [u.strip() for u in media_urls if u and str(u).strip()]
    if not urls:
        raise ValueError("No image URLs to publish")

    caption_clean = _truncate_caption(caption.strip() or " ")

    payload: dict[str, Any] = {
        "caption": caption_clean,
        "social_accounts": ids,
        "media": [{"url": u} for u in urls],
    }

    headers = {
        "Authorization": f"Bearer {settings.postforme_api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(
            POSTFORME_CREATE_POST_URL,
            json=payload,
            headers=headers,
        )

    latency_ms = int((time.monotonic() - start) * 1000)

    if response.is_error:
        detail = format_error_response(response)
        logger.error(
            "postforme_http_error",
            flow_id=flow_id,
            status=response.status_code,
            detail=detail,
            latency_ms=latency_ms,
        )
        response.raise_for_status()

    data: dict[str, Any] = response.json()
    if not isinstance(data, dict):
        raise TypeError("postforme response JSON must be an object")

    post_id = str(data.get("id") or "")
    if not post_id:
        logger.warning("postforme_missing_post_id", flow_id=flow_id, keys=list(data.keys()))

    permalink = _extract_permalink(data)
    status = str(data.get("status") or "submitted")

    logger.info(
        "carousel_submitted_to_postforme",
        flow_id=flow_id,
        post_id=post_id or "unknown",
        status=status,
        permalink=permalink,
        latency_ms=latency_ms,
        slide_count=len(urls),
    )
    return PostResult(post_id=post_id or "unknown", permalink=permalink, status=status)
