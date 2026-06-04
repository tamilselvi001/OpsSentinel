"""The OpenInference instrumentation helper must import cleanly (Phase 2, Task 5.3 acceptance).

Heavy OTel/OpenInference deps are lazy inside configure_tracing, so importing the module and
referencing the function must work without those packages installed.
"""

import lib.observability as observability


def test_helper_imports_cleanly_and_exposes_configure_tracing():
    assert callable(observability.configure_tracing)
    assert observability.DEFAULT_COLLECTOR.startswith("http")
