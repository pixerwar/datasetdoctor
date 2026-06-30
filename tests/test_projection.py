"""Projection and provider registry tests (Phase 2)."""
from __future__ import annotations

import numpy as np

from dataset_insight.embedding.registry import get_provider, VALID_PROVIDERS
from dataset_insight.embedding.tfidf_provider import TfidfProvider
from dataset_insight.projection import compute_projection
from dataset_insight.pipeline import build_report
from tests.synthetic import good_dataset, imbalanced_dataset


def test_registry_tfidf():
    p = get_provider("tfidf")
    assert isinstance(p, TfidfProvider)


def test_registry_unknown_raises():
    try:
        get_provider("bogus")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown provider")


def test_valid_providers_listed():
    assert "tfidf" in VALID_PROVIDERS
    assert "semantic" in VALID_PROVIDERS


def test_projection_explicit_labels():
    pairs = imbalanced_dataset(300)
    emb = TfidfProvider().embed([f"{p['instruction']} {p['output']}" for p in pairs])
    proj = compute_projection(pairs, emb)
    assert proj["method"] == "pca"
    assert len(proj["points"]) > 0
    # Explicit categories (5, reasonable) are used as labels
    labels = {pt["label"] for pt in proj["points"]}
    assert "Python" in labels
    # Each point has x, y, label, text fields
    pt = proj["points"][0]
    assert set(pt) == {"x", "y", "label", "text"}
    assert isinstance(pt["x"], float)


def test_projection_cluster_summary():
    pairs = imbalanced_dataset(300)
    emb = TfidfProvider().embed([f"{p['instruction']} {p['output']}" for p in pairs])
    proj = compute_projection(pairs, emb)
    clusters = proj["clusters"]
    assert len(clusters) >= 1
    # Sorted by count descending; dominant first
    assert clusters[0]["count"] >= clusters[-1]["count"]
    c = clusters[0]
    assert set(c) == {"label", "count", "share", "example"}
    assert clusters[0]["label"] == "Python"  # 80% dominant
    assert sum(c["count"] for c in clusters) == 300


def test_projection_unique_categories_fall_back_to_clusters():
    # Each row a unique category (e.g. the answer text chosen as category) -> KMeans
    pairs = [
        {"instruction": f"Question {i}", "output": f"Answer {i}", "category": f"unique-{i}"}
        for i in range(60)
    ]
    emb = TfidfProvider().embed([f"{p['instruction']} {p['output']}" for p in pairs])
    proj = compute_projection(pairs, emb)
    labels = {pt["label"] for pt in proj["points"]}
    # The unique categories must not be used; short "Cluster N" labels instead
    assert all(l.startswith("Cluster ") for l in labels)
    assert len(labels) <= 8


def test_projection_tiny_dataset_single_group():
    pairs = [
        {"instruction": f"Question {i}", "output": f"Answer {i}", "category": None}
        for i in range(5)
    ]
    emb = TfidfProvider().embed([f"{p['instruction']} {p['output']}" for p in pairs])
    proj = compute_projection(pairs, emb)
    assert {pt["label"] for pt in proj["points"]} == {"All samples"}


def test_build_report_includes_projection():
    report = build_report(good_dataset(120))
    assert "projection" in report
    assert report["embedding_provider"] == "tfidf"
    assert len(report["projection"]["points"]) > 0


def test_build_report_projection_optional():
    report = build_report(good_dataset(60), include_projection=False)
    assert "projection" not in report
