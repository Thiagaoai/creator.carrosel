"""Prompt quality validator using local sentence-transformers (SDD §4.4).

Runs entirely on the VPS CPU — zero API cost.
Model: all-MiniLM-L6-v2 (~80 MB, downloaded once to HF_HOME cache).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any

import numpy as np
from sentence_transformers import SentenceTransformer

from app.utils.logging import get_logger

logger = get_logger(__name__)

_MODEL_NAME = "all-MiniLM-L6-v2"


@lru_cache(maxsize=1)
def _get_model() -> SentenceTransformer:
    """Load and cache the sentence-transformers model (lazy init, thread-safe)."""
    logger.info("loading_embedding_model", model=_MODEL_NAME)
    return SentenceTransformer(_MODEL_NAME)


@dataclass
class ValidationResult:
    """Output of score_prompts()."""

    average: float
    needs_claude_fix: bool
    problematic_slides: list[int]
    scores: dict[str, float] = field(default_factory=dict)


def score_prompts(
    prompts: list[dict[str, Any]],
    brand_rules: dict[str, Any],
) -> ValidationResult:
    """Score a list of slide prompt dicts on four quality dimensions.

    Dimensions (each 1-10):
    1. Similarity — cosine similarity between all prompt pairs.
    2. Length — all prompts must be 80-200 words.
    3. Brand keywords — all prompts contain at least one required keyword.
    4. Role diversity — enough distinct roles (hook/dev/cta).

    Returns a ValidationResult with average score and which slides need fixing.
    The threshold for triggering Claude rewrite is average < 7.0.
    """
    texts = [p["prompt"] for p in prompts]
    model = _get_model()
    embeddings: np.ndarray = model.encode(texts, convert_to_numpy=True)

    # ── 1. Similarity ─────────────────────────────────────────────────────────
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms = np.where(norms == 0, 1e-9, norms)
    normalised = embeddings / norms
    sim_matrix: np.ndarray = normalised @ normalised.T
    np.fill_diagonal(sim_matrix, 0.0)
    max_sim: float = float(sim_matrix.max()) if sim_matrix.size > 1 else 0.0

    if max_sim < 0.70:
        similarity_score = 10.0
    elif max_sim < 0.85:
        similarity_score = 5.0
    else:
        similarity_score = 1.0

    # ── 2. Length ─────────────────────────────────────────────────────────────
    lengths = [len(t.split()) for t in texts]
    all_in_range = all(80 <= length <= 200 for length in lengths)
    length_score = 10.0 if all_in_range else 6.0

    # ── 3. Brand keywords ─────────────────────────────────────────────────────
    required_keywords: list[str] = brand_rules.get("required_keywords", [])
    if required_keywords:
        all_have_keyword = all(
            any(kw.lower() in t.lower() for kw in required_keywords) for t in texts
        )
        brand_score = 10.0 if all_have_keyword else 5.0
    else:
        brand_score = 10.0  # No requirement defined → full score

    # ── 4. Role diversity ─────────────────────────────────────────────────────
    roles = [p.get("role", "") for p in prompts]
    unique_roles = len(set(roles))
    required_unique = min(3, len(prompts))
    role_score = 10.0 if unique_roles >= required_unique else 5.0

    # ── Aggregate ─────────────────────────────────────────────────────────────
    avg = (similarity_score + length_score + brand_score + role_score) / 4.0

    # Identify problematic slides (bad length or involved in high-similarity pair)
    problematic: list[int] = []

    # Bad-length slides
    for i, length in enumerate(lengths):
        if not (80 <= length <= 200) and i not in problematic:
            problematic.append(i)

    # High-similarity pairs: flag the slide with highest avg similarity to others
    if max_sim >= 0.85 and sim_matrix.size > 1:
        avg_sim_per_slide = sim_matrix.mean(axis=1)
        worst_idx = int(avg_sim_per_slide.argmax())
        if worst_idx not in problematic:
            problematic.append(worst_idx)

    result = ValidationResult(
        average=round(avg, 2),
        needs_claude_fix=avg < 7.0,
        problematic_slides=sorted(problematic),
        scores={
            "similarity": similarity_score,
            "length": length_score,
            "brand": brand_score,
            "role_diversity": role_score,
        },
    )
    logger.info(
        "prompts_scored",
        average=result.average,
        needs_fix=result.needs_claude_fix,
        problematic_slides=result.problematic_slides,
    )
    return result
