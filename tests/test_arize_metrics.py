"""Tests for the pure Arize metric computations + seed history shape (Phase 2, Tasks 5.3/5.4)."""

import importlib.util
import pathlib

_BASE = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _BASE / relpath)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


metrics = _load("arize_metrics", "services/mcp-arize/app/metrics.py")
seed_data = _load("seed_data", "scripts/seed_data.py")


def test_accuracy_and_calibration_basic():
    outcomes = [
        {"successful": True, "stated_confidence": 0.9},
        {"successful": True, "stated_confidence": 0.9},
        {"successful": False, "stated_confidence": 0.9},
    ]
    assert metrics.accuracy(outcomes) == 2 / 3
    # mean confidence 0.9 vs accuracy 0.667 -> ~0.233
    assert abs(metrics.calibration_error(outcomes) - 0.2333) < 0.001


def test_is_novel_threshold():
    assert metrics.is_novel([{"successful": True}] * 2) is True
    assert metrics.is_novel([{"successful": True}] * 10) is False


def test_empty_outcomes_are_safe():
    assert metrics.accuracy([]) == 0.0
    assert metrics.calibration_error([]) == 0.0


def _for_category(outcomes, category):
    return [o for o in outcomes if o["category"] == category]


def test_seed_history_hits_reference_targets():
    outcomes = seed_data.arize_outcomes()
    db_pool = _for_category(outcomes, "Database Connection Pool")
    # ~91% accuracy, well-calibrated (<5% variance) — the spec's reference walk-through.
    assert abs(metrics.accuracy(db_pool) - 0.91) < 0.005
    assert metrics.calibration_error(db_pool) < 0.05

    degraded = _for_category(outcomes, "Deployment Regression")
    assert metrics.accuracy(degraded) < 0.7  # degraded -> autonomy-lowering path
    assert metrics.calibration_error(degraded) > 0.05  # poorly calibrated

    novel = _for_category(outcomes, "DNS Resolution Failure")
    assert metrics.is_novel(novel) is True
