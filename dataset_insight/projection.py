"""2D semantic map of the embeddings (Phase 2 visualization).

Used two ways:
- With enough samples (frontend threshold): PCA scatter + cluster blobs.
- With few samples: falls back to cluster cards / a note.

Labeling rule: explicit categories are used as cluster labels only if they are
*reasonably few and not unique per sample*; otherwise (each row a distinct category,
e.g. the answer text was chosen as the category) the embeddings are grouped with
KMeans into short "Cluster N" labels — so no point gets its own color.
"""
from __future__ import annotations

from collections import OrderedDict

import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics.pairwise import cosine_similarity

MAX_POINTS = 400
# If the number of explicit categories exceeds this (or ~unique per sample), cluster.
MAX_EXPLICIT_LABELS = 12
# Below this sample count no meaningful clusters are produced (single group).
MIN_FOR_CLUSTERING = 8
_TEXT_PREVIEW = 70


def _short(text: str) -> str:
    text = (text or "").strip()
    return text[:_TEXT_PREVIEW] + "…" if len(text) > _TEXT_PREVIEW else text


def _cluster_labels(pairs: list[dict], embeddings: np.ndarray) -> list[str]:
    """Produce a short coloring label for each sample."""
    n = len(pairs)
    explicit = [(p.get("category") or "").strip() for p in pairs]
    distinct = {c for c in explicit if c}

    # Use explicit categories if they are a reasonable count.
    if (
        all(explicit)
        and 2 <= len(distinct) <= MAX_EXPLICIT_LABELS
        and len(distinct) < n
    ):
        return explicit

    # Too few samples: clustering is meaningless, single group.
    if n < MIN_FOR_CLUSTERING:
        return ["All samples"] * n

    # Group the embeddings with KMeans and assign short "Cluster N" labels.
    k = min(8, max(2, round((n / 2) ** 0.5)))
    k = min(k, n - 1)
    labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(embeddings)
    return [f"Cluster {int(lbl) + 1}" for lbl in labels]


def _representative(idxs: list[int], embeddings: np.ndarray, pairs: list[dict]) -> str:
    """Return the instruction of the sample closest to the cluster centroid (medoid)."""
    sub = embeddings[idxs]
    centroid = sub.mean(axis=0, keepdims=True)
    sims = cosine_similarity(sub, centroid).ravel()
    best = idxs[int(np.argmax(sims))]
    return _short(pairs[best].get("instruction", ""))


def _cluster_summary(
    labels: list[str], embeddings: np.ndarray, pairs: list[dict]
) -> list[dict]:
    """Summary for cluster cards: label, count, share, representative example."""
    n = len(labels)
    groups: "OrderedDict[str, list[int]]" = OrderedDict()
    for i, lbl in enumerate(labels):
        groups.setdefault(lbl, []).append(i)

    summary = [
        {
            "label": lbl,
            "count": len(idxs),
            "share": round(len(idxs) / n, 4),
            "example": _representative(idxs, embeddings, pairs),
        }
        for lbl, idxs in groups.items()
    ]
    summary.sort(key=lambda c: c["count"], reverse=True)
    return summary


def compute_projection(
    pairs: list[dict], embeddings: np.ndarray, max_points: int = MAX_POINTS
) -> dict:
    n = len(pairs)
    if n == 0 or embeddings.size == 0:
        return {"method": "pca", "points": [], "clusters": [], "truncated": 0}

    labels = _cluster_labels(pairs, embeddings)
    clusters = _cluster_summary(labels, embeddings, pairs)

    # 2D PCA (safe fallback if n or dimension < 2).
    if n >= 2 and embeddings.shape[1] >= 2:
        coords = PCA(n_components=2, random_state=42).fit_transform(embeddings)
    else:
        coords = np.zeros((n, 2), dtype=np.float64)

    # If too large, sample evenly (cluster summary counts stay exact).
    truncated = 0
    indices = list(range(n))
    if n > max_points:
        step = n / max_points
        indices = [int(i * step) for i in range(max_points)]
        truncated = n - max_points

    points = [
        {
            "x": round(float(coords[i, 0]), 4),
            "y": round(float(coords[i, 1]), 4),
            "label": labels[i],
            "text": _short(pairs[i].get("instruction", "")),
        }
        for i in indices
    ]

    return {
        "method": "pca",
        "points": points,
        "clusters": clusters,
        "truncated": truncated,
    }
