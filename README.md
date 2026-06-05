# OpsSentinel

> Agentic AI **intelligence + self-awareness layer** that sits above an enterprise's existing
> monitoring stack. It correlates cross-tool alerts, reasons over them with Gemini, retrieves
> historical fixes via Elastic (vector search), routes a human approval brief to Slack, executes
> approved remediations, and continuously evaluates its own decision accuracy via Arize Phoenix
> to adjust its autonomy at runtime.

This repository is built in **five sequential phases**, each owned by a team member. Phase
prompts live in [`PROMPTS/`](PROMPTS) and are run **in order** with Claude Code — paste one
phase file as a message, review the diff, run its acceptance checks, then continue.

> **Status:** All 5 phases implemented. Backend deterministic logic verified locally
> (ruff + **88 tests** green) and the **Next.js dashboard builds green** (`npm run build`, standalone).
> All services, MCP servers, the ADK agent, the Slack HITL gate, the dashboard, IaC, and the
> end-to-end storm validation are authored. Cloud-tool acceptance checks (Terraform/Docker/gcloud/
> Elasticsearch/Phoenix/Postgres/Gemini/Slack) run where those tools are installed — see the
> per-phase acceptance matrices below and [`docs/DEMO.md`](docs/DEMO.md) for the end-to-end walkthrough.

## Build phases

| Phase | Title | Owner | Runs after | Prompt |
|------:|-------|-------|-----------|--------|
| 0 | Project bootstrap | — | — | this README |
| 1 | Infrastructure & Orchestration Foundation ✅ | Cloud Infra & Backend Lead | — | [01](PROMPTS/01-phase1-infrastructure-foundation.md) |
| 2 | Data Sources, Memory & MCP Servers ✅ | Integrations, Memory & Observability | Phase 1 | [02](PROMPTS/02-phase2-data-sources-and-mcp.md) |
| 3 | Core ADK Agent (reasoning brain) ✅ | AI & Agent Orchestration | Phase 2 | [03](PROMPTS/03-phase3-adk-agent-core.md) |
| 4 | Frontend Dashboard & Security ✅ | Frontend & Security | scaffold anytime; finalize after P3 | [04](PROMPTS/04-phase4-frontend-and-security.md) |
| 5 | Workflow Integration & Validation ✅ | All members | Phases 1–4 | [05](PROMPTS/05-phase5-integration-and-validation.md) |

Conventions, shared contracts, and scope are defined in
[`PROMPTS/00-README-and-build-conventions.md`](PROMPTS/00-README-and-build-conventions.md).

## Getting started

1. Drop the source PDFs into [`docs/`](docs) (see [docs/README.md](docs/README.md)). They are git-ignored.
2. Open Claude Code in this folder.
3. Paste the **Phase 1** prompt as your message. Do not start a phase until the previous phase's
   Definition of Done is met (Phase 4 scaffolding is the one allowed early-start exception).

## Scope guardrails (MVP)

- **Real:** Pub/Sub, PostgreSQL, Gemini 2.0 Flash, Elastic vector search, Arize Phoenix, Slack
  approval, Next.js dashboard, Cloud Run.
- **Mocked:** inbound signals (Alert Simulator), remediation execution (mock infra state).
- **Deferred — do NOT build:** multi-agent collaboration, digital-twin simulation, predictive
  prevention, cost-aware remediation, cross-org federated learning, executive intelligence.

## Global build rules

1. Work in small, reviewable steps; pause at each phase's checkpoints.
2. Import cross-service contracts from the shared contracts package; never fork a schema locally.
3. Local-first: everything runs via `docker-compose` with emulators before any cloud deploy.
4. Secrets only via the shared secrets helper; never hardcode keys; never commit `.env`.
5. Every service is independently buildable and deployable to Cloud Run.
6. Enforce least-privilege IAM; no broad project Editor roles.
7. Each service gets a `README.md` explaining how to run and test it.

---

## Phase 1 — repo layout

```
opssentinel/
├── lib/                  # shared Python helpers (events, pubsub, db, secrets, logging)
├── services/
│   └── webhook-receiver/ # Input Layer → Queue (FastAPI, non-root container)
├── infra/                # Terraform IaC, one standalone root per component
│   ├── pubsub/  postgres/  secret-manager/  cloud-run/  networking/  iam/  scheduler/
├── migrations/           # Alembic schema + SLA seed
├── tests/                # pytest (events, secrets, logging, normalizers, db concurrency)
├── scripts/              # publish_test.py (queue round-trip), seed.py
├── docker-compose.yml    # local stack: Pub/Sub emulator + Postgres + webhook receiver
├── Makefile  ·  pyproject.toml  ·  alembic.ini  ·  .env.example
```

GCP project id: `opssentinel-mvp` · Region: `us-central1` · Python 3.12 (deploy) / 3.11+ (dev).

## Phase 1 — run locally (zero to a round-trip)

```bash
# 1. Python foundation (no Docker needed): lint + tests
python -m venv .venv
.venv/Scripts/python -m pip install pydantic python-dotenv ruff pytest   # Windows path
.venv/Scripts/python -m ruff check . && .venv/Scripts/python -m pytest

# 2. Full local stack (needs Docker)
cp .env.example .env
make dev                                   # Pub/Sub emulator + Postgres + webhook receiver
make migrate PY=.venv/Scripts/python       # apply schema + SLA seed
make publish-test PY=.venv/Scripts/python  # publish a sample alert and read it back
```

## Phase 1 — cloud deploy order

```
infra/secret-manager  →  infra/iam  →  infra/pubsub  →  infra/postgres
   →  (build+push image)  →  infra/cloud-run  →  infra/scheduler  →  infra/networking
```
Each component: `terraform -chdir=infra/<name> init && validate && apply -var project_id=...`.
After `infra/postgres`, feed its `database_url` output into the `database-url` secret, then
`make migrate`. `infra/networking` applies after the Phase-4 frontend exists. Per-component
details live in each `infra/<name>/README.md`.

## Phase 1 — acceptance matrix

| Check | How | Status here |
|---|---|---|
| Repo lints, imports clean; events validate sample | `ruff check` + `pytest` | ✅ verified (lint + format clean, tests pass) |
| Normalizers map each source → valid event | `pytest tests/test_normalizers.py` | ✅ verified |
| Pub/Sub round-trip + DLQ | `make publish-test` (emulator) / Terraform apply | ⏳ needs Docker / GCP |
| Container builds + runs non-root | `make build` | ⏳ needs Docker |
| Migrations apply; 4 tables + SLA rows; concurrent-update consistency | `make migrate` + `pytest` | ⏳ needs Postgres |
| Secrets resolved via accessor only; none hardcoded/logged | code + `lib/secrets` | ✅ by construction |
| IaC validates (pubsub/postgres/cloud-run/networking/iam/scheduler/secret-manager) | `terraform validate` | ⏳ needs Terraform |
| Least-privilege IAM, no Editor | `infra/iam` | ✅ by construction |

## Phase 2 — data sources, memory & MCP servers

New services: `mcp-elastic` (semantic memory — all-MiniLM-L6-v2 + KNN + full-text via **RRF**),
`mcp-arize` (self-evaluation — accuracy / calibration / novelty / outcome logging), and
`alert-simulator` (mock signals → `opssentinel-alerts`). The Phase-3 agent connects to both MCP
servers as an MCP client over SSE and applies [`lib/observability.py`](lib/observability.py) to
stream ADK spans to Phoenix.

```bash
make dev               # now also: Elasticsearch + Phoenix + mcp-elastic + mcp-arize + simulator
make migrate           # incident store + agent_outcomes (migration 0002)
make seed              # runbooks + logs + Arize history (DB-pool ~91%, degraded, novel)
make validate-phase2   # semantic robustness + logs + Arize signals + /health
make storm             # 50+ correlated signals (Phase-5 dedup input)
```

| Check | How | Status here |
|---|---|---|
| RRF fusion, result shaping | `pytest tests/test_retrieval_rrf.py` | ✅ verified |
| Arize metrics; DB-pool ≈91%, degraded, novel | `pytest tests/test_arize_metrics.py` | ✅ verified |
| Simulator: single + 50 correlated signals | `pytest tests/test_simulator_generator.py` | ✅ verified |
| Seed datasets (runbooks/logs/outcomes) | `pytest tests/test_seed_data.py` | ✅ verified |
| OpenInference helper imports cleanly | `pytest tests/test_observability_import.py` | ✅ verified |
| Indices (384-dim dense_vector + hybrid) exist | `make seed` (Elasticsearch) | ⏳ needs ES |
| `search_runbooks` semantic match via RRF | `make validate-phase2` | ⏳ needs ES + model |
| MCP servers serve `/sse` + `/health`, non-root | `make dev` / `terraform validate` | ⏳ needs Docker |
| Arize tools against seeded `agent_outcomes` | `make validate-phase2` | ⏳ needs Postgres |
| Per-secret IAM, no Editor; secrets via accessor | `infra/iam`, `infra/cloud-run/mcp.tf` | ✅ by construction |

## Phase 3 — the ADK agent (reasoning brain)

A single generalized orchestrator in [`services/agent/`](services/agent/). The **ADK graph** keeps
deterministic nodes off the LLM and invokes **Gemini 2.0 Flash** only for classification and the
RAG-bound recommendation; it correlates a storm into one incident, grounds its proposal in retrieved
runbooks, sets an `autonomy_tier` from Arize, applies a deterministic **Policy Engine**, and produces
an execution brief that awaits human approval before a **mocked** remediation.

```bash
make dev                        # now also runs the agent (alert + execution consumers)
make storm                      # 50+ correlated signals -> one incident -> awaiting_approval
make approve INCIDENT=<id>      # drive the deterministic execution path -> resolved
make reject  INCIDENT=<id>      # -> rejected
```

| Check | How | Status here |
|---|---|---|
| Storm folds into one incident (correlation) | `pytest tests/test_correlation.py` | ✅ verified |
| Policy gates (high-risk/schema/destructive/low-autonomy) + SLA escalation | `pytest tests/test_policy.py` | ✅ verified |
| Adaptive autonomy (high/moderate/low, degrade, novel) | `pytest tests/test_autonomy.py` | ✅ verified |
| Brief assembles all decision sections | `pytest tests/test_brief.py` | ✅ verified |
| Graph e2e → `awaiting_approval` (autonomy, risk, runbook, trace_id, branches) | `pytest tests/test_graph.py` | ✅ verified |
| Execution path: approve→resolved+closure+outcome, reject, idempotent | `pytest tests/test_executor.py` `tests/test_mock_infra.py` | ✅ verified |
| Gemini classification + RAG-bound recommendation | live run | ⏳ needs Gemini key |
| MCP tools callable over SSE via the agent | live run | ⏳ needs MCP servers |
| OpenInference trace per run in Phoenix; `trace_id` persisted | live run | ⏳ needs Phoenix |
| Agent Cloud Run deploy validates; least-privilege IAM (no Editor) | `terraform validate`; `infra/cloud-run/agent.tf`, `infra/iam` | ⏳ needs Terraform |

## Phase 4 — dashboard & security

A **Next.js 16 App Router** console in [`frontend/`](frontend/): server-rendered incident state +
reliability telemetry, **Google Identity Services** auth (server-side token verification, `sub`-keyed
httpOnly session, role separation), and a multi-stage **Alpine / standalone / non-root** image behind
the Phase-1 **Serverless NEG + L7 LB + Cloud CDN**. Read-only — it never mutates incident state.

```bash
cd frontend && npm install && npm run build   # standalone output for the Alpine image
make dev                                        # runs the dashboard (mock mode) at http://localhost:3000
```

| Check | How | Status here |
|---|---|---|
| App builds; standalone output enabled | `npm run build` → `.next/standalone/server.js` | ✅ verified |
| TypeScript types compile (read-model, auth, data) | `npm run build` (tsc) | ✅ verified |
| 4 views render server-side; loading/error boundaries | route segments + `error.tsx`/`loading.tsx` | ✅ builds (SSR routes are `ƒ`) |
| Google token verified server-side; `sub`-keyed httpOnly session; role separation | `lib/auth/*`, `app/api/auth` | ✅ by construction |
| Server-side guard blocks unauthenticated routes | `app/(dashboard)/layout.tsx` | ✅ by construction |
| Multi-stage Alpine, standalone, non-root image | `docker build ./frontend` | ⏳ needs Docker |
| Cloud Run + NEG/L7 LB/CDN attach; least-privilege IAM | `terraform validate`; `infra/cloud-run/frontend.tf`, `infra/networking`, `infra/iam/phase4.tf` | ⏳ needs Terraform |
| Live SSR reads real agent incidents + Phoenix deep-link | `OPSSENTINEL_DATA_MODE=live` | ⏳ needs Postgres + agent |

## Phase 5 — integration & validation

Connects the work-streams into one workflow: the **Slack HITL gate** ([`services/slack-bot/`](services/slack-bot/)) —
signature-verified, plain-text brief, Approve/Reject → `opssentinel-actions` → the Phase-3 executor;
the agent wired to `/notify` (`Notifier` on the graph); the **alert-storm validation**
([`scripts/run_storm.py`](scripts/run_storm.py), `make validate`); and the end-to-end demo
([`docs/DEMO.md`](docs/DEMO.md)). No new schemas/topics — only wiring.

```bash
make dev && make migrate && make seed
make validate                      # 50+ signal storm → reconcile → assert DLQ empty
make approve INCIDENT=<id>         # drive the executor without live Slack
```

| Exit Criterion / check | How | Status here |
|---|---|---|
| **EC1** Storm → one incident, zero alert loss | `pytest tests/test_storm_dedup.py`; `make validate` | ✅ verified (logic); ⏳ live reconcile |
| Slack signature verification (anti-spoof) | `pytest tests/test_slack_signing.py` | ✅ verified |
| Plain-text brief + Approve/Reject buttons (value=incident_id) | `pytest tests/test_slack_brief.py` | ✅ verified |
| Approve→publish actions; Reject→rejected; both audited | `pytest tests/test_slack_actions.py` | ✅ verified |
| **EC2** retrieve→self-eval→propose→Slack→Approve→execute | `tests/test_graph.py` + `test_executor.py` + `test_slack_*` | ✅ verified (logic) |
| Agent → slack-bot `/notify` wiring | `Notifier` in graph; `SlackNotifier` in runtime | ✅ by construction |
| **EC3** OpenInference traces + secured exception-free SSR frontend | Phoenix UI + `npm run build` | ⏳ needs Phoenix; ✅ build green |
| slack-bot deploy validates; least-privilege IAM (no Editor) | `terraform validate`; `infra/cloud-run/slack-bot.tf`, `infra/iam/phase5.tf` | ⏳ needs Terraform |

