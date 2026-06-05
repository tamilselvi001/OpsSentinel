"""Exit Criterion 1 (logic level): a 50+ signal storm folds into ONE incident with zero alert loss.

Ties the Phase-2 Alert Simulator's storm generator to the Phase-3 time-windowed correlation, proving
the dedup invariant deterministically without the live queue. The live count-reconciliation +
empty-DLQ check is in scripts/run_storm.py (needs the emulator).
"""

import importlib.util
import pathlib
import sys

_BASE = pathlib.Path(__file__).resolve().parent.parent


def _load(name: str, relpath: str):
    spec = importlib.util.spec_from_file_location(name, _BASE / relpath)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


generator = _load("sim_generator_p5", "services/alert-simulator/app/generator.py")
correlation = _load("agent_correlation_p5", "services/agent/app/correlation.py")


def test_storm_of_50_folds_into_one_incident_with_no_loss():
    storm = generator.make_storm(50)
    assert len(storm) == 50

    contexts = correlation.group_by_correlation(storm, window_seconds=120)

    # Exactly one incident — the ~85% duplicate-reduction / single-entity guarantee.
    assert len(contexts) == 1
    assert contexts[0].size == 50

    # Zero alert loss: every published event id is retained in the single incident.
    published = {event.event_id for event in storm}
    folded = set(contexts[0].event_ids)
    assert folded == published


def test_larger_storm_still_single_incident():
    storm = generator.make_storm(120)
    contexts = correlation.group_by_correlation(storm, window_seconds=120)
    assert len(contexts) == 1
    assert contexts[0].size == 120
