# webhook-receiver — Input Layer (Cloud Run)

A minimal Python/FastAPI service that receives inbound monitoring webhooks, **deterministically
normalizes** each into the shared [`AlertEvent`](../../lib/events.py) contract, and **publishes**
to the `opssentinel-alerts` topic. It performs **no correlation and no LLM calls** — those belong
to the Agent Layer (Phase 3). The mock Alert Simulator is Member 3's (Phase 2); this service only
ingests and publishes.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/webhook/pagerduty` | Ingest a PagerDuty webhook |
| POST | `/webhook/grafana` | Ingest a Grafana alert webhook |
| POST | `/webhook/elastic` | Ingest an Elastic alert/APM webhook |
| GET | `/health` | Liveness |
| GET | `/ready` | Readiness |

Each ingest endpoint returns `202` with `{event_id, message_id}`.

## Run locally

Via the repo's docker-compose stack (recommended — wires the Pub/Sub emulator):

```bash
make dev   # webhook-receiver is published on host port 8000 (MCP servers use 8080/8081)
curl -X POST localhost:8000/webhook/grafana -H 'content-type: application/json' \
  -d '{"commonLabels":{"service":"payment-service","environment":"production","severity":"critical","k8s_namespace":"payments-ns"},"commonAnnotations":{"summary":"DB connection timeout"}}'
```

Or directly (with the venv active and `PUBSUB_EMULATOR_HOST` set):

```bash
uvicorn app.main:app --reload --port 8080   # run from the repo root so `lib` and `app` resolve
```

## Build the container (context = repo root, runs as non-root)

```bash
docker build -f services/webhook-receiver/Dockerfile -t webhook-receiver .
docker run --rm -p 8080:8080 -e OPSSENTINEL_USE_SECRET_MANAGER=false webhook-receiver
```

## Deploy

See [`infra/cloud-run`](../../infra/cloud-run) — the service is deployed **redundantly across
parallel regions** behind the L7 load balancer for fault tolerance.
