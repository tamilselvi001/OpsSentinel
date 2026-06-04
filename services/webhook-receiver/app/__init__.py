"""OpsSentinel webhook receiver — the Input Layer that feeds the Queue Layer.

Receives inbound monitoring webhooks, deterministically normalizes each into the shared
AlertEvent contract, and publishes to the ``opssentinel-alerts`` topic. No correlation, no LLM —
those belong to the Agent Layer (Phase 3).
"""
