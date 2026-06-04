# OpsSentinel

> Agentic AI **intelligence + self-awareness layer** that sits above an enterprise's existing
> monitoring stack. It correlates cross-tool alerts, reasons over them with Gemini, retrieves
> historical fixes via Elastic (vector search), routes a human approval brief to Slack, executes
> approved remediations, and continuously evaluates its own decision accuracy via Arize Phoenix
> to adjust its autonomy at runtime.

This repository is built in **five sequential phases**, each owned by a team member. Phase
prompts live in [`PROMPTS/`](PROMPTS) and are run **in order** with Claude Code — paste one
phase file as a message, review the diff, run its acceptance checks, then continue.

> **Status:** Phases 1–2 implemented. All pure logic verified locally (ruff + 37 tests green);
> IaC, services, MCP servers, migrations, seeds, and the local harness authored. Cloud-tool
> acceptance checks (Terraform/Docker/gcloud/Elasticsearch/Phoenix/Postgres) run where those tools
> are installed (see the acceptance matrices at the bottom of this file). Phase 3 not started.

## Build phases

| Phase | Title | Owner | Runs after | Prompt |
|------:|-------|-------|-----------|--------|
| 0 | Project bootstrap | — | — | this README |
| 1 | Infrastructure & Orchestration Foundation ✅ | Cloud Infra & Backend Lead | — | [01](PROMPTS/01-phase1-infrastructure-foundation.md) |
| 2 | Data Sources, Memory & MCP Servers ✅ | Integrations, Memory & Observability | Phase 1 | [02](PROMPTS/02-phase2-data-sources-and-mcp.md) |
| 3 | Core ADK Agent (reasoning brain) | AI & Agent Orchestration | Phase 2 | [03](PROMPTS/03-phase3-adk-agent-core.md) |
| 4 | Frontend Dashboard & Security | Frontend & Security | scaffold anytime; finalize after P3 | [04](PROMPTS/04-phase4-frontend-and-security.md) |
| 5 | Workflow Integration & Validation | All members | Phases 1–4 | [05](PROMPTS/05-phase5-integration-and-validation.md) |

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

