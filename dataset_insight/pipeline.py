"""Analysis pipeline — builds the full report from instruction-output pairs.

The API layer calls this; it combines the metric/risk modules in one place.
"""
from __future__ import annotations

from .cache.embedding_cache import EmbeddingCache
from .embedding.base import EmbeddingProvider
from .embedding.registry import TFIDF, get_provider
from .metrics.balance import compute_balance
from .metrics.diversity import compute_diversity, diversity_level
from .metrics.size_adequacy import compute_size_adequacy
from .metrics.training_time import estimate_training_time
from .projection import compute_projection
from .risk.composite import compute_composite_risk


def _embedding_text(pair: dict) -> str:
    """Embeddings use the instruction + output combined."""
    return f"{pair['instruction']}\n{pair['output']}"


def build_report(
    pairs: list[dict],
    model_size: str = "3b",
    embedding_provider: str = TFIDF,
    provider: EmbeddingProvider | None = None,
    cache: EmbeddingCache | None = None,
    diversity_threshold: float = 0.90,
    include_projection: bool = True,
) -> dict:
    """Build a report (matching the API contract) from instruction-output pairs.

    embedding_provider: "tfidf" | "semantic" (model2vec). If `provider` is passed
    directly it is used (test/DI), otherwise it is resolved from the registry.
    """
    n = len(pairs)
    if n == 0:
        raise ValueError("At least one sample is required to build a report.")

    if provider is None:
        provider = get_provider(embedding_provider)
    texts = [_embedding_text(p) for p in pairs]
    if cache is not None:
        embeddings = cache.get_or_compute(texts, provider)
    else:
        embeddings = provider.embed(texts)

    # Diversity
    diversity = compute_diversity(embeddings, threshold=diversity_threshold)
    diversity_report = {
        "score": diversity["score"],
        "level": diversity_level(diversity["score"]),
        "n_clusters": diversity["n_clusters"],
    }

    # Balance
    balance = compute_balance(pairs, embeddings=embeddings)

    # Size adequacy
    n_categories = len(balance.get("category_counts") or {}) or None
    size = compute_size_adequacy(n, n_categories=n_categories)

    # Training time
    min_h, max_h = estimate_training_time(n, model_size)

    # Composite risk
    composite = compute_composite_risk(diversity, size["category"], balance)

    report = {
        "n_samples": n,
        "embedding_provider": embedding_provider,
        "diversity": diversity_report,
        "balance": {
            "category_counts": balance.get("category_counts", {}),
            "warnings": balance.get("warnings", []),
            "method": balance.get("method"),
        },
        "size_adequacy": {
            "category": size["category"],
            "message": size["message"],
            **(
                {"relative_note": size["relative_note"]}
                if "relative_note" in size
                else {}
            ),
        },
        "training_time_estimate": {
            "min_hours": round(min_h, 2),
            "max_hours": round(max_h, 2),
            "model_size": model_size,
        },
        "composite_risk": composite,
    }

    # Semantic map (2D projection) — for visualization
    if include_projection:
        report["projection"] = compute_projection(pairs, embeddings)

    return report
