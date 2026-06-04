"""FastAPI webhook receiver: ingest monitoring webhooks → normalize → publish to the queue."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from app.normalizers import NORMALIZERS
from lib.logging import get_logger
from lib.pubsub import publish_alert

logger = get_logger("opssentinel.webhook-receiver")

app = FastAPI(title="OpsSentinel Webhook Receiver", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness — the process is up."""
    return {"status": "ok"}


@app.get("/ready")
def ready() -> dict[str, str]:
    """Readiness — ready to accept and publish webhooks."""
    return {"status": "ready"}


async def _ingest(source: str, request: Request) -> JSONResponse:
    try:
        payload = await request.json()
    except Exception as exc:
        raise HTTPException(status_code=400, detail="invalid JSON body") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail="webhook body must be a JSON object")

    event = NORMALIZERS[source](payload)
    message_id = publish_alert(event)
    logger.info(
        "ingested webhook",
        extra={
            "source": source,
            "event_id": event.event_id,
            "service": event.service,
            "correlation_key": event.correlation_key,
            "message_id": message_id,
        },
    )
    return JSONResponse(
        status_code=202,
        content={"event_id": event.event_id, "message_id": message_id},
    )


@app.post("/webhook/pagerduty")
async def webhook_pagerduty(request: Request) -> JSONResponse:
    return await _ingest("pagerduty", request)


@app.post("/webhook/grafana")
async def webhook_grafana(request: Request) -> JSONResponse:
    return await _ingest("grafana", request)


@app.post("/webhook/elastic")
async def webhook_elastic(request: Request) -> JSONResponse:
    return await _ingest("elastic", request)
