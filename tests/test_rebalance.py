"""Local class-imbalance fix (downsample plan + minority guidance)."""
from __future__ import annotations

from dataset_insight.rebalance import plan_rebalance


def _pairs(spec: dict[str, int]) -> list[dict]:
    """Build pairs from {category: count}."""
    out = []
    for cat, n in spec.items():
        for i in range(n):
            out.append({"instruction": f"{cat} q{i}", "output": f"{cat} a{i}", "category": cat})
    return out


def test_downsample_dominant_to_target():
    pairs = _pairs({"A": 80, "B": 20})  # A is 80%
    plan = plan_rebalance(pairs, target_share=0.5)
    assert plan["applicable"] is True
    assert plan["dominant"]["category"] == "A"
    assert plan["dominant"]["count"] == 80
    # keep k s.t. k/(20+k) <= 0.5  -> k = 20, remove 60
    assert plan["target_count"] == 20
    assert plan["n_removable"] == 60
    assert len(plan["remove_indices"]) == 60
    # removed indices are all in category A, and the first 20 A's are kept
    assert all(pairs[i]["category"] == "A" for i in plan["remove_indices"])
    assert min(plan["remove_indices"]) == 20  # first 20 (idx 0..19) kept
    assert plan["result_counts"] == {"A": 20, "B": 20}


def test_already_balanced_not_applicable():
    plan = plan_rebalance(_pairs({"A": 50, "B": 50}), target_share=0.5)
    assert plan["applicable"] is False
    assert plan["remove_indices"] == []


def test_no_explicit_categories_returns_none_method():
    pairs = [{"instruction": "q", "output": "a"} for _ in range(20)]
    plan = plan_rebalance(pairs)
    assert plan["applicable"] is False
    assert plan["method"] == "none"


def test_partial_categories_treated_as_non_explicit():
    pairs = _pairs({"A": 5})
    pairs.append({"instruction": "q", "output": "a"})  # missing category
    plan = plan_rebalance(pairs)
    assert plan["method"] == "none"


def test_single_category_not_applicable_but_explicit():
    plan = plan_rebalance(_pairs({"A": 40}))
    assert plan["method"] == "explicit"
    assert plan["applicable"] is False


def test_minority_guidance_suggestions():
    plan = plan_rebalance(_pairs({"A": 80, "B": 12}), target_share=0.5)
    # B has 12 (< 30) -> a "collect more" suggestion mentioning B and the gap.
    assert any("'B'" in s and "18" in s for s in plan["suggestions"])


def test_removed_indices_span_only_the_dominant_tail():
    pairs = _pairs({"X": 10, "big": 90})  # 'big' dominates
    plan = plan_rebalance(pairs, target_share=0.5)
    kept = [i for i in range(len(pairs)) if i not in set(plan["remove_indices"])]
    kept_counts: dict[str, int] = {}
    for i in kept:
        kept_counts[pairs[i]["category"]] = kept_counts.get(pairs[i]["category"], 0) + 1
    assert kept_counts["X"] == 10
    assert kept_counts["big"] == plan["target_count"]
    # no single class is the majority after the plan
    total = sum(kept_counts.values())
    assert max(kept_counts.values()) / total <= 0.5 + 1e-9
