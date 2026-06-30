"""End-to-end pipeline checks for the brief's 3 scenarios + conversion/export."""
from __future__ import annotations

import json

from dataset_insight.conversion.rule_based import convert_csv_rows
from dataset_insight.conversion.llm_assisted import convert_txt, LLMConfig
from dataset_insight.export.chatml_export import export_chatml
from dataset_insight.pipeline import build_report
from tests.synthetic import good_dataset, risky_dataset, imbalanced_dataset


def test_scenario_good_low_risk():
    report = build_report(good_dataset(200))
    assert report["n_samples"] == 200
    assert report["size_adequacy"]["category"] in ("good", "high")
    assert report["composite_risk"]["risk_level"] == "low"
    assert report["diversity"]["level"] == "good"


def test_scenario_risky_high_risk():
    report = build_report(risky_dataset(40))
    assert report["n_samples"] == 40
    assert report["size_adequacy"]["category"] == "minimal"
    assert report["diversity"]["score"] < 0.6
    assert report["composite_risk"]["risk_level"] == "high"
    assert report["composite_risk"]["should_review_before_training"] is True


def test_scenario_imbalanced_minority_warning():
    report = build_report(imbalanced_dataset(300))
    assert report["n_samples"] == 300
    counts = report["balance"]["category_counts"]
    # The dominant category should cover most of the samples
    assert max(counts.values()) / 300 >= 0.6
    # A dominance warning is present
    assert any("dominant" in w for w in report["balance"]["warnings"])
    # Minority categories (< 30) are flagged in the risk output
    assert len(report["composite_risk"]["minority_category_warnings"]) >= 1
    # Imbalance escalation: a dominant category raises risk to at least medium_high
    assert report["composite_risk"]["risk_level"] == "medium_high"
    assert report["composite_risk"]["should_review_before_training"] is True


# --- conversion ------------------------------------------------------------
def test_csv_conversion():
    rows = [
        {"q": "Question 1", "a": "Answer 1", "cat": "X"},
        {"q": "Question 2", "a": "Answer 2", "cat": "Y"},
        {"q": "", "a": "empty question is skipped", "cat": "Z"},  # should be skipped
    ]
    pairs = convert_csv_rows(rows, "q", "a", "cat")
    assert len(pairs) == 2
    assert pairs[0] == {"instruction": "Question 1", "output": "Answer 1", "category": "X"}


def test_csv_missing_column_raises():
    try:
        convert_csv_rows([{"q": "x", "a": "y"}], "missing", "a")
    except ValueError:
        pass
    else:
        raise AssertionError("expected ValueError for missing column")


def test_txt_conversion_with_mock_llm():
    text = "First paragraph text.\n\nSecond paragraph text.\n\nThird paragraph."

    def fake_llm(prompt: str, config: LLMConfig) -> str:
        # A single small text becomes one chunk; return two pairs from this call.
        return json.dumps(
            [
                {"instruction": "Question 1?", "output": "Answer 1."},
                {"instruction": "Question 2?", "output": "Answer 2."},
            ],
            ensure_ascii=False,
        )

    pairs = convert_txt(
        text,
        character_description="a polite assistant",
        target_samples=2,
        config=LLMConfig(api_key="test"),
        llm_call=fake_llm,
    )
    assert len(pairs) == 2  # capped to target_samples
    assert all(p["instruction"] and p["output"] for p in pairs)


# --- export ----------------------------------------------------------------
def test_chatml_export_format():
    pairs = [{"instruction": "Hello", "output": "Hi", "category": None}]
    out = json.loads(export_chatml(pairs))
    assert out[0]["conversations"][0] == {"role": "user", "content": "Hello"}
    assert out[0]["conversations"][1] == {"role": "assistant", "content": "Hi"}
