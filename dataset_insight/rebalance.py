"""Local class-imbalance fix — no API, no data leaves the machine.

When a dataset has explicit categories and one category dominates, this proposes
a *downsampling* plan: drop enough of the dominant category so no single class is
the majority. It only produces pair indices to remove — the existing /clean flow
applies it — so nothing is fabricated (unlike LLM augmentation, which would also
manufacture the near-duplicates the Clean step warns about).

For under-represented categories it adds non-destructive guidance ("collect N
more"), since the honest fix there is more real data, not synthetic copies.

Only explicit categories are handled: implicit clusters are fuzzy, and silently
deleting rows from a guessed cluster would be surprising.
"""
from __future__ import annotations

from collections import Counter

# Bring the dominant category to at most this share of the *resulting* dataset.
TARGET_SHARE = 0.50
# Categories below this many samples get "collect more" guidance.
MIN_HEALTHY_CATEGORY = 30


def _explicit_categories(pairs: list[dict]) -> list[str] | None:
    """Return per-pair categories iff every pair has an explicit one, else None."""
    if not pairs:
        return None
    cats = [p.get("category") for p in pairs]
    if any(not c for c in cats):
        return None
    return [str(c) for c in cats]


def plan_rebalance(pairs: list[dict], target_share: float = TARGET_SHARE) -> dict:
    """Propose a local downsample of the dominant category + minority guidance.

    Returns:
        {
          "applicable": bool,          # a dominant category can be trimmed
          "method": "explicit" | "none",
          "dominant": {"category", "count", "share"} | None,
          "target_share": float,
          "target_count": int,         # dominant kept after downsample
          "n_removable": int,
          "remove_indices": [int],     # dominant pairs to drop (keeps the first N)
          "result_counts": {cat: int}, # counts after applying the plan
          "suggestions": [str],        # non-destructive minority guidance
        }
    """
    none = {
        "applicable": False,
        "method": "none",
        "dominant": None,
        "target_share": target_share,
        "target_count": 0,
        "n_removable": 0,
        "remove_indices": [],
        "result_counts": {},
        "suggestions": [],
    }

    cats = _explicit_categories(pairs)
    if cats is None:
        return none

    counts = Counter(cats)
    total = len(cats)
    result: dict = {**none, "method": "explicit", "result_counts": dict(counts)}

    # Minority guidance is useful regardless of dominance.
    result["suggestions"] = [
        f"Add at least {MIN_HEALTHY_CATEGORY - cnt} more '{cat}' samples "
        f"(has {cnt})."
        for cat, cnt in counts.most_common()
        if cnt < MIN_HEALTHY_CATEGORY
    ]

    if len(counts) < 2:
        return result  # a single category can't be rebalanced by downsampling

    dom_cat, dom_count = counts.most_common(1)[0]
    others = total - dom_count
    dom_share = dom_count / total
    result["dominant"] = {
        "category": dom_cat,
        "count": dom_count,
        "share": round(dom_share, 4),
    }

    # Keep k dominant samples so k / (others + k) <= target_share.
    #   k <= target_share * others / (1 - target_share)
    if others == 0 or target_share <= 0 or target_share >= 1:
        return result
    target_count = int((target_share * others) / (1 - target_share))
    target_count = min(target_count, dom_count)
    n_remove = dom_count - target_count

    if dom_share <= target_share or n_remove <= 0:
        return result  # already balanced enough

    # Deterministic: keep the first `target_count` of the dominant category.
    remove_indices: list[int] = []
    kept = 0
    for i, c in enumerate(cats):
        if c == dom_cat:
            if kept < target_count:
                kept += 1
            else:
                remove_indices.append(i)

    result_counts = dict(counts)
    result_counts[dom_cat] = target_count

    result.update(
        applicable=True,
        target_count=target_count,
        n_removable=n_remove,
        remove_indices=remove_indices,
        result_counts=result_counts,
    )
    return result
