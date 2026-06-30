"""Balance / category distribution.

- If the user provided category labels: direct count.
- No labels and N >= 50: implicit categories via DBSCAN (cosine); if noise is high,
  pick K with KMeans + silhouette (K = 2..floor(sqrt(N))).
- N < 50: balance analysis is skipped.
"""
from __future__ import annotations

from collections import Counter

import numpy as np
from sklearn.cluster import DBSCAN, KMeans
from sklearn.metrics import silhouette_score

MIN_SAMPLES_FOR_IMPLICIT = 50
DOMINANCE_THRESHOLD = 0.60  # a category > 60% -> dominance warning
MIN_CATEGORY_COUNT = 10  # a category < 10 samples -> under-representation warning
# If the DBSCAN noise ratio exceeds this, fall back to KMeans.
NOISE_FALLBACK_RATIO = 0.40


def _warnings_from_counts(counts: dict, total: int) -> list[str]:
    warnings: list[str] = []
    for cat, count in counts.items():
        if total and count / total > DOMINANCE_THRESHOLD:
            warnings.append(
                f"Category '{cat}' covers {count / total * 100:.0f}% of the samples "
                f"(dominant)."
            )
    for cat, count in counts.items():
        if count < MIN_CATEGORY_COUNT:
            warnings.append(
                f"Category '{cat}' has only {count} samples "
                f"(under-represented)."
            )
    return warnings


def _kmeans_labels(embeddings: np.ndarray) -> np.ndarray:
    """Pick the best K with KMeans + silhouette (K = 2..floor(sqrt(N)))."""
    n = len(embeddings)
    k_max = max(2, int(np.sqrt(n)))
    best_k, best_score, best_labels = 2, -1.0, None
    for k in range(2, k_max + 1):
        if k >= n:
            break
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(
            embeddings
        )
        if len(set(labels)) < 2:
            continue
        score = silhouette_score(embeddings, labels, metric="cosine")
        if score > best_score:
            best_k, best_score, best_labels = k, score, labels
    if best_labels is None:
        best_labels = np.zeros(n, dtype=int)
    return best_labels


def compute_balance(
    pairs: list[dict],
    embeddings: np.ndarray | None = None,
) -> dict:
    n = len(pairs)
    explicit = [p.get("category") for p in pairs if p.get("category")]

    # 1) Explicit labels available.
    if explicit and len(explicit) == n:
        counts = dict(Counter(explicit))
        return {
            "method": "explicit",
            "category_counts": counts,
            "warnings": _warnings_from_counts(counts, n),
        }

    # 2) Dataset too small -> skip.
    if n < MIN_SAMPLES_FOR_IMPLICIT:
        return {
            "method": "skipped",
            "category_counts": {},
            "warnings": [],
            "note": "dataset too small for category analysis at this size",
        }

    if embeddings is None or len(embeddings) != n:
        return {
            "method": "skipped",
            "category_counts": {},
            "warnings": [],
            "note": "embeddings required for implicit category analysis",
        }

    # 3) DBSCAN (cosine).
    db_labels = DBSCAN(metric="cosine", eps=0.3, min_samples=5).fit_predict(embeddings)
    noise_ratio = float(np.mean(db_labels == -1)) if n else 1.0

    if noise_ratio > NOISE_FALLBACK_RATIO:
        labels = _kmeans_labels(embeddings)
        method = "kmeans"
    else:
        labels = db_labels
        method = "dbscan"

    counts: dict[str, int] = {}
    for lbl in labels:
        key = "noise" if lbl == -1 else f"cluster_{int(lbl)}"
        counts[key] = counts.get(key, 0) + 1

    return {
        "method": method,
        "category_counts": counts,
        "warnings": _warnings_from_counts(counts, n),
        "noise_ratio": noise_ratio,
    }
