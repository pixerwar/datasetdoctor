"""Semantic (model2vec) embedding provider test.

Skipped if model2vec is not installed. On the first run the model is downloaded from
HuggingFace and cached on disk; subsequent runs are fast.
"""
from __future__ import annotations

import pytest

pytest.importorskip("model2vec")

from dataset_insight.embedding.semantic_provider import SemanticProvider
from sklearn.metrics.pairwise import cosine_similarity


def test_semantic_captures_meaning():
    provider = SemanticProvider()
    texts = [
        "Python is a programming language.",
        "Python is used to write code.",  # semantically close
        "The Ottoman Empire was founded in 1299.",  # unrelated
    ]
    emb = provider.embed(texts)
    assert emb.shape[0] == 3
    sim = cosine_similarity(emb)
    # The semantically close pair should be clearly more similar than the unrelated one
    assert sim[0, 1] > sim[0, 2] + 0.2


def test_semantic_stable_dimensions():
    # Unlike TF-IDF, the dimension must be corpus-independent and fixed (key for cache)
    provider = SemanticProvider()
    a = provider.embed(["one sentence"])
    b = provider.embed(["another", "two sentences"])
    assert a.shape[1] == b.shape[1]
