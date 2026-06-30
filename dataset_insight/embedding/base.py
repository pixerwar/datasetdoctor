"""Embedding provider interface — the key abstraction point.

Phase 1: TfidfProvider. Later OllamaEmbeddingProvider, FaissIndexProvider can be
added; the consuming code (metrics module) must not change — only the provider is
swapped via config/DI.
"""
from __future__ import annotations

from abc import ABC, abstractmethod

import numpy as np


class EmbeddingProvider(ABC):
    #: Provider identifier used in cache keys.
    name: str

    @abstractmethod
    def embed(self, texts: list[str]) -> np.ndarray:
        """texts -> returns an (N, D) dense float matrix."""
        raise NotImplementedError
