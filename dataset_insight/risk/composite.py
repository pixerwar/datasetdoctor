"""Composite risk matrix.

Inputs: diversity score, size category, balance result.
Outputs: risk level, minority category warnings, suggested epochs, review flag.

The risk level is determined in two stages:
1. Base risk: derived from diversity + size.
2. Imbalance escalation: if a category covers >60% of the samples (dominant), the
   dataset is prone to memorizing the dominant category, so the risk is raised to at
   least `medium_high` (never lowered if the current risk is already higher).
"""
from __future__ import annotations

MINORITY_THRESHOLD = 30  # is every category >= 30?
DOMINANCE_THRESHOLD = 0.60  # a category > 60% -> dominant
EPOCH_SUGGESTION = {"low": 3, "medium": 2, "medium_high": 1, "high": 1}

# Risk severity ordering (for escalation / floor comparisons).
_SEVERITY = {"low": 0, "medium": 1, "medium_high": 2, "high": 3}


def _at_least(risk: str, floor: str) -> str:
    """Raise risk to floor if it is below floor; otherwise leave it unchanged."""
    return risk if _SEVERITY[risk] >= _SEVERITY[floor] else floor


def compute_composite_risk(
    diversity: dict, size_category: str, balance: dict
) -> dict:
    div_score = diversity.get("score", 0.0)
    counts = balance.get("category_counts", {})
    total = sum(counts.values())
    max_ratio = (max(counts.values()) / total) if total else 0.0
    is_dominated = max_ratio > DOMINANCE_THRESHOLD

    # 1) Base risk: diversity + size.
    if size_category == "minimal":
        risk = "high" if div_score < 0.6 else "medium"
    elif div_score < 0.6:
        risk = "medium_high" if size_category in ("good", "high") else "high"
    else:
        risk = "low"

    # 2) Imbalance escalation: a dominant category raises risk to at least medium_high.
    if is_dominated:
        risk = _at_least(risk, "medium_high")

    # Minority category check: is every category >= MINORITY_THRESHOLD?
    minority_warnings = [
        cat for cat, count in counts.items() if count < MINORITY_THRESHOLD
    ]

    epoch_suggestion = EPOCH_SUGGESTION[risk]

    return {
        "risk_level": risk,  # low | medium | medium_high | high
        "minority_category_warnings": minority_warnings,
        "suggested_epochs": epoch_suggestion,
        "should_review_before_training": risk in ("medium_high", "high"),
    }
