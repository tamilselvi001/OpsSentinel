"""The OpsSentinel agent, built on **Google ADK** (the spec's mandated framework).

A single ``LlmAgent`` (Gemini 2.0 Flash) is the MCP **client** via two ``McpToolset`` instances over
**SSE** — one to the Elastic MCP server, one to the Arize MCP server (Phase 2). The agent classifies
the correlated incident, calls ``fetch_recent_logs`` + ``search_runbooks`` (RAG grounding) and the
Arize accuracy/calibration/novelty tools, then emits a structured JSON proposal. It is executed by
the ADK ``Runner``; with ``GoogleADKInstrumentor`` applied, every model call, tool call, and token
becomes an OpenInference span in Phoenix.

The **deterministic governance** (autonomy tier + Policy Engine + brief) runs off-LLM afterward in
:mod:`app.governance` — the LLM cannot bypass the policy gate. Node 9 (execution) stays a separate
deterministic consumer. Remediation stays mocked.
"""

from __future__ import annotations

import asyncio
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import uuid4

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams
from google.genai import types
from opentelemetry import trace

from app.config import AgentConfig, load_config
from app.governance import apply_governance
from app.models import AgentProposal
from lib.logging import get_logger

logger = get_logger("opssentinel.agent.adk")
APP_NAME = "opssentinel"
_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


@dataclass
class IncidentResult:
    incident_id: str
    status: str
    brief: dict[str, Any]
    autonomy_tier: str
    risk_level: str
    trace_id: str | None


def _instruction() -> str:
    classify = (_PROMPT_DIR / "classify.md").read_text(encoding="utf-8")
    recommend = (_PROMPT_DIR / "recommend.md").read_text(encoding="utf-8")
    return (
        "You are OpsSentinel's incident reasoner. You have tools from two MCP servers: the Elastic "
        "server (`fetch_recent_logs`, `search_runbooks`) and the Arize server "
        "(`get_category_accuracy`, `get_calibration`, `is_novel_category`).\n\n"
        "For each incident: (1) classify it, (2) call `fetch_recent_logs(service)` and "
        "`search_runbooks(<query>)` to ground your analysis in retrieved runbooks, (3) call the "
        "Arize tools for the incident's category to gather your historical accuracy, calibration "
        "error, and novelty, (4) synthesize a remediation grounded ONLY in the retrieved "
        "runbooks.\n\n"
        "Then respond with ONLY a JSON object (no prose, no markdown fences) with these keys: "
        "category, severity (P1-P4), remediation_team, confidence (0-1), root_cause, summary, "
        "steps (array), commands (array), risk_level (low|medium|high), based_on_runbook_id, "
        "historical_match_ids (array), category_accuracy (0-1), calibration_error (0-1), "
        "is_novel (boolean).\n\n"
        f"--- classification guidance ---\n{classify}\n\n"
        f"--- recommendation guidance ---\n{recommend}"
    )


def build_agent(config: AgentConfig | None = None) -> LlmAgent:
    """Build the ADK agent + its two SSE MCP toolsets. Constructs offline (no key needed)."""
    config = config or load_config()
    elastic_tools = McpToolset(connection_params=SseConnectionParams(url=config.mcp_elastic_url))
    arize_tools = McpToolset(connection_params=SseConnectionParams(url=config.mcp_arize_url))
    return LlmAgent(
        name="opssentinel_reasoner",
        model=config.gemini_model,
        instruction=_instruction(),
        tools=[elastic_tools, arize_tools],
    )


_runner: Runner | None = None


def _get_runner() -> Runner:
    global _runner
    if _runner is None:
        _runner = Runner(
            agent=build_agent(),
            app_name=APP_NAME,
            session_service=InMemorySessionService(),
        )
    return _runner


def _incident_prompt(context: Any) -> str:
    rep = context.representative
    return json.dumps(
        {
            "service": context.service,
            "environment": context.environment,
            "signal_count": context.size,
            "error_code": rep.error_code,
            "http_status": rep.http_status,
            "message": rep.message,
            "labels": rep.labels,
        }
    )


def _extract_json(text: str) -> dict[str, Any]:
    """Pull the JSON object out of the model's final response (tolerant of ```json fences/prose)."""
    if not text:
        return {}
    cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except json.JSONDecodeError:
                return {}
    return {}


async def _run_agent(context: Any) -> str:
    runner = _get_runner()
    user_id, session_id = "agent", str(uuid4())
    await runner.session_service.create_session(
        app_name=APP_NAME, user_id=user_id, session_id=session_id
    )
    message = types.Content(role="user", parts=[types.Part(text=_incident_prompt(context))])
    final_text = ""
    async for event in runner.run_async(
        user_id=user_id, session_id=session_id, new_message=message
    ):
        if event.is_final_response() and event.content and event.content.parts:
            final_text = event.content.parts[0].text or ""
    return final_text


# Substrings that mark a transient Gemini error worth retrying with backoff.
_TRANSIENT_MARKERS = ("503", "UNAVAILABLE", "RESOURCE_EXHAUSTED", "429", "500", "INTERNAL")


def _run_agent_with_retry(context: Any, attempts: int = 4) -> str:
    """Run the ADK agent, retrying transient model errors (503/429) with exponential backoff."""
    delay = 4.0
    for attempt in range(1, attempts + 1):
        try:
            return asyncio.run(_run_agent(context))
        except Exception as exc:
            message = str(exc)
            transient = any(marker in message for marker in _TRANSIENT_MARKERS)
            if attempt < attempts and transient:
                logger.warning(
                    "gemini transient error; retrying",
                    extra={"attempt": attempt, "error": message[:160]},
                )
                time.sleep(delay)
                delay = min(delay * 2, 30)
                continue
            raise


def run_incident(
    context: Any,
    *,
    store: Any,
    notifier: Any | None = None,
    incident_id: str | None = None,
) -> IncidentResult:
    """Run one incident through the ADK agent, then deterministic governance + persist."""
    incident_id = incident_id or str(uuid4())
    tracer = trace.get_tracer("opssentinel.agent")
    with tracer.start_as_current_span("incident") as span:
        trace_id = format(span.get_span_context().trace_id, "032x")
        raw = _run_agent_with_retry(context)
        logger.info("agent raw response", extra={"raw_preview": (raw or "")[:600]})
        proposal = AgentProposal.from_dict(_extract_json(raw))
        gov = apply_governance(incident_id, context, proposal)
        store.persist(gov.brief, "awaiting_approval", trace_id)
        if notifier is not None:
            try:
                notifier.notify(incident_id)
            except Exception as exc:
                logger.warning(
                    "slack notify failed", extra={"incident_id": incident_id, "error": str(exc)}
                )

    logger.info(
        "incident briefed (ADK)",
        extra={
            "incident_id": incident_id,
            "severity": gov.policy.final_severity,
            "autonomy_tier": gov.autonomy.tier,
            "approval_required": gov.policy.approval_required,
            "trace_id": trace_id,
        },
    )
    return IncidentResult(
        incident_id=incident_id,
        status="awaiting_approval",
        brief=gov.brief,
        autonomy_tier=gov.autonomy.tier,
        risk_level=proposal.risk_level,
        trace_id=trace_id,
    )
