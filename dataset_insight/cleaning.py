"""Cleaning analysis — near-duplicate detection + per-sample quality lint.

Moves the tool from "diagnose" to "fix": surfaces concrete pairs to remove
(duplicates, empty/short/degenerate, over-long), so the user can clean the dataset
before export.
"""
from __future__ import annotations

from collections import defaultdict

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import connected_components
from sklearn.metrics.pairwise import cosine_similarity

DUP_THRESHOLD = 0.95  # cosine >= this -> near-duplicate
SHORT_OUTPUT_CHARS = 10
LONG_TOKEN_LIMIT = 2048
# Skip the O(N^2) duplicate scan above this many samples (Phase 1 sets are small).
MAX_DEDUP_SAMPLES = 3000
_TEXT_PREVIEW = 70


def _short(text: str) -> str:
    text = (text or "").strip()
    return text[:_TEXT_PREVIEW] + "…" if len(text) > _TEXT_PREVIEW else text


def _token_counts(pairs: list[dict]) -> list[int]:
    """Approximate token counts (tiktoken cl100k_base; word-based fallback)."""
    texts = [f"{p['instruction']}\n{p['output']}" for p in pairs]
    try:
        import tiktoken

        enc = tiktoken.get_encoding("cl100k_base")
        return [len(enc.encode(t)) for t in texts]
    except Exception:  # noqa: BLE001 — tiktoken unavailable/offline
        return [int(len(t.split()) * 1.3) for t in texts]


def _duplicate_groups(pairs: list[dict], embeddings: np.ndarray, threshold: float):
    n = len(pairs)
    if n < 2 or embeddings.size == 0 or n > MAX_DEDUP_SAMPLES:
        return [], 0

    sim = cosine_similarity(embeddings)
    adjacency = (sim >= threshold).astype(np.int8)
    np.fill_diagonal(adjacency, 0)
    _, labels = connected_components(csr_matrix(adjacency), directed=False)

    members: dict[int, list[int]] = defaultdict(list)
    for i, lbl in enumerate(labels):
        members[int(lbl)].append(i)

    groups = []
    for idxs in members.values():
        if len(idxs) > 1:
            groups.append(
                {
                    "indices": idxs,
                    "size": len(idxs),
                    "representative_text": _short(pairs[idxs[0]].get("instruction", "")),
                }
            )
    groups.sort(key=lambda g: g["size"], reverse=True)
    n_extra = sum(g["size"] - 1 for g in groups)  # removable duplicates
    return groups, n_extra


def analyze_cleaning(
    pairs: list[dict],
    embeddings: np.ndarray,
    dup_threshold: float = DUP_THRESHOLD,
) -> dict:
    n = len(pairs)
    groups, n_extra = _duplicate_groups(pairs, embeddings, dup_threshold)

    toks = _token_counts(pairs)

    def _flag(pred) -> list[int]:
        return [i for i in range(n) if pred(i)]

    def _ins(i: int) -> str:
        return (pairs[i].get("instruction") or "").strip()

    def _out(i: int) -> str:
        return (pairs[i].get("output") or "").strip()

    issues = {
        "empty_output": {"indices": _flag(lambda i: not _out(i)), "count": 0},
        "very_short_output": {
            "indices": _flag(lambda i: 0 < len(_out(i)) < SHORT_OUTPUT_CHARS),
            "count": 0,
            "threshold": SHORT_OUTPUT_CHARS,
        },
        "instruction_equals_output": {
            "indices": _flag(lambda i: _ins(i) and _ins(i) == _out(i)),
            "count": 0,
        },
        "long_token": {
            "indices": _flag(lambda i: toks[i] > LONG_TOKEN_LIMIT),
            "count": 0,
            "threshold": LONG_TOKEN_LIMIT,
        },
    }
    for v in issues.values():
        v["count"] = len(v["indices"])

    return {
        "n_samples": n,
        "dup_threshold": dup_threshold,
        "duplicate_groups": groups[:50],
        "n_duplicate_extra": n_extra,
        "issues": issues,
        "token_max": int(max(toks)) if toks else 0,
        "token_p95": int(np.percentile(toks, 95)) if toks else 0,
    }
