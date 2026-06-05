"""Validated data structures the reasoning nodes produce and the brief / policy consume.

Plain dataclasses (no heavy deps) so they are importable and testable in isolation. The Gemini
nodes (Task 6.5) return these; the deterministic nodes consume them.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Classification:
    """Output of the Reason node (node 3): incident triage."""

    category: str
    severity: str  # P1 | P2 | P3 | P4
    remediation_team: str
    confidence: float  # 0..1, calibrated
    root_cause: str


@dataclass
class Recommendation:
    """Output of the Synthesize node (node 5): a RAG-bound remediation plan."""

    summary: str
    steps: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    risk_level: str = "medium"  # low | medium | high
    based_on_runbook_id: str | None = None
