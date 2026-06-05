"""Tests for the adaptive autonomy mapping (Phase 3, Task 6.7)."""

import importlib.util
import pathlib
import sys

_PATH = (
    pathlib.Path(__file__).resolve().parent.parent / "services" / "agent" / "app" / "autonomy.py"
)
_spec = importlib.util.spec_from_file_location("agent_autonomy", _PATH)
autonomy = importlib.util.module_from_spec(_spec)
sys.modules["agent_autonomy"] = autonomy
_spec.loader.exec_module(autonomy)


def test_high_tier_when_accurate_and_well_calibrated():
    d = autonomy.decide_autonomy(accuracy=0.91, calibration_error=0.01, is_novel=False)
    assert d.tier == "high"
    assert d.requires_human is False


def test_moderate_when_mid_accuracy():
    d = autonomy.decide_autonomy(accuracy=0.80, calibration_error=0.02, is_novel=False)
    assert d.tier == "moderate"
    assert d.requires_human is False
    assert d.caution_note  # carries a caution note


def test_moderate_when_accurate_but_poorly_calibrated():
    d = autonomy.decide_autonomy(accuracy=0.95, calibration_error=0.20, is_novel=False)
    assert d.tier == "moderate"  # high requires well-calibrated


def test_low_when_degraded_accuracy():
    d = autonomy.decide_autonomy(accuracy=0.55, calibration_error=0.30, is_novel=False)
    assert d.tier == "low"
    assert d.requires_human is True


def test_low_when_novel_category():
    d = autonomy.decide_autonomy(accuracy=0.99, calibration_error=0.0, is_novel=True)
    assert d.tier == "low"
    assert d.requires_human is True


def test_low_when_intent_confidence_below_floor():
    d = autonomy.decide_autonomy(
        accuracy=0.95, calibration_error=0.0, is_novel=False, intent_confidence=0.5
    )
    assert d.tier == "low"
    assert d.requires_human is True


def test_degraded_fallback_is_low_and_requires_human():
    d = autonomy.degraded_fallback("arize unreachable")
    assert d.tier == "low"
    assert d.requires_human is True
