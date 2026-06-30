"""model2vec-based semantic embedding provider (Phase 2).

Static distilled embeddings: pure-numpy inference, no torch; on first use the model
is downloaded from HuggingFace and cached on disk. Unlike TF-IDF, it produces a
corpus-independent, fixed-size (stable) vector per text — so the SQLite embedding
cache provides a real speedup with this provider.
"""
from __future__ import annotations

import numpy as np

# Multilingual (including Turkish) static model.
DEFAULT_MODEL = "minishlab/potion-multilingual-128M"

# Share loaded models across the process (model id -> StaticModel).
_MODEL_CACHE: dict[str, object] = {}


def _load_model(model_id: str):
    model = _MODEL_CACHE.get(model_id)
    if model is None:
        from model2vec import StaticModel

        model = StaticModel.from_pretrained(model_id)
        _MODEL_CACHE[model_id] = model
    return model


class SemanticProvider:
    def __init__(self, model_id: str = DEFAULT_MODEL):
        self.model_id = model_id
        # Include the model id in cache keys (so different models don't collide).
        self.name = f"model2vec:{model_id}"

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float64)
        model = _load_model(self.model_id)
        vectors = model.encode(texts)
        return np.asarray(vectors, dtype=np.float64)
