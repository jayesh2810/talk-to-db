"""
Shared signal normalization utilities used by the scoring engine.

All normalization functions map raw signal values to [0, 1] where
1.0 represents maximum risk/likelihood for the prediction in question.
"""

import datetime


def normalize_days(days: int, max_days: int = 90) -> float:
    """Normalize days to [0, 1]; more days = higher churn risk."""
    return min(days / max_days, 1.0)


def normalize_rate(rate: float) -> float:
    """Clamp a rate that is already in [0, 1]."""
    return max(0.0, min(1.0, rate))


def normalize_count(count: int, max_count: int) -> float:
    """Normalize an integer count to [0, 1]."""
    return min(count / max_count, 1.0)


def invert(value: float) -> float:
    """Invert a [0, 1] signal so high engagement → low risk."""
    return 1.0 - max(0.0, min(1.0, value))


def clamp(value: float) -> float:
    """Clamp a score to [0, 1]."""
    return max(0.0, min(1.0, value))


def variance_confidence(signal_values: list[float], score: float) -> float:
    """
    Compute confidence based on signal agreement.

    When all signals agree (all high or all low), variance is low → high confidence.
    When signals are mixed, variance is high → lower confidence.
    """
    if not signal_values:
        return 0.5
    var = sum((v - score) ** 2 for v in signal_values) / len(signal_values)
    return max(0.3, 1.0 - (var * 3.0))
