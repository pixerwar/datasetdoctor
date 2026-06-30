"""Embedding provider selection (the DI/config point).

The consuming code (pipeline/metrics) asks for a provider by name; the concrete
class is resolved here. Adding a new provider = one line here.
"""
from __future__ import annotations

from .base import EmbeddingProvider
from .tfidf_provider import TfidfProvider

# Valid provider names.
TFIDF = "tfidf"
SEMANTIC = "semantic"  # model2vec

VALID_PROVIDERS = (TFIDF, SEMANTIC)


def get_provider(name: str = TFIDF) -> EmbeddingProvider:
    if name == TFIDF:
        return TfidfProvider()
    if name == SEMANTIC:
        # Import the heavy module only when needed (model2vec is optional).
        from .semantic_provider import SemanticProvider

        return SemanticProvider()
    raise ValueError(
        f"Unknown embedding provider: {name!r}. Valid: {VALID_PROVIDERS}"
    )
