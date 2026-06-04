"""Pure observability metric computations over a list of outcome records.

An *outcome* is a dict: ``{category, approved, successful, stated_confidence}``. These functions
are storage-agnostic and unit-testable; the store layer fetches rows and calls them. All values
are fractions in [0, 1].
"""

from __future__ import annotations

from typing import Any

# Below this many historical outcomes, a category is treated as novel (drift / unseen type).
NOVELTY_THRESHOLD = 5


def accuracy(outcomes: list[dict[str, Any]]) -> float:
    """Empirical accuracy = fraction of outcomes whose remediation was successful."""
    scored = [o for o in outcomes if o.get("successful") is not None]
    if not scored:
        return 0.0
    return sum(1 for o in scored if o["successful"]) / len(scored)


def calibration_error(outcomes: list[dict[str, Any]]) -> float:
    """|mean stated confidence − empirical accuracy| (the <5% calibration metric)."""
    confidences = [
        o["stated_confidence"] for o in outcomes if o.get("stated_confidence") is not None
    ]
    if not confidences:
        return 0.0
    mean_confidence = sum(confidences) / len(confidences)
    return abs(mean_confidence - accuracy(outcomes))


def is_novel(outcomes: list[dict[str, Any]], threshold: int = NOVELTY_THRESHOLD) -> bool:
    """True when there is little/no history for the category."""
    return len(outcomes) < threshold
