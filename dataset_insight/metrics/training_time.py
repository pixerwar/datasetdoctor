"""Training time estimate.

The output is always a range (not a single number) to avoid false precision.
"""
from __future__ import annotations

# Reference points (from real measurements).
REFERENCE_POINTS = {
    "3b": {"samples": 10000, "hours": 3.0},   # RTX 3060 12GB, QLoRA
    "1.5b": {"samples": 5000, "hours": 1.2},  # RTX 4060 8GB, QLoRA (rough interpolation)
}


def estimate_training_time(n_samples: int, model_size: str) -> tuple[float, float]:
    if model_size not in REFERENCE_POINTS:
        raise ValueError(
            f"Unknown model size: {model_size!r}. "
            f"Valid: {sorted(REFERENCE_POINTS)}"
        )
    ref = REFERENCE_POINTS[model_size]
    estimate = (n_samples / ref["samples"]) * ref["hours"]
    # Return a range, not a precise number.
    return (estimate * 0.7, estimate * 1.4)
