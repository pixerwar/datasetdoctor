"""SQLite-based embedding cache.

Schema: embeddings(hash TEXT PRIMARY KEY, provider_name TEXT, dim INTEGER, vector BLOB)

Note: for corpus-dependent providers like TF-IDF, the same text's vector changes when
the corpus changes and the dimension may not be stable. On a non-full cache hit or a
dimension mismatch, get_or_compute recomputes the whole batch and refreshes the cache
— so the result is always correct, and the cache only speeds up text-independent,
stable providers such as Ollama/API (e.g. model2vec).
"""
from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

import numpy as np

from ..embedding.base import EmbeddingProvider

_VECTOR_DTYPE = np.float64


def _hash_text(text: str, provider_name: str) -> str:
    h = hashlib.sha256()
    h.update(provider_name.encode("utf-8"))
    h.update(b"\x00")
    h.update(text.encode("utf-8"))
    return h.hexdigest()


class EmbeddingCache:
    def __init__(self, db_path: str = "embedding_cache.sqlite"):
        self.db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS embeddings (
                hash TEXT PRIMARY KEY,
                provider_name TEXT NOT NULL,
                dim INTEGER NOT NULL,
                vector BLOB NOT NULL
            )
            """
        )
        self._conn.commit()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> "EmbeddingCache":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _get(self, key: str) -> np.ndarray | None:
        row = self._conn.execute(
            "SELECT vector FROM embeddings WHERE hash = ?", (key,)
        ).fetchone()
        if row is None:
            return None
        return np.frombuffer(row[0], dtype=_VECTOR_DTYPE)

    def _put(self, key: str, provider_name: str, vector: np.ndarray) -> None:
        blob = np.ascontiguousarray(vector, dtype=_VECTOR_DTYPE).tobytes()
        self._conn.execute(
            "INSERT OR REPLACE INTO embeddings (hash, provider_name, dim, vector) "
            "VALUES (?, ?, ?, ?)",
            (key, provider_name, int(vector.shape[0]), blob),
        )

    def get_or_compute(
        self, texts: list[str], provider: EmbeddingProvider
    ) -> np.ndarray:
        if not texts:
            return np.empty((0, 0), dtype=_VECTOR_DTYPE)

        keys = [_hash_text(t, provider.name) for t in texts]
        cached = [self._get(k) for k in keys]

        # Full hit and consistent dimension: return directly.
        if all(v is not None for v in cached):
            dims = {v.shape[0] for v in cached}
            if len(dims) == 1:
                return np.vstack(cached)

        # Otherwise recompute the whole batch (corpus-dependent provider safety).
        embeddings = provider.embed(texts)
        for key, vec in zip(keys, embeddings):
            self._put(key, provider.name, vec)
        self._conn.commit()
        return embeddings


def get_or_compute(
    texts: list[str], provider: EmbeddingProvider, db_path: str = "embedding_cache.sqlite"
) -> np.ndarray:
    """Module-level convenience function — opens and closes its own connection."""
    with EmbeddingCache(db_path) as cache:
        return cache.get_or_compute(texts, provider)
