"""OpsSentinel Agent Layer — the ADK graph orchestrator (the cognitive brain).

A single generalized orchestrator: it pulls normalized alerts from Pub/Sub, correlates them
deterministically (pre-LLM), reasons with Gemini 2.0 Flash grounded in retrieved runbooks,
self-evaluates via Arize to set its autonomy tier, applies a deterministic Policy Engine, and
produces an execution brief for human approval before running a mocked remediation.
"""
