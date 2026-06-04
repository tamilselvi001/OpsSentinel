# PHASE 2 — Data Sources & MCP Server Deployment (Member 3)

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Owner:        Member 3 — Integrations, Memory & Observability Engineer
Source of truth: "OpsSentinel: Master Architecture and Minimum Viable Product Specification"
Build phase:  Phase 2 of 5 — "Data Sources and MCP Server Deployment"
Runs after:   Phase 1 (needs the Pub/Sub event bus + normalized event contract, the PostgreSQL
              incident store, Secret Manager + the runtime secrets accessor, the Cloud Run
              deploy scaffolding, the least-privilege IAM pattern, and the local dev harness).
How to use:   Open Claude Code at the Phase-1 repo root, ensure ./docs/mvp.pdf is present,
              then paste THIS ENTIRE FILE as your message.
```

> **Build discipline (read first).** Implement this phase **strictly as written in the
> OpsSentinel MVP specification**. Do **not** substitute technologies, re-architect, or add
> features beyond Member 3's data/memory/observability scope. Every component, technology choice,
> and design rationale below comes directly from the specification. If a detail is unspecified,
> choose the simplest implementation that satisfies the spec's stated intent, note the
> assumption, and do not expand scope.

---

## 1. Project context (from the specification)

OpsSentinel is structured across **five processing layers**: Input, Queue, **Agent**, **Memory &
Self-Evaluation**, and **Observe**. Phase 1 built the foundation (Queue Layer, incident-store
persistence, credentials, compute, networking). **Phase 2 builds the agent's data sources** — the
two halves of the agent's "mind" that every reasoning step depends on:

- the **Memory & Self-Evaluation Layer's** semantic memory — the **Elastic** knowledge base
  (vector search over historical runbooks), exposed to the agent through the **Elastic MCP
  server**; and
- the **Observe Layer** — **Arize Phoenix** tracing, LLM-as-a-judge evaluation, and the **adaptive
  autonomy loop**, exposed through the **Arize Phoenix MCP server**.

Per the specification's implementation milestones, Phase 2's core objective is to *containerize
and deploy the Elastic and Arize MCP servers, configure vector indices, and test semantic search
using synthetic telemetry*. As the Integrations, Memory & Observability Engineer, Member 3 also
builds the **Alert Simulator** (mock Elastic/PagerDuty signals) — both because it is explicitly in
this role's domain and because it is how the **synthetic telemetry** required to test this phase is
produced. The Agent Layer (Phase 3) will immediately connect to both MCP servers the moment it
exists, so the tool contracts defined here are a hard interface.

**What Phase 2 deliberately does NOT build** (belongs to later phases / other members): the ADK
agent, the Gemini reasoning loop, the Policy Engine, and the signal-correlation algorithm (Phase 3
/ Member 2); the **Slack human-in-the-loop bot and its approval webhook** (Phase 5 / Member 3 — the
spec places "Connect the Slack integration for approval webhooks" in Phase 5); the full **alert-
storm validation run** (Phase 5); and the Next.js dashboard (Phase 4 / Member 4). Also out of
scope: the spec-deferred capabilities — **Multi-Agent Collaboration, Digital Twin Simulation,
Predictive Prevention**.

---

## 2. Non-negotiable principles Phase 2 must honor (directly from the spec)

1. **Model Context Protocol, client–host–server, over SSE.** External tools are reached through
   **MCP**, which "operates on a client-host-server architecture." The agent (built later) is the
   **MCP Client** via ADK's **`McpToolset`**; the servers you build here run as **independent
   Docker containers** and the connection is established via **Server-Sent Events (SSE)** —
   real-time, persistent HTTP streaming, chosen over legacy stdio for better error handling and
   deployment flexibility. **No brittle, custom API wrappers.**
2. **Elastic is dual-purpose:** the **high-throughput intake layer for raw logs** *and* the
   **long-term semantic memory repository**.
3. **Embeddings use `all-MiniLM-L6-v2`** — a **384-dimensional** space with **~100 ms encoding
   times**, the spec's chosen intersection of latency and precision for operational logs (and the
   mitigation for the **context-retrieval-latency** risk against the 30-second MTTD target). Do
   not substitute a larger/slower model.
4. **Hybrid retrieval:** similarity via **K-Nearest Neighbors (KNN)** over dense vectors,
   **combined with traditional full-text relevance via Reciprocal Rank Fusion (RRF)** — so a query
   phrased "connection pool exhausted" still retrieves a historical "database connection limit
   reached" runbook.
5. **RAG grounding:** the knowledge base exists so the agent "cannot act outside the bounds of
   retrieved historical runbooks." Retrieval quality is therefore a safety control, not a nicety.
6. **Arize Phoenix is an active component of the cognitive loop, not a passive dashboard.** The
   ADK app is instrumented with the **OpenTelemetry-compatible `openinference-instrumentation-
   google-adk`** package so that **every tool call, context retrieval, and generated token is a
   discrete trace span** in **Phoenix**. The Observe Layer also runs **LLM-as-a-judge** evaluations
   and feeds the **adaptive autonomy loop**: when accuracy for a category **degrades**, the agent
   **lowers its autonomy tier** and refuses to act without human intervention. (Calibration target:
   the variance between stated confidence and empirical accuracy must stay **below a 5% margin**.)
7. **Single cloud (GCP only); core language Python; secrets only via Secret Manager** (the keys
   for Elasticsearch and Arize are injected at runtime, never hardcoded or committed); **least
   privilege** for the service accounts running these containers (no default project Editor).
8. The MCP servers are **hosted in independent Docker containers** — containerize each (multi-
   stage, non-root) and deploy on **Cloud Run** using the Phase-1 scaffolding.

---

## 3. Interfaces Phase 2 must publish

The Agent Layer connects to Phase 2 through these. Define them now as stable contracts. (They
implement the spec's described MCP tools; they introduce no new concepts.)

**Elastic MCP server** — SSE endpoint `http://mcp-elastic:8080/sse` (local) / Cloud Run URL (prod).
Tools (names/signatures fixed):
- `search_runbooks(query: str, top_k: int = 3)` → encode `query` with `all-MiniLM-L6-v2`, run
  **KNN** over the dense-vector field **and** a full-text query, **fuse with RRF**, and return the
  top-k historical incidents/runbooks as
  `{id, title, root_cause, resolution_steps, commands, who_handled, time_to_fix, similarity_score}`.
  *(Implements "the closest historical incident match via vector search.")*
- `fetch_recent_logs(service: str, minutes: int = 30)` → return the recent application/APM log
  lines for that service. *(Implements "retrieve the last thirty minutes of application logs.")*
- `write_closure_summary(incident_id: str, summary: str, tags: list[str])` → embed and index the
  resolved incident as a new knowledge document so it is immediately retrievable.
  *(Implements "permanently log the successful outcome into the Elastic knowledge base.")*

**Arize Phoenix MCP server** — SSE endpoint `http://mcp-arize:8081/sse` (local) / Cloud Run URL.
Tools:
- `get_category_accuracy(category: str, window: int = 30)` → the recent LLM-as-a-judge accuracy for
  that incident category. *(Implements "query its recent historical accuracy for 'Database
  Connection Pool' incidents," e.g. 91%.)*
- `get_calibration(category: str)` → the variance between the agent's stated confidence and its
  empirical accuracy (the <5% calibration metric).
- `is_novel_category(category: str)` → whether the category falls outside the agent's historical
  experience (drift / unseen-type signal).
- `log_outcome(trace_id: str, incident_id: str, approved: bool, successful: bool)` → record the
  result into the trace history. *(Implements "log ... into the Arize trace history.")*

These tools **return the raw observability metrics only.** The mapping from metrics → autonomy
tier (and the "refuse to act when degraded" behavior) is the Agent Layer's loop in Phase 3; Phase 2
just exposes faithful data. The `autonomy_tier` enum (`high | moderate | low`) and the incident
schema were published by Phase 1.

**Elasticsearch indices** (created in this phase):
- `opssentinel-knowledge` — hybrid-search index: a `dense_vector` field (`dims: 384`, cosine
  similarity) plus analyzed text fields (`title`, `summary`, `root_cause`, `resolution_steps`,
  `service`, `category`, `tags`, `environment`, `resolved_at`).
- `opssentinel-logs` — raw log/APM lines backing `fetch_recent_logs` (fields: `service`,
  `timestamp`, `level`, `message`, `labels`).

**OpenInference instrumentation module** — a small importable helper (`lib/observability.py`) that
configures `openinference-instrumentation-google-adk` to export spans to the Phoenix collector. The
Phase-3 ADK app imports and applies it; Phase 2 owns the integration per Member 3's domain.

**Alert Simulator output** — emits the **Phase-1 normalized alert event** onto the Phase-1 topic
`opssentinel-alerts` (reusing `lib/events.py` and `lib/pubsub.py`). It introduces no new schema.

---

## 4. Working method for Claude Code

Build in **small, reviewable increments**. After each numbered task: summarize what you created,
show the command(s) to verify it, and **stop for review** before continuing. Reuse the Phase-1
`lib/` helpers (`events`, `pubsub`, `secrets`, `logging`) and the `infra/` IaC pattern (Terraform
preferred; idempotent `gcloud` acceptable, but reproducible from code). Resolve the Elasticsearch
and Arize credentials **only** through the Phase-1 secrets accessor. Never print secret values.
Keep every choice faithful to Section 2.

---

## 5. Tasks

### Task 5.1 — Stand up Elasticsearch and configure the vector indices
Add an Elasticsearch service to the Phase-1 `docker-compose.yml` (local harness) and document the
managed/cloud equivalent. Create the two indices from Section 3, with the
`opssentinel-knowledge` mapping supporting **hybrid search**: a `dense_vector` field of **384
dims** (cosine) alongside full-text fields. Put the index definitions in
`services/mcp-elastic/index/` (or `infra/elastic/`). **Acceptance:** both indices exist with the
correct mapping; a manually inserted document with a 384-dim vector is retrievable by both a KNN
query and a full-text query.

### Task 5.2 — Build & containerize the Elastic MCP server
In `services/mcp-elastic/`, build a **Python MCP server exposing an SSE endpoint at `/sse`** plus
`/health`. Implement the three tools from Section 3 exactly. The embedding helper must load
**`all-MiniLM-L6-v2`** once and cache it (384-dim, ~100 ms encode). `search_runbooks` must perform
**KNN + full-text fused via RRF** and return the documented shape. Containerize with a **multi-
stage, non-root** Dockerfile (Phase-1 pattern). **Acceptance:** the server starts, `/sse` accepts an
MCP client connection, `search_runbooks` returns RRF-ranked results, `fetch_recent_logs` returns
seeded logs, and `write_closure_summary` indexes a new retrievable document.

### Task 5.3 — Stand up Phoenix and build the Arize Phoenix MCP server
Stand up a **Phoenix** collector/instance (add a container to the local harness; document the cloud
config) to receive OpenInference spans. In `services/mcp-arize/`, build a second **Python MCP
server (SSE at `/sse`, `/health`, multi-stage non-root container)** implementing the four tools
from Section 3, backed by the stored trace/evaluation data. Also provide the
`lib/observability.py` instrumentation helper that configures **`openinference-instrumentation-
google-adk`** to export spans to Phoenix (applied by the Phase-3 agent). **Acceptance:** the server
starts and `/sse` accepts a client; `get_category_accuracy`, `get_calibration`, `is_novel_category`,
and `log_outcome` each return/persist correctly; the instrumentation helper imports cleanly.

### Task 5.4 — Seed synthetic telemetry (the data Phase 2 is tested against)
Create reproducible seed scripts (`scripts/seed_knowledge.py`, `scripts/seed_logs.py`,
`scripts/seed_arize.py`; wire `make seed`) that load the synthetic telemetry the spec's reference
scenario depends on:
- A **"Database Connection Pool Exhausted"** runbook with full resolution steps (connection-pool
  restart + dynamic limit increase), plus several **Kubernetes-class** incidents (pod
  CrashLoopBackOff, OOMKill, network partition, deployment regression) — embedded into
  `opssentinel-knowledge`.
- Corresponding recent log/APM lines in `opssentinel-logs`.
- Seeded Arize history: a **~91% recent accuracy for the "Database Connection Pool" category** (so
  the spec's reference walk-through behaves as written), a well-calibrated example (<5% variance),
  and at least one **degraded/novel** category to exercise the autonomy-lowering path.
**Acceptance:** `make seed` is idempotent and populates all of the above.

### Task 5.5 — Build the Alert Simulator (mock Elastic/PagerDuty signals)
In `services/alert-simulator/`, build a service/CLI that emits **mock Elastic / PagerDuty / Grafana**
signals as **Phase-1 normalized alert events** published to **`opssentinel-alerts`** via
`lib/pubsub.py`. Support two modes: (a) a single realistic incident (the 2:47 AM payment-service
database-connection-pool scenario), and (b) an **alert-storm** mode that emits **50+ related
signals sharing a `correlation_key`**, ready for the Phase-5 deduplication test. Add it to the
local harness; wire `make signal` and `make storm`. **Acceptance:** `make signal` publishes one
valid normalized event and `make storm` publishes 50+ correlated events onto the topic.
*(The full storm-deduplication validation is Phase 5; here you only confirm the signals are
produced and land on the queue.)*

### Task 5.6 — Validate semantic search & observability tools (the spec's Phase-2 test)
Write a validation script/tests (`scripts/validate_phase2.py`; wire `make validate-phase2`) proving:
- **Semantic robustness:** `search_runbooks("connection pool exhausted")` returns the
  **"database connection limit reached"** runbook with sensible **RRF** ordering (different wording,
  correct match).
- `fetch_recent_logs("payment-service")` returns the seeded logs.
- The Arize tools return the seeded values and correctly surface a **degraded/novel** category.
- Both MCP servers are reachable over **SSE** and pass `/health`.
**Acceptance:** the validation suite passes against the seeded data.

### Task 5.7 — Deploy configs, secrets wiring & least-privilege IAM
In `infra/cloud-run/`, add deploy configuration for **`mcp-elastic`** and **`mcp-arize`** as
independent Cloud Run services, pulling `elastic-url`, `elastic-api-key`,
`phoenix-collector-endpoint`, and `phoenix-api-key` from **Secret Manager** via the Phase-1
accessor. In `infra/iam/`, add **dedicated service accounts with custom least-privilege roles** for
each MCP server (and the simulator's Pub/Sub-publish-only role) — **no project Editor**. Document
the SA → role mapping. **Acceptance:** the deploy configs validate / dry-run; credentials resolve
only via Secret Manager; IAM is enumerated and minimal.

---

## 6. Local development & verification harness (mirrors the cloud resources)

Extend the Phase-1 `docker-compose.yml` so `make dev` now also brings up **Elasticsearch**,
**Phoenix**, **`mcp-elastic`**, **`mcp-arize`**, and the **Alert Simulator**, each healthy on its
port. `make seed` loads the synthetic telemetry; `make validate-phase2` runs the Section-5.6 checks.
This local harness is a development/test convenience that mirrors the GCP deployment target; it does
not replace or alter the Cloud Run IaC.

---

## 7. Definition of Done — Phase 2 is complete when

- **Elasticsearch** has `opssentinel-knowledge` (384-dim `dense_vector`, hybrid mapping) and
  `opssentinel-logs`.
- **Elastic MCP server** runs as a non-root container, serves `/sse`, and its three tools work;
  `search_runbooks` uses **`all-MiniLM-L6-v2` + KNN + full-text via RRF**.
- **Phoenix** is running; the **Arize Phoenix MCP server** runs as a non-root container, serves
  `/sse`, and its four tools work; the **`openinference-instrumentation-google-adk`** helper is
  ready for the Phase-3 agent to apply.
- **Synthetic telemetry** is seeded (DB-pool + Kubernetes runbooks, logs, ~91% DB-category Arize
  history, plus a degraded/novel category).
- **Semantic search validation passes:** a differently-worded query retrieves the correct runbook
  via RRF; the Arize tools surface accuracy/calibration/novelty correctly.
- The **Alert Simulator** publishes single and 50+-signal correlated events onto `opssentinel-alerts`.
- Cloud Run deploy configs for both MCP servers validate; credentials come only from Secret
  Manager; least-privilege IAM (no Editor) is in place.
- `make dev` brings up the full local harness; `make seed` and `make validate-phase2` succeed.

---

## 8. Handoff to Phase 3 (and beyond)

Phase 2 hands the team: live **Elastic MCP** and **Arize Phoenix MCP** SSE endpoints with the exact
tool contracts; the **`all-MiniLM-L6-v2` + KNN + RRF** semantic memory seeded with runbooks; the
**Phoenix** collector plus the **OpenInference instrumentation helper** the ADK app will apply; and
the **Alert Simulator** for generating test signals. Phase 3 (Member 2 — the ADK agent) connects to
both servers as an MCP client over SSE and drives the retrieval + adaptive-autonomy loop.

---

## 9. Guardrails — do NOT build in Phase 2

- No ADK agent, Gemini reasoning, Policy Engine, or signal-correlation algorithm (Phase 3).
- No Slack bot, Block Kit brief, or approval webhook (Phase 5 / Member 3).
- No full alert-storm deduplication validation run — the simulator is built here, but the storm
  test itself is Phase 5.
- No Next.js dashboard (Phase 4).
- None of the spec-deferred features: Multi-Agent Collaboration, Digital Twin Simulation,
  Predictive Prevention.

Keep every choice faithful to the OpsSentinel MVP specification — no technology substitutions and
no scope beyond Member 3's data, memory, and observability responsibilities for this phase.
