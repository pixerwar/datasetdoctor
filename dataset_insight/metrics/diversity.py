"""Diversity score.

Highly similar samples are connected in a graph; the ratio of connected components
to the number of samples gives the diversity ratio (1.0 = all distinct, ~0 = all
similar).
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.metrics.pairwise import cosine_similarity


def compute_diversity(embeddings: np.ndarray, threshold: float = 0.90) -> dict:
    n = len(embeddings)
    if n == 0:
        return {"score": 0.0, "n_clusters": 0, "total_samples": 0}
    if n == 1:
        return {"score": 1.0, "n_clusters": 1, "total_samples": 1}

    similarity_matrix = cosine_similarity(embeddings)  # NxN
    adjacency = (similarity_matrix >= threshold).astype(np.int8)
    np.fill_diagonal(adjacency, 0)
    n_components, _labels = connected_components(
        csgraph=csr_matrix(adjacency), directed=False
    )
    diversity_ratio = n_components / n
    return {
        "score": float(diversity_ratio),
        "n_clusters": int(n_components),
        "total_samples": int(n),
    }


def diversity_level(score: float) -> str:
    """Threshold labels for the report: good | medium | high_risk."""
    if score > 0.85:
        return "good"
    if score >= 0.6:
        return "medium"
    return "high_risk"
