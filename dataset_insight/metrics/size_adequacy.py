"""Size adequacy."""
from __future__ import annotations

SIZE_THRESHOLDS = [
    (50, "minimal", "Very low; high risk of memorization"),
    (150, "low", "Minimal but usable; enough for a narrow persona"),
    (500, "good", "A solid foundation, suitable for most niche tasks"),
    (float("inf"), "high", "Broad coverage; diversity control is more critical"),
]


def compute_size_adequacy(n_samples: int, n_categories: int | None = None) -> dict:
    category = "minimal"
    message = SIZE_THRESHOLDS[0][2]
    for threshold, cat, msg in SIZE_THRESHOLDS:
        if n_samples < threshold:
            category, message = cat, msg
            break

    result = {
        "category": category,
        "message": message,
        "n_samples": n_samples,
    }

    # If the number of categories is known, add a relative assessment.
    if n_categories:
        recommended_minimum = n_categories * 30
        result["recommended_minimum"] = recommended_minimum
        if n_samples < recommended_minimum:
            result["relative_note"] = (
                f"Recommended minimum for {n_categories} categories is "
                f"~{recommended_minimum} samples; current {n_samples} is below that."
            )
        else:
            result["relative_note"] = (
                f"Recommended minimum for {n_categories} categories "
                f"(~{recommended_minimum} samples) is met."
            )

    return result
