"""Slack bot HTTP service: ``/notify`` (agent → post brief), ``/slack/interactions``, ``/health``.

Credentials resolve only via the Phase-1 secrets accessor. Heavy clients are imported lazily so the
process starts and ``/health`` responds before the first call.
"""

from __future__ import annotations

import json
import os
from typing import Any
from urllib.parse import parse_qs

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse

from app.actions import handle_decision
from app.brief_format import brief_from_incident, build_message
from app.signing import verify_signature
from lib.logging import get_logger
from lib.secrets import get_secret

logger = get_logger("opssentinel.slack-bot")
app = FastAPI(title="OpsSentinel Slack Bot", version="0.1.0")

SLACK_CHANNEL = os.environ.get("SLACK_CHANNEL", "#opssentinel")
DASHBOARD_BASE_URL = os.environ.get("DASHBOARD_BASE_URL", "")
ACTIONS_TOPIC = os.environ.get("OPSSENTINEL_ACTIONS_TOPIC", "opssentinel-actions")
PROJECT_ID = (
    os.environ.get("PUBSUB_PROJECT_ID")
    or os.environ.get("GOOGLE_CLOUD_PROJECT")
    or "opssentinel-mvp"
)


class _PubSubPublisher:
    def publish_action(self, decision: dict[str, Any]) -> None:
        from google.cloud import pubsub_v1

        publisher = pubsub_v1.PublisherClient()
        topic_path = publisher.topic_path(PROJECT_ID, ACTIONS_TOPIC)
        publisher.publish(topic_path, json.dumps(decision).encode("utf-8")).result(timeout=30)


class _DbUpdater:
    def set_rejected(self, incident_id: str, approver: str) -> None:
        from lib.db import upsert_incident

        upsert_incident(
            {
                "incident_id": incident_id,
                "status": "rejected",
                "approval_status": "rejected",
                "approver_subject": approver,
            }
        )

    def audit(self, incident_id: str, actor: str, action: str, details: dict[str, Any]) -> None:
        from lib.db import append_audit

        append_audit(actor=actor, action=action, incident_id=incident_id, details=details)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "slack-bot"}


@app.post("/notify")
async def notify(request: Request) -> Response:
    """Internal: the agent posts ``{incident_id}`` when an incident reaches awaiting_approval."""
    payload = await request.json()
    incident_id = payload.get("incident_id")
    if not incident_id:
        return JSONResponse({"error": "incident_id required"}, status_code=400)

    from lib.db import get_incident

    row = get_incident(incident_id)
    if not row:
        return JSONResponse({"error": "incident not found"}, status_code=404)

    brief = brief_from_incident(row)
    dashboard_url = f"{DASHBOARD_BASE_URL}/incidents/{incident_id}" if DASHBOARD_BASE_URL else None
    message = build_message(brief, dashboard_url=dashboard_url)

    from slack_sdk import WebClient

    WebClient(token=get_secret("slack-bot-token")).chat_postMessage(
        channel=SLACK_CHANNEL, text=message["text"], blocks=message["blocks"]
    )
    logger.info("posted brief to slack", extra={"incident_id": incident_id})
    return JSONResponse({"ok": True})


@app.post("/slack/interactions")
async def interactions(request: Request) -> Response:
    """Slack interactivity URL: signature-verified Approve/Reject handling."""
    body = (await request.body()).decode("utf-8")
    timestamp = request.headers.get("X-Slack-Request-Timestamp", "")
    signature = request.headers.get("X-Slack-Signature", "")
    if not verify_signature(get_secret("slack-signing-secret"), timestamp, body, signature):
        return Response(status_code=401)

    payload = json.loads(parse_qs(body).get("payload", ["{}"])[0])
    action = (payload.get("actions") or [{}])[0]
    user = payload.get("user") or {}
    approver = user.get("username") or user.get("id") or "slack-user"
    try:
        result = handle_decision(
            action.get("action_id"),
            action.get("value"),
            approver,
            publisher=_PubSubPublisher(),
            updater=_DbUpdater(),
        )
    except ValueError:
        return Response(status_code=400)
    logger.info(
        "handled slack interaction",
        extra={"incident_id": action.get("value"), "result": result},
    )
    return JSONResponse({"text": f"Incident {action.get('value')} {result}."})
