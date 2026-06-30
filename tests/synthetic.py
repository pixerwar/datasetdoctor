"""Synthetic dataset generators for the brief's 3 test scenarios.

1. Good example: 200 rows, diverse, balanced -> low risk
2. Risky example: 40 rows, most very similar to each other -> high risk
3. Imbalanced example: 300 rows, one category 80% -> medium-high + minority warning
"""
from __future__ import annotations

# Deterministic generation (no Math.random/randomness) — reproducible tests.

_TOPICS = [
    ("Python", "Python is a programming language."),
    ("History", "The Ottoman Empire was founded in 1299."),
    ("Science", "Water boils at 100 degrees Celsius."),
    ("Geography", "The capital of Turkey is Ankara."),
    ("Music", "An octave consists of eight notes."),
    ("Sports", "A football team has eleven players."),
    ("Art", "The Mona Lisa was painted by Leonardo da Vinci."),
    ("Food", "Pizza originated in Italy."),
]


def good_dataset(n: int = 200) -> list[dict]:
    """Diverse and balanced: topics rotate, each example has distinct content."""
    pairs = []
    for i in range(n):
        topic, fact = _TOPICS[i % len(_TOPICS)]
        pairs.append(
            {
                "instruction": f"Question {i} about {topic}: what can you say?",
                "output": f"{fact} Extra detail {i * 7 % 13} given in example {i}.",
                "category": topic,
            }
        )
    return pairs


def risky_dataset(n: int = 40) -> list[dict]:
    """Most examples are very similar (nearly identical text)."""
    pairs = []
    for i in range(n):
        pairs.append(
            {
                "instruction": "Hello, how are you?",
                "output": "I'm fine, thank you. How about you?",
                "category": None,
            }
        )
    return pairs


def imbalanced_dataset(n: int = 300, dominant_ratio: float = 0.80) -> list[dict]:
    """One category covers ~80% of the samples; the rest are a few minority ones."""
    pairs = []
    n_dominant = int(n * dominant_ratio)
    minor_topics = _TOPICS[1:5]  # 4 minority categories
    for i in range(n):
        if i < n_dominant:
            topic, fact = _TOPICS[0]
            pairs.append(
                {
                    "instruction": f"{topic} question {i}: what is the detail?",
                    "output": f"{fact} (variant {i}, number {i * 3 % 17})",
                    "category": topic,
                }
            )
        else:
            j = i - n_dominant
            topic, fact = minor_topics[j % len(minor_topics)]
            pairs.append(
                {
                    "instruction": f"{topic} question {i}: explain.",
                    "output": f"{fact} (variant {i})",
                    "category": topic,
                }
            )
    return pairs
