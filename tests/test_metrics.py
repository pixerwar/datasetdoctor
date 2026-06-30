"""Unit tests for the 4 metric functions + the risk matrix."""
from __future__ import annotations

import numpy as np

from dataset_insight.metrics.diversity import compute_diversity, diversity_level
from dataset_insight.metrics.size_adequacy import compute_size_adequacy
from dataset_insight.metrics.training_time import estimate_training_time
from dataset_insight.metrics.balance import compute_balance
from dataset_insight.risk.composite import compute_composite_risk


# --- diversity -------------------------------------------------------------
def test_diversity_all_distinct():
    emb = np.eye(5)  # orthogonal -> nothing similar
    res = compute_diversity(emb, threshold=0.9)
    assert res["score"] == 1.0
    assert res["n_clusters"] == 5
    assert diversity_level(res["score"]) == "good"


def test_diversity_all_identical():
    emb = np.tile(np.array([1.0, 0.0, 0.0]), (6, 1))  # all identical
    res = compute_diversity(emb, threshold=0.9)
    assert res["n_clusters"] == 1
    assert res["score"] < 0.6
    assert diversity_level(res["score"]) == "high_risk"


def test_diversity_empty():
    assert compute_diversity(np.empty((0, 0)))["score"] == 0.0


# --- size adequacy ---------------------------------------------------------
def test_size_categories():
    assert compute_size_adequacy(30)["category"] == "minimal"
    assert compute_size_adequacy(100)["category"] == "low"
    assert compute_size_adequacy(300)["category"] == "good"
    assert compute_size_adequacy(2000)["category"] == "high"


def test_size_relative_note():
    res = compute_size_adequacy(50, n_categories=5)
    assert res["recommended_minimum"] == 150
    assert "below" in res["relative_note"]


# --- training time ---------------------------------------------------------
def test_training_time_range():
    lo, hi = estimate_training_time(10000, "3b")
    assert lo < hi
    assert abs(lo - 2.1) < 1e-6  # 3.0 * 0.7
    assert abs(hi - 4.2) < 1e-6  # 3.0 * 1.4


def test_training_time_unknown_model():
    try:
        estimate_training_time(100, "70b")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for unknown model")


# --- balance ---------------------------------------------------------------
def test_balance_explicit_counts():
    pairs = [{"instruction": "a", "output": "b", "category": "X"} for _ in range(8)]
    pairs += [{"instruction": "a", "output": "b", "category": "Y"} for _ in range(2)]
    res = compute_balance(pairs)
    assert res["method"] == "explicit"
    assert res["category_counts"] == {"X": 8, "Y": 2}
    # X dominant (80%) + Y under-represented (<10) warnings
    assert any("dominant" in w for w in res["warnings"])
    assert any("under-represented" in w for w in res["warnings"])


def test_balance_skipped_small():
    pairs = [{"instruction": "a", "output": "b", "category": None} for _ in range(10)]
    res = compute_balance(pairs)
    assert res["method"] == "skipped"


# --- composite risk --------------------------------------------------------
def test_risk_minimal_low_diversity_is_high():
    res = compute_composite_risk(
        {"score": 0.4}, "minimal", {"category_counts": {}}
    )
    assert res["risk_level"] == "high"
    assert res["suggested_epochs"] == 1
    assert res["should_review_before_training"] is True


def test_risk_good_diverse_is_low():
    res = compute_composite_risk(
        {"score": 0.95}, "good", {"category_counts": {"a": 50, "b": 50}}
    )
    assert res["risk_level"] == "low"
    assert res["suggested_epochs"] == 3
    assert res["should_review_before_training"] is False


def test_risk_minority_warnings():
    res = compute_composite_risk(
        {"score": 0.95}, "good", {"category_counts": {"a": 100, "b": 5}}
    )
    assert "b" in res["minority_category_warnings"]
    assert "a" not in res["minority_category_warnings"]


def test_risk_dominance_escalates_to_medium_high():
    # Diverse + good size but one category 80% -> base low, escalated to medium_high
    res = compute_composite_risk(
        {"score": 0.95}, "good", {"category_counts": {"a": 240, "b": 60}}
    )
    assert res["risk_level"] == "medium_high"
    assert res["should_review_before_training"] is True


def test_risk_dominance_does_not_downgrade_high():
    # If already high, the dominance escalation must not lower it
    res = compute_composite_risk(
        {"score": 0.4}, "minimal", {"category_counts": {"a": 38, "b": 2}}
    )
    assert res["risk_level"] == "high"


def test_risk_balanced_not_escalated():
    res = compute_composite_risk(
        {"score": 0.95}, "good", {"category_counts": {"a": 50, "b": 50}}
    )
    assert res["risk_level"] == "low"
