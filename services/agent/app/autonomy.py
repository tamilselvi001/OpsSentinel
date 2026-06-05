"""Adaptive autonomy (node 6): map Arize self-evaluation metrics → an ``autonomy_tier``.

Runtime adaptive autonomy, exactly per the shared contract:
- **≥ 90%** accuracy **and** well-calibrated (calibration error < 5%) → ``high`` (assertive).
- **70–89%** (or ≥ 90% but poorly calibrated) → ``moderate`` (proceed, lower confidence, caution).
- **< 70%**, OR the category is **novel**, OR intent confidence **< 70%** → ``low`` (flag for human
  review; the agent must not propose autonomous execution).

Pure logic — no MCP/network — so it is unit-testable. ``degraded_fallback`` is the safe default
when the Arize MCP server is unreachable: a tracing/eval hiccup must never crash incident handling,
it must degrade to the safest tier.
"""

from __future__ import annotations

from dataclasses import dataclass

HIGH_ACCURACY = 0.90
MODERATE_ACCURACY = 0.70
CALIBRATION_TARGET = 0.05  # stated-confidence-vs-empirical-accuracy variance must stay < 5%
INTENT_CONFIDENCE_FLOOR = 0.70


@dataclass
class AutonomyDecision:
    tier: str  # high | moderate | low
    requires_human: bool
    reason: str
    caution_note: str | None = None


def decide_autonomy(
    accuracy: float,
    calibration_error: float,
    is_novel: bool,
    intent_confidence: float = 1.0,
) -> AutonomyDecision:
    """Map the Arize metrics for this incident's category to an autonomy tier."""
    if is_novel:
        return AutonomyDecision(
            "low",
            requires_human=True,
            reason="novel category — little/no historical accuracy",
            caution_note="Unseen incident type; routing to human review.",
        )
    if intent_confidence < INTENT_CONFIDENCE_FLOOR:
        return AutonomyDecision(
            "low",
            requires_human=True,
            reason=f"intent confidence {intent_confidence:.0%} below {INTENT_CONFIDENCE_FLOOR:.0%}",
            caution_note="Low classification confidence; routing to human review.",
        )
    if accuracy < MODERATE_ACCURACY:
        return AutonomyDecision(
            "low",
            requires_human=True,
            reason=f"category accuracy {accuracy:.0%} below {MODERATE_ACCURACY:.0%}",
            caution_note="Historical accuracy degraded; routing to human review.",
        )
    if accuracy >= HIGH_ACCURACY and calibration_error < CALIBRATION_TARGET:
        return AutonomyDecision(
            "high",
            requires_human=False,
            reason=f"accuracy {accuracy:.0%}, well-calibrated ({calibration_error:.1%})",
        )
    return AutonomyDecision(
        "moderate",
        requires_human=False,
        reason=f"accuracy {accuracy:.0%}, calibration error {calibration_error:.1%}",
        caution_note="Proceeding with lowered stated confidence; verify before approval.",
    )


def degraded_fallback(reason: str) -> AutonomyDecision:
    """Safe default when self-evaluation is unavailable — never crash, degrade to ``low``."""
    return AutonomyDecision(
        "low",
        requires_human=True,
        reason=f"observability unavailable: {reason}",
        caution_note="Self-evaluation unavailable; defaulting to human review.",
    )
