"""Reciprocal Rank Fusion (RRF).

Combines multiple ranked lists into a single ranked list. RRF is simple,
parameter-light, and works well when the individual lists have different
score scales (which is exactly the case for vector similarity vs BM25).

Formula: RRF(d) = sum over rankers of 1 / (k + rank(d))

where k is a smoothing constant (typically 60).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeVar

T = TypeVar("T")


@dataclass(slots=True)
class FusedResult:
    """A result after RRF fusion."""

    item_id: str
    rrf_score: float
    ranks: dict[str, int]  # ranker_name → rank position (1-indexed)


def reciprocal_rank_fusion(
    ranked_lists: dict[str, list[str]],
    k: int = 60,
) -> list[FusedResult]:
    """Fuse multiple ranked lists using RRF.

    Args:
        ranked_lists: {ranker_name: [item_id, ...]} — each list is ordered
                      best-first.
        k: smoothing constant (default 60, standard value).

    Returns: list of FusedResult sorted by RRF score descending.
    """
    scores: dict[str, float] = {}
    ranks: dict[str, dict[str, int]] = {}

    for ranker_name, items in ranked_lists.items():
        ranks[ranker_name] = {}
        for rank, item_id in enumerate(items, 1):
            scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank)
            ranks[ranker_name][item_id] = rank

    # Sort by score descending
    sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    return [
        FusedResult(
            item_id=item_id,
            rrf_score=score,
            ranks={rn: r[item_id] for rn, r in ranks.items() if item_id in r},
        )
        for item_id, score in sorted_ids
    ]
