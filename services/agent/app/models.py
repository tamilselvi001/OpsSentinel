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


@dataclass
class AgentProposal:
    """The structured JSON the ADK LlmAgent emits after calling the Elastic + Arize MCP tools.

    It carries the triage (classification), the RAG-bound recommendation, and the Arize metrics the
    agent gathered (so the deterministic governance step can map them to an autonomy tier without
    re-calling the tools).
    """

    category: str
    severity: str
    remediation_team: str
    confidence: float
    root_cause: str
    summary: str
    steps: list[str] = field(default_factory=list)
    commands: list[str] = field(default_factory=list)
    risk_level: str = "medium"
    based_on_runbook_id: str | None = None
    historical_match_ids: list[str] = field(default_factory=list)
    category_accuracy: float = 0.0
    calibration_error: float = 0.0
    is_novel: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> AgentProposal:
        """Tolerant builder from the LLM's JSON (missing/extra keys handled gracefully)."""
        return cls(
            category=str(data.get("category", "unknown")),
            severity=str(data.get("severity", "P3")),
            remediation_team=str(data.get("remediation_team", "sre-oncall")),
            confidence=float(data.get("confidence", 0.0) or 0.0),
            root_cause=str(data.get("root_cause", "")),
            summary=str(data.get("summary", "")),
            steps=[str(s) for s in (data.get("steps") or [])],
            commands=[str(c) for c in (data.get("commands") or [])],
            risk_level=str(data.get("risk_level", "medium")),
            based_on_runbook_id=data.get("based_on_runbook_id"),
            historical_match_ids=[str(m) for m in (data.get("historical_match_ids") or [])],
            category_accuracy=float(data.get("category_accuracy", 0.0) or 0.0),
            calibration_error=float(data.get("calibration_error", 0.0) or 0.0),
            is_novel=bool(data.get("is_novel", False)),
        )
