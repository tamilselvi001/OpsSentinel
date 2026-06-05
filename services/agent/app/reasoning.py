"""Gemini 2.0 Flash reasoning (nodes 3 & 5) — the only LLM steps.

Classification and the RAG-bound recommendation, with **structured output** (a response schema) so
each node returns a validated object. Prompts are centralized in ``services/agent/prompts/``. The
key resolves only via :func:`lib.secrets.get_secret`. Heavy ``google-genai`` import is module-level
(only the agent process loads this module; the unit tests use a fake Reasoner instead).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.models import Classification, Recommendation
from lib.secrets import get_secret

_PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"

_CLASSIFY_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "severity": {"type": "string", "enum": ["P1", "P2", "P3", "P4"]},
        "remediation_team": {"type": "string"},
        "confidence": {"type": "number"},
        "root_cause": {"type": "string"},
    },
    "required": ["category", "severity", "remediation_team", "confidence", "root_cause"],
}

_RECOMMEND_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "steps": {"type": "array", "items": {"type": "string"}},
        "commands": {"type": "array", "items": {"type": "string"}},
        "risk_level": {"type": "string", "enum": ["low", "medium", "high"]},
        "based_on_runbook_id": {"type": "string"},
    },
    "required": ["summary", "steps", "commands", "risk_level"],
}


class GeminiReasoner:
    """Concrete :class:`app.interfaces.Reasoner` backed by Gemini 2.0 Flash."""

    def __init__(self, model: str = "gemini-2.0-flash") -> None:
        self._client = genai.Client(api_key=get_secret("gemini-api-key"))
        self._model = model
        self._classify_prompt = (_PROMPT_DIR / "classify.md").read_text(encoding="utf-8")
        self._recommend_prompt = (_PROMPT_DIR / "recommend.md").read_text(encoding="utf-8")

    def classify(self, context: Any) -> Classification:
        payload = {
            "service": context.service,
            "environment": context.environment,
            "signal_count": context.size,
            "signals": [
                {
                    "source": str(e.source),
                    "severity_hint": str(e.severity_hint),
                    "error_code": e.error_code,
                    "http_status": e.http_status,
                    "message": e.message,
                    "labels": e.labels,
                }
                for e in context.events[:25]
            ],
        }
        data = self._generate_json(self._classify_prompt, payload, _CLASSIFY_SCHEMA)
        return Classification(
            category=data["category"],
            severity=data["severity"],
            remediation_team=data["remediation_team"],
            confidence=float(data["confidence"]),
            root_cause=data["root_cause"],
        )

    def synthesize(
        self,
        context: Any,
        classification: Classification,
        logs: list[dict[str, Any]],
        runbooks: list[dict[str, Any]],
    ) -> Recommendation:
        payload = {
            "incident": {
                "service": context.service,
                "category": classification.category,
                "severity": classification.severity,
                "root_cause": classification.root_cause,
            },
            "recent_logs": logs[:25],
            "retrieved_runbooks": runbooks,  # RAG grounding: the ONLY allowed source of steps
        }
        data = self._generate_json(self._recommend_prompt, payload, _RECOMMEND_SCHEMA)
        return Recommendation(
            summary=data["summary"],
            steps=list(data.get("steps", [])),
            commands=list(data.get("commands", [])),
            risk_level=data.get("risk_level", "medium"),
            based_on_runbook_id=data.get("based_on_runbook_id"),
        )

    def _generate_json(
        self, system_instruction: str, payload: dict[str, Any], schema: dict[str, Any]
    ) -> dict[str, Any]:
        response = self._client.models.generate_content(
            model=self._model,
            contents=[json.dumps(payload)],
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.2,
            ),
        )
        return json.loads(response.text)
