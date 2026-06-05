"""Deterministic Policy Engine (node 7) — hard rules + governance gates, independent of the LLM.

Operates alongside Gemini; **hard rules win**. The LLM cannot bypass these gates. Implements the
shared-contract Policy Engine:
- ``production`` + a critical service (payment/checkout/auth) → minimum severity **P1**.
- ``production`` (any service) → minimum severity **P2**.
- A database **schema change** → require DBA approval regardless of confidence.
- Any action with ``risk_level = high`` → require explicit human approval.
- The agent is restricted to **non-destructive** actions unless explicitly authorized.
- ``autonomy_tier = low`` → human review (no autonomous execution).

Pure logic — unit-testable. SLA timers live in :mod:`policy.sla`.
"""

from __future__ import annotations

from dataclasses import dataclass, field

CRITICAL_SERVICE_TOKENS = ("payment", "checkout", "auth")
DESTRUCTIVE_TOKENS = (
    "delete ",
    "drop ",
    "rm -rf",
    "terminate",
    "destroy",
    "truncate",
    "--force",
    "kubectl delete",
)
SCHEMA_CHANGE_TOKENS = (
    "alter table",
    "drop table",
    "create table",
    "drop column",
    "add column",
    "schema change",
    "migration",
)

# Lower rank = more severe. P1 is the most urgent.
_SEVERITY_RANK = {"P1": 1, "P2": 2, "P3": 3, "P4": 4}


@dataclass
class PolicyInput:
    severity: str
    environment: str
    service: str
    risk_level: str
    autonomy_tier: str
    recommended_steps: list[str] = field(default_factory=list)
    recommended_commands: list[str] = field(default_factory=list)
    explicitly_authorized: bool = False  # a senior engineer pre-authorized via the approval webhook


@dataclass
class PolicyDecision:
    final_severity: str
    approval_required: bool
    allowed_autonomous: bool
    gates: list[str]


def _is_critical_service(service: str) -> bool:
    name = service.lower()
    return any(token in name for token in CRITICAL_SERVICE_TOKENS)


def severity_floor(environment: str, service: str) -> str:
    """The minimum (most-urgent) severity the policy permits for this context."""
    if environment.lower() == "production" and _is_critical_service(service):
        return "P1"
    if environment.lower() == "production":
        return "P2"
    return "P4"


def enforce_minimum_severity(severity: str, environment: str, service: str) -> str:
    """Raise ``severity`` up to the policy floor if the LLM under-rated it."""
    floor = severity_floor(environment, service)
    assigned_rank = _SEVERITY_RANK.get(severity, 4)
    return severity if assigned_rank <= _SEVERITY_RANK[floor] else floor


def _matches(tokens: tuple[str, ...], steps: list[str], commands: list[str]) -> bool:
    blob = " ".join([*steps, *commands]).lower()
    return any(token in blob for token in tokens)


def is_destructive(steps: list[str], commands: list[str]) -> bool:
    return _matches(DESTRUCTIVE_TOKENS, steps, commands)


def is_schema_change(steps: list[str], commands: list[str]) -> bool:
    return _matches(SCHEMA_CHANGE_TOKENS, steps, commands)


def evaluate(policy_input: PolicyInput) -> PolicyDecision:
    """Apply the hard rules and governance gates; return the binding decision."""
    gates: list[str] = []
    final_severity = enforce_minimum_severity(
        policy_input.severity, policy_input.environment, policy_input.service
    )

    if policy_input.risk_level == "high":
        gates.append("high_risk_requires_approval")
    if is_schema_change(policy_input.recommended_steps, policy_input.recommended_commands):
        gates.append("dba_approval_schema_change")
    if (
        is_destructive(policy_input.recommended_steps, policy_input.recommended_commands)
        and not policy_input.explicitly_authorized
    ):
        gates.append("destructive_action_unauthorized")
    if policy_input.autonomy_tier == "low":
        gates.append("low_autonomy_human_review")

    approval_required = bool(gates)
    # Autonomous execution is only ever allowed when no gate fired AND the agent is fully confident.
    allowed_autonomous = not approval_required and policy_input.autonomy_tier == "high"
    return PolicyDecision(
        final_severity=final_severity,
        approval_required=approval_required,
        allowed_autonomous=allowed_autonomous,
        gates=gates,
    )
