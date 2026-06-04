# PHASE 1 — Infrastructure & Orchestration Foundation (Member 1)

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Owner:        Member 1 — Cloud Infrastructure & Backend Lead
Source of truth: "OpsSentinel: Master Architecture and Minimum Viable Product Specification"
Build phase:  Phase 1 of 5 — "Infrastructure and Orchestration Foundation"
How to use:   Open Claude Code in an empty project folder, place the spec PDF at
              ./docs/mvp.pdf, then paste THIS ENTIRE FILE as your first message.
```

> **Build discipline (read first).** Implement this phase **strictly as written in the
> OpsSentinel MVP specification**. Do **not** substitute technologies, re-architect, or add
> features beyond Member 1's infrastructure scope. Every component, technology choice, and
> design rationale below comes directly from the specification. If a detail is unspecified in
> the spec, choose the simplest implementation that satisfies the spec's stated intent, and
> note the assumption — do not expand scope.

---

## 1. Project context (from the specification)

OpsSentinel is structured across **five distinct processing layers**: the **Input Layer**
(telemetry ingress: alert simulator + live webhook receivers), the **Queue Layer** (Google
Cloud Pub/Sub — the system's "shock absorber"), the **Agent Layer** (Google ADK orchestrator +
Gemini 2.0 Flash + Policy Engine), the **Memory & Self-Evaluation Layer** (Elastic knowledge
base + PostgreSQL incident store + Slack approve/reject gate), and the **Observe Layer** (Arize
Phoenix tracing and the adaptive autonomy loop).

**Phase 1 builds the foundation that every other layer sits on.** Per the specification's
implementation milestones, Phase 1's core objective is to *deploy Google Cloud Run instances,
configure the Pub/Sub event bus, and provision Secret Manager for credential storage*. As the
Cloud Infrastructure & Backend Lead, Member 1 additionally provisions the **PostgreSQL incident
store** (Memory Layer persistence) and the **basic networking, including the Serverless Network
Endpoint Group (NEG)** — both explicitly within this role's domain. No backend, agent, or
frontend code can be securely tested until the event bus, incident store, and credential
management exist.

**What Phase 1 deliberately does NOT build** (these belong to later phases / other members and
must not be implemented here): the ADK agent and Gemini reasoning (Phase 3 / Member 2); the
Elastic and Arize MCP servers and vector indices (Phase 2 / Member 3); the Slack human-in-the-
loop bot (Phase 5 / Member 3); the Next.js dashboard application (Phase 4 / Member 4). Also out
of scope are all spec-deferred capabilities: **Multi-Agent Collaboration, Digital Twin
Simulation, and Predictive Prevention**.

---

## 2. Non-negotiable principles Phase 1 must honor (directly from the spec)

1. **Single cloud — Google Cloud Platform only.** The MVP operates exclusively within GCP to
   minimize networking complexity. Region: `us-central1` (placeholder; keep it single-region for
   data stores, with the multi-region note in Task 3).
2. **Core backend language is Python**, chosen for native compatibility with Google ADK and the
   AI instrumentation libraries the later phases require.
3. **CAP-theorem-aware layering:**
   - The **Pub/Sub ingestion path is tuned for Availability + Partition Tolerance (AP)** — it
     must remain highly available to accept *all* incoming alerts even if the database indexing
     them falls momentarily behind, guaranteeing **zero alert loss** and applying **back-pressure**
     to downstream processing.
   - The **PostgreSQL incident store and remediation path are tuned for Consistency + Partition
     Tolerance (CP)** — strong **ACID** consistency to prevent race conditions and duplicate
     remediation when incident state is written.
4. **99.99% availability target** (≈ 52 min 35.7 s downtime/year). For the persistent data store
   this is realized via an **Active-Passive (Master-Slave) replication topology** with
   continuous **heartbeats** and automatic failover (the passive standby assumes the primary's
   IP). For compute, fault tolerance increases by placing **redundant Cloud Run regions in
   parallel**.
5. **Throughput-first ingestion:** maximal throughput for alert ingestion while maintaining
   **sub-second latency** for message queuing during high-load alert storms.
6. **Secrets are never hardcoded or committed.** API keys for Gemini, Elasticsearch, and Arize
   are **injected dynamically at runtime via Google Cloud Secret Manager**, secure at rest and
   in transit.
7. **Least privilege everywhere.** Broad IAM roles such as the default project **Editor are
   explicitly prohibited**. Each service account gets a **custom role** scoped to specific,
   non-destructive actions.
8. **Inference cost is hard-capped per day** using **Google Cloud Scheduler** to enforce limits
   on API invocations during runaway alert storms.

---

## 3. Architectural interfaces Phase 1 must publish

Other layers connect to Phase 1 through these interfaces. Define them now as the project's
foundation so Phases 2–5 have stable contracts. (These implement the spec's "normalized event
queue" and "structured incident metadata / state tracking / relational data"; they do not add
new concepts.)

**Pub/Sub topology (the Queue Layer):**
- Ingest topic: `opssentinel-alerts` — the normalized event queue.
- Pull subscription for the Agent Layer: `opssentinel-alerts-sub`.
- Dead-letter topic: `opssentinel-alerts-dlq` (so a poison message can never drop an alert).

**Normalized alert event** (JSON published to `opssentinel-alerts`; the Input Layer normalizes
every inbound signal into this shape):
```json
{
  "event_id": "uuid",
  "source": "elastic | pagerduty | grafana | simulator",
  "received_at": "RFC3339 timestamp",
  "service": "payment-service",
  "environment": "production",
  "severity_hint": "P1 | P2 | P3 | P4 | unknown",
  "error_code": "ERR_DB_CONN_TIMEOUT",
  "http_status": 503,
  "deployment_id": "deploy-2026-01-01-0000",
  "correlation_key": "stable hash of {service + environment + infrastructure scope}",
  "message": "raw alert / log line text",
  "labels": { "k8s_namespace": "payments-ns", "pod": "payment-7c9", "region": "us-central1" },
  "raw": { "original": "untouched source payload" }
}
```
`correlation_key` exists so the Agent Layer can perform **time-windowed spatial correlation
based on service IDs before any LLM call** (the spec's defense against alert-correlation
failure). Phase 1 only needs to populate it deterministically; the correlation logic itself is
Phase 3.

**PostgreSQL incident store** — the primary store for structured incident metadata, state
tracking, and relational data. Phase 1 creates the schema; the Agent Layer populates it later.
Minimum tables:
- `incidents` — `incident_id (uuid pk)`, `status`, `severity`, `category`, `title`,
  `root_cause`, `confidence`, `risk_level`, `correlated_event_ids (jsonb)`,
  `recommended_action (jsonb)`, `historical_match_ids (jsonb)`, `autonomy_tier`, `trace_id`,
  `approver_subject`, `approval_status`, `approved_at`, `resolution_summary`,
  `created_at`, `updated_at`.
- `incident_events` — the raw correlated events linked to an incident.
- `audit_log` — append-only record of every state change / decision (for governance + traceability).
- `sla_policies` — per-severity response/resolution windows (the Policy Engine and Cloud
  Scheduler read these later).

Enumerations to enforce:
- `status`: `open | correlating | analyzing | awaiting_approval | approved | executing | resolved | rejected | escalated`
- `severity`: `P1 | P2 | P3 | P4`
- `risk_level`: `low | medium | high`
- `autonomy_tier`: `high | moderate | low`

**Secret Manager secrets** (created empty/placeholder now; populated as later phases need them):
`gemini-api-key`, `elastic-url`, `elastic-api-key`, `phoenix-collector-endpoint`,
`phoenix-api-key`, `slack-bot-token`, `slack-signing-secret`, `google-oauth-client-id`,
`database-url`.

---

## 4. Working method for Claude Code

Build in **small, reviewable increments**. After each numbered task: summarize exactly what you
created, show the command(s) to verify it, and **stop for review** before continuing. Prefer
**Infrastructure-as-Code (Terraform)**; if a step is faster/cleaner with idempotent `gcloud`
scripts, that is acceptable, but every resource must be reproducible from code in the repo.
Never print secret values. Keep the implementation faithful to Section 2.

---

## 5. Tasks

### Task 5.1 — Repository & Python backend foundation
Create the project skeleton:
```
opssentinel/
├── docs/                       # the MVP spec PDF
├── infra/                      # all Infrastructure-as-Code for Phase 1
│   ├── pubsub/
│   ├── postgres/
│   ├── secret-manager/
│   ├── cloud-run/
│   ├── networking/
│   ├── iam/
│   └── scheduler/
├── services/
│   └── webhook-receiver/       # the Phase-1 Cloud Run workload (Input → Queue)
├── lib/                        # shared Python helpers Phase 1 produces
│   ├── events.py               # the normalized event model + validation
│   ├── pubsub.py               # publisher + pull-subscriber helpers
│   ├── db.py                   # PostgreSQL connection pool + minimal data access
│   ├── secrets.py              # Secret Manager runtime accessor (+ local fallback)
│   └── logging.py              # structured JSON logging
├── migrations/                 # database schema migrations (Alembic)
├── .env.example
├── Makefile
├── docker-compose.yml          # local dev/test harness (see Section 6)
├── pyproject.toml              # Python 3.12, ruff, pytest
├── .gitignore                  # ignore .env, venvs, build artifacts
└── README.md
```
Initialize git, configure Python 3.12 tooling (ruff + pytest), and write a `README.md` that
states the GCP project id / region placeholders and the deploy order. **Acceptance:** repo lints
and imports cleanly; `lib/events.py` validates the normalized event sample from Section 3.

### Task 5.2 — Queue Layer: Google Cloud Pub/Sub (AP-tuned)
In `infra/pubsub/`, provision the topic `opssentinel-alerts`, the subscription
`opssentinel-alerts-sub`, and the dead-letter topic `opssentinel-alerts-dlq`. Configure the
subscription for **back-pressure and zero alert loss**: a sensible ack-deadline, a retry policy
with exponential backoff, **dead-letter forwarding** to the DLQ after N delivery attempts, and
**flow-control / message-ordering** settings appropriate to a sustainable, controlled consume
rate. In `lib/pubsub.py`, implement `publish_alert(event)` (validates against the normalized
event model, then publishes) and a pull-subscriber helper with bounded concurrency and graceful
shutdown. **Acceptance:** publishing a normalized event and pulling it back succeeds; an
intentionally failing message lands in the DLQ.

### Task 5.3 — Compute: Google Cloud Run + the webhook receiver workload
The spec requires deploying Cloud Run instances; the natural Phase-1 workload is the **Input
Layer's webhook receiver** that feeds the Queue Layer. In `services/webhook-receiver/`, build a
**minimal Python HTTP service** that:
- exposes endpoints to receive inbound monitoring webhooks (e.g. `/webhook/pagerduty`,
  `/webhook/grafana`, `/webhook/elastic`),
- **normalizes** each inbound payload into the Section-3 event shape (deterministic mapping; no
  LLM), deriving `correlation_key` from `service + environment + infrastructure scope`,
- publishes the normalized event to `opssentinel-alerts` via `lib/pubsub.py`,
- exposes `/health` and `/ready`.
Containerize it with a **multi-stage Python Dockerfile** that runs as a **non-root** user. In
`infra/cloud-run/`, write the deploy configuration/scripts (Artifact Registry + Cloud Run
service), wiring secrets from Secret Manager via the runtime accessor, and **document deploying
the service redundantly across parallel regions** for fault tolerance (per the spec's parallel-
availability principle). **Acceptance:** the container builds and runs locally as non-root;
hitting a webhook endpoint publishes a valid normalized event to the topic; the Cloud Run deploy
config validates / dry-runs cleanly.
*(Signal correlation and the mock Alert Simulator are explicitly NOT part of this service — they
belong to the Agent Layer and Member 3 respectively. This service only ingests and publishes.)*

### Task 5.4 — Incident Store: PostgreSQL (CP-tuned, Active-Passive, ACID)
In `infra/postgres/`, provision **Cloud SQL for PostgreSQL** configured for **high availability
(regional)** — GCP's managed realization of the spec's **Active-Passive (Master-Slave)**
topology: a synchronously-replicated standby in a second zone, continuous heartbeats, and
automatic failover behind a shared IP, targeting **99.99% availability**. Document this mapping
and the CP rationale in `infra/postgres/README.md`. Author the schema in `migrations/` (Alembic)
creating `incidents`, `incident_events`, `audit_log`, and `sla_policies` exactly per Section 3
(correct enums, jsonb columns, and indexes on `status`, `severity`, `correlation_key`,
`created_at`). Seed `sla_policies` with the spec's governance defaults (e.g. P1 fast-response,
P2 slower). In `lib/db.py`, implement an ACID-safe connection pool and a minimal data-access
layer (`upsert_incident`, `get_incident`, `add_event`, `append_audit`) that the Agent Layer will
import. **Acceptance:** migrations apply; the four tables and SLA seed rows exist; a concurrent
double-update test demonstrates consistent state (no duplicate/lost update).

### Task 5.5 — Credentials: Google Cloud Secret Manager
In `infra/secret-manager/`, create every secret named in Section 3 (placeholder values, with a
documented procedure to populate real values). In `lib/secrets.py`, implement a single
`get_secret(name)` accessor that reads from **Secret Manager at runtime** when running on GCP and
falls back to environment variables / `.env` for local development — so **no key is ever
hardcoded or committed**. Write `.env.example` listing every variable with safe placeholders.
**Acceptance:** services resolve credentials through the accessor only; secret values never
appear in logs or source.

### Task 5.6 — Basic networking: Serverless NEG + Layer-7 load balancer (+ Cloud CDN config)
In `infra/networking/`, define the **Serverless Network Endpoint Group (NEG)** that securely
connects an **external Layer-7 (HTTP/S) load balancer** to a Cloud Run service, with L7 routing
based on application-layer info (HTTP headers/cookies), plus the **Cloud CDN (Pull strategy +
TTL headers)** configuration for static-asset delivery. Phase 1 stands up the NEG + LB
foundation and the CDN config; the **frontend** is attached to it in Phase 4 (Member 4, assisted
by Member 1). Document the apply order. **Acceptance:** the networking IaC validates / dry-runs
cleanly and is documented as ready for the Phase-4 frontend attach.

### Task 5.7 — Security: least-privilege IAM
In `infra/iam/`, create a **dedicated service account per service** with **custom roles** scoped
to the minimum permissions each needs (e.g. the webhook receiver: Pub/Sub publish only; the
future agent: Pub/Sub subscribe + Cloud SQL client + Secret Manager accessor). **Explicitly
forbid** the default project Editor role anywhere. Document the service-account → role mapping in
`infra/iam/README.md`. **Acceptance:** no resource uses Editor; each SA's permissions are
enumerated and minimal.

### Task 5.8 — Cost governance: Google Cloud Scheduler inference cap
In `infra/scheduler/`, provision a **Cloud Scheduler** job that enforces a **hard daily cap on
LLM/API invocations** to protect against runaway cost during alert storms (per the spec's
inference-cost constraint and risk mitigation). Scaffold the job and the quota-enforcement target
now (the Agent Layer wires its inference calls to respect this cap in Phase 3). Also scaffold the
SLA-check schedule the Policy Engine will use later. **Acceptance:** the Scheduler IaC validates;
the cap mechanism and its intended hook point are documented.

### Task 5.9 — Operational baseline + glue
Add `lib/logging.py` (structured JSON logs) and a consistent `/health` + `/ready` convention for
services. Write the `Makefile` targets (`dev`, `down`, `migrate`, `seed`, `publish-test`, `fmt`,
`lint`, `test`) and complete the root `README.md` "how to provision and how to run locally"
guide. **Acceptance:** `make lint` and `make test` pass; the README walks a new teammate from
zero to a running local stack and to the GCP deploy.

---

## 6. Local development & verification harness (supporting, mirrors the GCP resources)

So Phase 1 can be built and exercised without waiting on live cloud resources — and so Phases 2–5
have something to develop against — provide a `docker-compose.yml` that runs the **Pub/Sub
emulator** and a **local PostgreSQL** container that mirror the GCP topology. This is a
development/test convenience only; it does not replace or alter the GCP IaC, which remains the
authoritative deployment target. `make dev` brings the harness up; `make migrate` applies the
schema; `make publish-test` publishes a sample normalized event and reads it back.

---

## 7. Definition of Done — Phase 1 is complete when

- The repo, Python tooling, and `lib/` helpers exist and pass lint + tests.
- **Pub/Sub**: `opssentinel-alerts`, `opssentinel-alerts-sub`, and `opssentinel-alerts-dlq` are
  provisioned (AP-tuned: retries, dead-letter, flow control); publish→pull round-trips; a poison
  message reaches the DLQ.
- **Cloud Run + webhook receiver**: the non-root container builds; a webhook call publishes a
  valid normalized event; the deploy config validates and documents multi-region redundancy.
- **PostgreSQL**: Cloud SQL HA (regional / Active-Passive) is defined; migrations create the four
  tables with correct enums/indexes and SLA seed rows; concurrent-update consistency holds.
- **Secret Manager**: all secrets exist; every credential is resolved via the runtime accessor;
  nothing is hardcoded or logged.
- **Networking**: Serverless NEG + L7 LB + Cloud CDN config validate and are documented as ready
  for the Phase-4 frontend attach.
- **IAM**: per-service custom roles, least privilege, no Editor anywhere.
- **Cloud Scheduler**: daily inference-cap job (and SLA-check schedule) scaffolded and documented.
- The local harness comes up via `make dev` and round-trips an event end to end.

---

## 8. Handoff to Phase 2 (and beyond)

Phase 1 hands the team: a running **Queue Layer** with a stable normalized event contract and DLQ;
a **PostgreSQL incident store** with schema + data-access layer; **Secret Manager** with a runtime
accessor; **Cloud Run** deploy scaffolding and the webhook-receiver ingress; the **networking**
foundation (NEG/LB/CDN) ready for the frontend; **least-privilege IAM**; the **Cloud Scheduler**
cost-cap mechanism; and a local harness for development. Phase 2 (Member 3 — Elastic & Arize MCP
servers) and Phase 3 (Member 2 — the ADK agent) build directly on these.

---

## 9. Guardrails — do NOT build in Phase 1

- No ADK agent, Gemini reasoning, Policy Engine logic, or signal-correlation algorithm (Phase 3).
- No Elastic or Arize MCP servers, embeddings, or vector indices (Phase 2).
- No Alert Simulator (Phase 2 / Member 3) — the webhook receiver ingests only.
- No Slack bot or approval webhook (Phase 5).
- No Next.js dashboard application (Phase 4) — networking foundation only.
- None of the spec-deferred features: Multi-Agent Collaboration, Digital Twin Simulation,
  Predictive Prevention.

Keep every choice faithful to the OpsSentinel MVP specification — no technology substitutions and
no scope beyond Member 1's infrastructure responsibilities.
