"""Cleaning analysis tests (near-duplicates + quality lint)."""
from __future__ import annotations

from dataset_insight.cleaning import analyze_cleaning
from dataset_insight.embedding.tfidf_provider import TfidfProvider
from dataset_insight.pipeline import build_report, compute_embeddings
from tests.synthetic import good_dataset, risky_dataset


def _emb(pairs):
    return TfidfProvider().embed([f"{p['instruction']} {p['output']}" for p in pairs])


def test_duplicates_detected():
    # risky_dataset is 40 identical pairs -> one big duplicate group
    pairs = risky_dataset(40)
    res = analyze_cleaning(pairs, _emb(pairs))
    assert len(res["duplicate_groups"]) == 1
    assert res["duplicate_groups"][0]["size"] == 40
    assert res["n_duplicate_extra"] == 39  # keep 1, remove 39


def test_no_false_duplicates_on_distinct():
    # Genuinely distinct content (different words) -> no near-duplicates
    pairs = [
        {"instruction": "What is Python?", "output": "A programming language.", "category": None},
        {"instruction": "When was Rome founded?", "output": "Around 753 BC.", "category": None},
        {"instruction": "How do plants make food?", "output": "Through photosynthesis.", "category": None},
        {"instruction": "What is the capital of Japan?", "output": "Tokyo.", "category": None},
    ]
    res = analyze_cleaning(pairs, _emb(pairs))
    assert res["n_duplicate_extra"] == 0


def test_quality_issues_flagged():
    pairs = [
        {"instruction": "Valid?", "output": "A proper answer here.", "category": None},
        {"instruction": "Empty?", "output": "   ", "category": None},  # empty
        {"instruction": "Short?", "output": "no", "category": None},  # very short
        {"instruction": "Repeat this line", "output": "Repeat this line", "category": None},  # equals
    ]
    res = analyze_cleaning(pairs, _emb(pairs))
    issues = res["issues"]
    assert issues["empty_output"]["count"] == 1
    assert issues["very_short_output"]["count"] == 1  # only "no"
    assert issues["instruction_equals_output"]["count"] == 1


def test_report_includes_cleaning():
    report = build_report(good_dataset(60))
    assert "cleaning" in report
    assert "duplicate_groups" in report["cleaning"]
    assert "issues" in report["cleaning"]


def test_precomputed_embeddings_reused():
    pairs = good_dataset(40)
    emb = compute_embeddings(pairs, "tfidf")
    # passing embeddings should not raise and should produce the same n_samples
    report = build_report(pairs, embeddings=emb)
    assert report["n_samples"] == 40
