"""Perplexity sonar-pro integration for topic research (SDD §4.2)."""

from __future__ import annotations

import time
from typing import Any

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.config import settings
from app.utils.costs import record_cost
from app.utils.logging import get_logger

logger = get_logger(__name__)

PERPLEXITY_API_URL = "https://api.perplexity.ai/chat/completions"
_TIMEOUT = httpx.Timeout(60.0, connect=10.0)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
async def search_topics(
    brand_name: str,
    brand_context: str,
    flow_id: str,
    user_topic: str | None = None,
) -> list[dict[str, str]]:
    """Search for 10 current sub-topic options inside ``user_topic`` using sonar-pro.

    Args:
        brand_name: Brand identifier (used only for logging).
        brand_context: Free-text brand voice context (e.g. "dockplus — professional").
        flow_id: Flow identifier for cost recording.
        user_topic: Topic provided by the user. Required — the model will be asked
            for 10 distinct angles/sub-topics inside this theme.

    Returns:
        A list of up to 10 dicts with keys: title, summary, source, date.
    """
    if not user_topic or not user_topic.strip():
        raise ValueError("search_topics requires a non-empty user_topic")

    topic = user_topic.strip()
    user_prompt = (
        f"The user's topic of interest is: \"{topic}\". "
        f"Brand context: {brand_context}. "
        "Find exactly 10 current Instagram-carousel-worthy angles, sub-topics, "
        "or concrete story ideas STRICTLY INSIDE that topic. "
        "Each option must be a different angle (do not repeat the same news). "
        "Focus on developments from the last 7 days when possible. "
        "Prefer concrete announcements, launches, research, funding rounds, "
        "trend shifts, or newsy explainers. "
        "Avoid duplicates, clickbait, and opinion-only angles. "
        "Respond ONLY with valid JSON in this exact format: "
        '{"topics": [{"title": "", "summary": "", "source": "", "date": ""}]}'
    )

    payload: dict[str, Any] = {
        "model": "sonar-pro",
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a brand-aware news curator for Instagram carousel teams. "
                    "Respond ONLY with valid JSON, no markdown, no explanations."
                ),
            },
            {"role": "user", "content": user_prompt},
        ],
        "max_tokens": 2500,
        "temperature": 0.2,
        "search_recency_filter": "week",
    }

    headers = {
        "Authorization": f"Bearer {settings.perplexity_api_key}",
        "Content-Type": "application/json",
    }

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        response = await client.post(PERPLEXITY_API_URL, json=payload, headers=headers)
        response.raise_for_status()

    latency_ms = int((time.monotonic() - start) * 1000)
    data = response.json()

    usage = data.get("usage", {})
    await record_cost(
        flow_id=flow_id,
        service="perplexity",
        model="sonar-pro",
        tokens_input=usage.get("prompt_tokens"),
        tokens_output=usage.get("completion_tokens"),
        latency_ms=latency_ms,
    )

    content = data["choices"][0]["message"]["content"]

    import json

    parsed: dict[str, Any] = json.loads(content)
    topics: list[dict[str, str]] = parsed.get("topics", [])
    topics = topics[:10]
    logger.info(
        "topics_fetched",
        flow_id=flow_id,
        count=len(topics),
        brand=brand_name,
        user_topic=user_topic,
    )
    return topics
