# OpsSentinel — Claude Code Build Prompts (Master Index)

This folder contains **one master prompt per build phase**. Each phase corresponds to the
team member who owns it and follows the execution order defined in the project workflow.
The phases are designed to be run **in order**, each one assuming the previous phase's
deliverables exist.

> OpsSentinel is the agentic AI **intelligence + self-awareness layer** that sits above an
> enterprise's existing monitoring stack. It correlates cross-tool alerts, reasons over them
> with Gemini, retrieves historical fixes via Elastic (vector search), routes a human approval
> brief to Slack, executes approved remediations, and continuously evaluates its own decision
> accuracy via Arize Phoenix to adjust its autonomy at runtime.

---

## How to use these prompts with Claude Code

1. Create an empty folder for the repo and `cd` into it.
2. Put the two source documents in `./docs/` (`docs/architecture-spec.pdf`,
   `docs/project-document.pdf`) so Claude Code can reference them when it wants more detail.
3. Open Claude Code in that folder and **paste the entire contents of one phase file** as
   your message. Run phases in numeric order.
4. Each prompt tells Claude Code to work **incrementally** and pause at checkpoints — review
   the diff, run the stated acceptance checks, then continue.
5. Do not start a phase until the previous phase's **Definition of Done** is met (Phase 4 is
   the one allowed exception — it may be scaffolded in parallel; see below).

The prompts are self-contained: every contract Claude Code needs is restated below and in each
file, so it will work even if the PDFs are not present. The PDFs add depth, not correctness.

---

## Team → Phase ownership

| Phase | Title | Owner | Runs after | Can overlap with |
|------:|-------|-------|-----------|------------------|
| 1 | Infrastructure & Orchestration Foundation | Member 1 — Cloud Infra & Backend Lead | — | Phase 4 scaffolding (once repo skeleton exists) |
| 2 | Data Sources, Memory & MCP Servers | Member 3 — Integrations, Memory & Observability | Phase 1 | Phase 4 scaffolding |
| 3 | Core ADK Agent (the reasoning brain) | Member 2 — AI & Agent Orchestration | Phase 2 | Phase 4 build |
| 4 | Frontend Dashboard & Security | Member 4 — Frontend & Security | scaffolding anytime; finalize after Phase 3 | Phase 3 |
| 5 | Workflow Integration & Validation | All members | Phases 1–4 | — |

**Parallelization note:** Member 4 can begin Phase 4 (Next.js scaffolding + Google Identity
Services wiring) as soon as the Phase 1 repo skeleton and the `shared/` contracts exist. It only
needs the live backend API for final integration, which lands in Phase 5.

---

## Recommended monorepo layout (created in Phase 1, used by everyone)

```
opssentinel/
├── docs/                       # the two source PDFs + any design notes
├── shared/                     # SINGLE SOURCE OF TRUTH for cross-service contracts
│   ├── opssentinel_shared/     # importable Python package
│   │   ├── schemas.py          # Pydantic models: AlertEvent, Incident, RemediationPlan...
│   │   ├── constants.py        # topic names, secret names, table names, MCP endpoints, tiers
│   │   └── secrets.py          # Secret Manager fetch helper (with local .env fallback)
│   └── json-schema/            # JSON Schema mirrors of the same contracts (for TS/frontend)
├── infra/                      # Member 1 — IaC + deploy scripts (Terraform or gcloud scripts)
│   ├── pubsub/  postgres/  secret-manager/  cloud-run/  networking/  iam/
├── services/
│   ├── agent/                  # Member 2 — Python ADK agent (Pub/Sub consumer)
│   ├── mcp-elastic/            # Member 3 — Elastic MCP server (SSE)
│   ├── mcp-arize/              # Member 3 — Arize/Phoenix MCP server (SSE)
│   ├── slack-bot/              # Member 3 — Slack HITL (notify + interactivity webhook)
│   └── alert-simulator/        # Member 3 — mock Elastic/PagerDuty signal generator
├── frontend/                   # Member 4 — Next.js (App Router) dashboard
├── scripts/                    # seed data, dev helpers, the alert-storm test
├── docker-compose.yml          # local dev stack (emulators + all services)
├── .env.example
├── Makefile
└── README.md
```

All services **import contracts from `shared/`** rather than redefining them. Changing a
contract means changing it in `shared/` and updating all consumers.

---

## SHARED CONTRACTS (read this before any phase)

These are the agreed interfaces between the four work-streams. Every phase prompt references
this section. Keep names exact.

### Project + environment
- GCP project id (placeholder): `opssentinel-mvp`  · Region: `us-central1`
- Language/runtimes: Python 3.12 (backend, MCP servers, simulator), Node 20 + Next.js (frontend)
- MVP is **single cloud (GCP only)**, incident focus is **Kubernetes-class failures**, **English only**.

### Secret Manager secrets → environment variables
| Secret name | Env var | Used by |
|---|---|---|
| `gemini-api-key` | `GEMINI_API_KEY` | agent |
| `elastic-url` | `ELASTIC_URL` | mcp-elastic |
| `elastic-api-key` | `ELASTIC_API_KEY` | mcp-elastic |
| `phoenix-collector-endpoint` | `PHOENIX_COLLECTOR_ENDPOINT` | agent, mcp-arize |
| `phoenix-api-key` | `PHOENIX_API_KEY` | agent, mcp-arize |
| `slack-bot-token` | `SLACK_BOT_TOKEN` | slack-bot |
| `slack-signing-secret` | `SLACK_SIGNING_SECRET` | slack-bot |
| `google-oauth-client-id` | `GOOGLE_OAUTH_CLIENT_ID` | frontend, backend (token verify) |
| `database-url` | `DATABASE_URL` | agent, backend API |

Secrets are **never** committed. They are injected at runtime via Secret Manager in cloud, and
read from `.env` locally. `shared/opssentinel_shared/secrets.py` provides one helper for both.

### Queue Layer — Pub/Sub (tuned for Availability + Partition tolerance)
- Ingest topic: `opssentinel-alerts`
- Agent pull subscription: `opssentinel-alerts-agent-sub`
- Dead-letter topic: `opssentinel-alerts-dlq`
- Approved-action topic (outbound execution): `opssentinel-actions`
- Guarantee: **zero alert loss** under storm; back-pressure via the subscription; the agent
  consumes at a controlled, sustainable rate.

### Normalized alert event (JSON published to `opssentinel-alerts`)
```json
{
  "event_id": "uuid",
  "source": "elastic | pagerduty | grafana | servicenow | simulator",
  "received_at": "2026-01-01T02:47:00Z",
  "service": "payment-service",
  "environment": "production",
  "severity_hint": "P1 | P2 | P3 | P4 | unknown",
  "error_code": "ERR_DB_CONN_TIMEOUT",
  "http_status": 503,
  "deployment_id": "deploy-2026-01-01-0000",
  "correlation_key": "stable hash of {service + environment + infra scope}",
  "message": "raw alert / log line text",
  "labels": { "k8s_namespace": "payments-ns", "pod": "payment-7c9", "region": "us-central1" },
  "raw": { "original": "untouched source payload" }
}
```
`correlation_key` is what the agent uses for **time-windowed spatial correlation** to fold an
alert storm into one incident before any LLM call.

### Incident Store — PostgreSQL (tuned for Consistency + Partition tolerance, ACID, HA via Active-Passive)
Core tables (full DDL is produced in Phase 1):
- `incidents` — `incident_id (uuid pk)`, `status`, `severity`, `category`, `title`,
  `root_cause`, `confidence`, `blast_radius`, `correlated_event_ids (jsonb)`,
  `recommended_action (jsonb)`, `risk_level`, `historical_match_ids (jsonb)`,
  `autonomy_tier`, `trace_id`, `approver_subject`, `approval_status`, `approved_at`,
  `resolution_summary`, `created_at`, `updated_at`
- `incident_events` — raw correlated events linked to an incident
- `audit_log` — every AI decision and every human action (append-only, for compliance)
- `sla_policies` — per-severity response/resolution windows

Enums:
- `status`: `open | correlating | analyzing | awaiting_approval | approved | executing | resolved | rejected | escalated`
- `severity`: `P1 | P2 | P3 | P4`
- `risk_level`: `low | medium | high`
- `autonomy_tier`: `high | moderate | low`

### MCP servers (client–host–server; transport = Server-Sent Events / SSE)
The agent is the **MCP Client** (ADK `McpToolset`). Servers run as independent containers.

**Elastic MCP** — `http://mcp-elastic:8080/sse` (local) / Cloud Run URL (prod). Tools:
- `search_runbooks(query: str, top_k: int = 3)` → top-k semantically similar past incidents +
  runbooks with resolution steps. Uses `all-MiniLM-L6-v2` (384-dim) embeddings, **KNN + full-text
  combined via Reciprocal Rank Fusion (RRF)**.
- `fetch_recent_logs(service: str, minutes: int = 30)` → recent log/APM lines for context.
- `write_closure_summary(incident_id: str, summary: str, tags: list[str])` → write the resolved
  incident back into the knowledge base (institutional memory).

**Arize / Phoenix MCP** — `http://mcp-arize:8081/sse` (local) / Cloud Run URL (prod). Tools:
- `get_category_accuracy(category: str, window: int = 30)` → recent accuracy % for that category.
- `get_calibration(category: str)` → calibration error (stated confidence vs empirical accuracy).
- `is_novel_category(category: str)` → true if the agent has little/no history for this type.
- `log_outcome(trace_id: str, incident_id: str, approved: bool, successful: bool)` → record result.

### Runtime adaptive autonomy (how the agent reads Arize results)
- **≥ 90%** accuracy **and** well-calibrated → `autonomy_tier = high` (assertive recommendation).
- **70–89%** → `autonomy_tier = moderate` (proceed, lower stated confidence, add a caution note).
- **< 70%**, OR `is_novel_category == true`, OR intent-classifier confidence **< 70%** →
  `autonomy_tier = low` (**flag for human review, do not propose autonomous execution**).

### Policy Engine (deterministic, runs alongside/over the LLM — hard rules win)
- `production` + service in {payment, checkout, auth} → minimum severity **P1**.
- `production` (any) → minimum severity **P2**.
- Database **schema change** → require DBA approval regardless of confidence.
- Any action with `risk_level = high` → require explicit human approval.
- **SLA**: P1 respond ≤ 15 min, P2 ≤ 60 min. Cloud Scheduler runs an SLA check every 15 min and
  escalates overdue items.
- **Inference cost cap**: a hard daily quota on LLM calls, enforced via Cloud Scheduler, to
  survive runaway alert storms.

### Slack contract (human-in-the-loop gate)
- The agent calls the slack-bot's internal endpoint `POST /notify` with an incident id + brief.
- The brief (Block Kit) shows: title, root cause, correlated evidence, confidence, historical
  match, proposed fix steps, risk level, and the autonomy/caution note.
- Buttons: **Approve** (`action_id = approve_incident`, `value = incident_id`),
  **Reject** (`action_id = reject_incident`, `value = incident_id`),
  **See full reasoning** (link to the dashboard incident page).
- Slack → `POST /slack/interactions` on slack-bot (signature-verified). On approve, slack-bot
  publishes to `opssentinel-actions` (or calls the backend execute endpoint), updates incident
  `status`, and appends to `audit_log`.

### Frontend ↔ backend API (read model + actions)
Backend exposes:
- `GET /api/incidents?status=&severity=`
- `GET /api/incidents/:id` (detail + audit timeline + Arize trace link)
- `GET /api/metrics` (MTTD, MTTR, triage accuracy, correlation precision, approval rate,
  calibration error, autonomy coverage)
- `GET /api/health`

Auth: the browser sends a Google **ID token** as `Authorization: Bearer <id_token>`. The backend
**cryptographically verifies** it with the official Google client library and uses the `sub`
claim as the immutable user key. The Next.js app fetches incident state **server-side** so the
page renders without client-side exceptions.

---

## What is REAL vs MOCKED for the MVP
- **Real:** Pub/Sub, PostgreSQL, Gemini 2.0 Flash reasoning, Elastic vector search, Arize Phoenix
  tracing + self-evaluation, Slack approval, the Next.js dashboard, Cloud Run deployment.
- **Mocked/simulated:** inbound signals come from the **Alert Simulator** (mock Elastic/PagerDuty)
  and/or test webhooks; the **remediation execution** updates a *mocked* infrastructure state
  (e.g., a "ServiceNow ticket" + a fake "restart pool" action) rather than touching a real cluster.
- **Deferred (do NOT build):** multi-agent collaboration, digital-twin simulation, predictive
  prevention, cost-aware remediation, cross-org federated learning, executive intelligence.

---

## Success thresholds the build is aiming at (validated in Phase 5)
- MTTD < 30s · MTTR < 10 min (known patterns) · triage accuracy > 90% · 85% reduction in
  duplicate P1/P2 during a storm · > 80% first-pass approval · Arize calibration variance < 5% ·
  architecture target 99.99% availability.

## Global build rules (restated in every phase)
1. Work in **small, reviewable steps**; pause at the checkpoints the prompt defines.
2. Import all cross-service contracts from `shared/`; never fork a schema locally.
3. **Local-first**: everything must run via `docker-compose` with emulators before cloud deploy.
4. Secrets only via the `shared` secrets helper; never hardcode keys; never commit `.env`.
5. Keep every service independently buildable and deployable to Cloud Run.
6. Enforce **least-privilege IAM**; no broad project Editor roles.
7. Add a `README.md` to each service explaining how to run and test it.
