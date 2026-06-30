"""TF-IDF based embedding provider (Phase 1)."""
from __future__ import annotations

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer


class TfidfProvider:
    name = "tfidf"

    def __init__(self, max_features: int = 4096):
        self.max_features = max_features

    def embed(self, texts: list[str]) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=np.float64)
        # Each embed call fits on an independent corpus; correct for Phase 1 since
        # the metrics process a single dataset all at once.
        vectorizer = TfidfVectorizer(max_features=self.max_features)
        matrix = vectorizer.fit_transform(texts)
        return matrix.toarray().astype(np.float64)
