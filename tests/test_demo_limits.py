"""Demo abuse protection: per-IP rate limiting + dataset cap with eviction.

Both are disabled by default (0), so these tests flip the module-level knobs on
and restore them via monkeypatch.
"""
from __future__ import annotations

import io
import os

from fastapi.testclient import TestClient

from dataset_insight.api import main

client = TestClient(main.app)


def _csv() -> bytes:
    lines = ["question,answer,topic"]
    for i in range(10):
        lines.append(f"Q{i}?,A{i}.,T{i % 2}")
    return "\n".join(lines).encode()


def _upload():
    return client.post(
        "/datasets/upload",
        files={"file": ("d.csv", io.BytesIO(_csv()), "text/csv")},
    )


def test_rate_limit_returns_429_after_threshold(monkeypatch):
    monkeypatch.setattr(main, "RATE_LIMIT_PER_MIN", 3)
    main._rate_hits.clear()

    # First 3 pass, the 4th is limited.
    assert _upload().status_code == 200
    assert _upload().status_code == 200
    assert _upload().status_code == 200
    limited = _upload()
    assert limited.status_code == 429
    assert "Retry-After" in limited.headers

    main._rate_hits.clear()  # don't leak state to other tests


def test_rate_limit_off_by_default():
    # Sanity: with the default (0), many uploads all succeed.
    main._rate_hits.clear()
    for _ in range(6):
        assert _upload().status_code == 200


def test_dataset_cap_evicts_oldest(monkeypatch):
    monkeypatch.setattr(main, "MAX_DATASETS", 2)

    first = _upload().json()["dataset_id"]
    first_file = main.store.get(first).sources[0].file_path
    assert os.path.exists(first_file)

    second = _upload().json()["dataset_id"]
    third = _upload().json()["dataset_id"]

    # Only the two newest survive; the oldest was evicted (record + file).
    assert main.store.count() == 2
    assert client.get(f"/datasets/{first}/report").status_code == 404
    assert not os.path.exists(first_file)
    assert client.get(f"/datasets/{second}/report").status_code in (409, 200)
    assert client.get(f"/datasets/{third}/report").status_code in (409, 200)
