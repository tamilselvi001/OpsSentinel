# PHASE 6 — Integration, Live Validation & Spec Fidelity

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Goal:         Turn the existing, unit-tested codebase into a VALIDATED MVP that demonstrably
              meets the spec's three Exit Criteria, and reconcile the one major framework
              deviation (Google ADK).
Runs after:   Phases 1–5 (all code is written, committed, and pushed). Backend unit tests pass
              (ruff clean, ~88 pytest green); the Next.js frontend builds (`npm run build`).
Source of truth: notes/mvp.pdf  (the MVP specification) — especially "Exit Criteria and
              Validation Checkpoints". Every prior phase prompt lives in PROMPTS/00..05.
How to use:   Open this repo in Claude Code (or any capable coding agent). FIRST confirm the
              human has completed docs/MANUAL-SETUP.md. Then paste THIS ENTIRE FILE as your
              message and work the tasks strictly in order.
```

> **Read this first — what state the project is in.** The five build phases are *written and
> committed*, and the deterministic logic is unit-tested. BUT nothing has ever run against live
> infrastructure: no `docker compose` up, no `terraform validate`, no container build, no real
> Gemini / Elastic / Phoenix / Slack / Postgres connection. The spec defines "done" by three
> **Exit Criteria that all require a live end-to-end run** (see notes/mvp.pdf p.14). Your job is to
> make those criteria actually pass, fixing real integration bugs as they surface — **not** to add
> features or to paper over failures with mocks.

---

## Operating rules (follow on every task)

1. **Work in small, reviewable increments.** After each numbered task: summarize what you did,
   show the exact command(s) that prove it works, and **STOP for human review** before continuing.
2. **Fix real bugs; never fake success.** When a container won't start or a call fails, read the
   logs, find the root cause, and fix it. Do not replace a broken real integration with a stub to
   make a check "pass". The remediation *execution path* stays mocked (that is per the spec); the
   *infrastructure and integrations* (Pub/Sub, Postgres, Elastic, Phoenix, Gemini, Slack) must be
   real.
3. **Never invent credentials or secrets.** If a required secret/tool is missing, STOP and tell the
   human exactly which item in `docs/MANUAL-SETUP.md` is incomplete. Never hardcode or commit a
   secret. Resolve secrets only through the existing `lib/secrets.get_secret()` (Python) or the
   frontend's runtime env.
4. **Reuse what exists.** All `lib/`, `services/`, `infra/`, `frontend/`, `scripts/`, and `tests/`
   code already exists — extend it, do not rewrite it. Keep changes minimal and faithful to the
   spec.
5. **Re-run the existing checks after any change.** Backend: `ruff check . && pytest`. Frontend:
   `npm run build`. Do not regress the green suite.
6. **Windows note:** `make` may not be installed. If a `make <target>` command is unavailable, open
   the `Makefile`, find that target, and run its underlying command directly (e.g. `docker compose
   up -d --build`). Use the project's `.venv` Python on Windows: `./.venv/Scripts/python`.
7. **One change of intent needs human sign-off:** Task 4 (the ADK decision). Do not implement it
   until the human has chosen Option A or Option B.

---

## Definition of Done for Phase 6

All three spec Exit Criteria are demonstrated on a live local stack, evidence is captured, the IaC
validates, and the ADK deviation is resolved:

- **EC1** — a ≥50-signal alert storm is ingested via Pub/Sub, deduplicated into **one** incident
  with **zero dropped events** (DLQ empty).
- **EC2** — the agent retrieves a relevant runbook (Elastic MCP), queries its accuracy (Arize MCP),
  formats a proposal, routes it to Slack; **Approve** runs the deterministic executor that updates
  the mocked infra and resolves the ticket, writes closure to Elastic, logs the outcome to Arize.
- **EC3** — every step appears as an OpenInference trace in Phoenix (tool calls, latency, tokens),
  AND the Next.js dashboard loads behind Google auth and renders incident state via SSR with zero
  unhandled client-side exceptions.

---

## TASK 0 — Preflight: confirm prerequisites & protect secrets

**Objective:** Make sure the environment is actually ready before touching anything.

**Steps**
1. Read `docs/MANUAL-SETUP.md`. Verify each item the human was responsible for is done:
   - Tools installed: **Docker** (required now), and confirm Python + Node are present. Terraform
     and gcloud are needed later (Tasks 6–7).
   - A real `.env` exists at the repo root (copied from `.env.example`) with **real** values for at
     least `GEMINI_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `GOOGLE_OAUTH_CLIENT_ID`,
     `SESSION_SECRET`.
   - **Secret safety:** confirm the root `.gitignore` ignores `.env`, `*.tfstate`, `*.tfvars`,
     `*-key.json`, `service-account*.json`. If it does not, add them now and verify with
     `git check-ignore .env` (it must print `.env`). **Do not let real secrets get committed.**
2. If anything is missing, STOP and list exactly what the human must do (point to the section in
   `docs/MANUAL-SETUP.md`). Do not proceed.

**Acceptance:** Docker runs (`docker version` works), `.env` exists with real secrets, and
`git check-ignore .env` confirms `.env` is ignored. **STOP for review.**

---

## TASK 1 — Bring up the full local stack and make every service healthy

**Objective:** Get the entire system running locally on the docker-compose stack. This is where the
real integration bugs live; expect to fix several.

**Steps**
1. `make dev` (or `docker compose up -d --build`). Bring up: Pub/Sub emulator, Postgres,
   Elasticsearch, Phoenix, mcp-elastic, mcp-arize, agent, slack-bot, frontend, alert-simulator.
2. Watch logs (`docker compose logs -f <service>`). For each unhealthy/crashing container, read the
   error, fix the root cause (a wrong import, a bad env var, a pinned dependency version that does
   not exist, an API signature drift in `mcp` / `google-genai` / `slack_sdk`, a port clash, etc.),
   and rebuild that service. Pin dependency versions to ones that actually resolve.
3. `make migrate` (apply the incident-store + agent_outcomes schema). `make seed` (load the runbooks,
   logs, and ~91% Arize history).
4. Confirm health endpoints: mcp-elastic `/health`, mcp-arize `/health`, slack-bot `/health`, agent
   `/health` all return 200; the frontend serves `/login`.

**Acceptance:** `docker compose ps` shows every service healthy; `make seed` completes; all `/health`
endpoints return 200. Summarize every bug you fixed. **STOP for review.**

---

## TASK 2 — Prove Exit Criterion 1 (storm dedup, zero alert loss)

**Objective:** Demonstrate the storm folds into one incident with no dropped events.

**Steps**
1. With the stack up and the agent consuming, run `make validate` (publishes ≥50 correlated signals
   via `scripts/run_storm.py`, waits, then reconciles).
2. Verify: exactly **one** incident is created for the storm's `correlation_key`; the count of
   correlated `incident_events` equals the number of published signals (no loss); the
   `opssentinel-alerts-dlq-sub` DLQ is **empty**.
3. If the agent's streaming correlator strands the final incident (it only flushes when a later
   event arrives), fix the flush (e.g. a periodic timer / idle-based flush) so the storm's incident
   is emitted within the correlation window without needing extra traffic.

**Acceptance:** 50+ signals → exactly one incident, published-count == processed-count, DLQ empty.
Capture the numbers. **STOP for review.**

---

## TASK 3 — Prove Exit Criterion 2 (retrieve → self-evaluate → propose → Slack → Approve → execute)

**Objective:** Run the full reference workflow end to end on the seeded DB-connection-pool scenario.

**Steps**
1. Emit the single reference incident: `make signal` (the 02:47 payment-service DB-pool event).
2. Confirm in logs/DB the agent: classified it with **Gemini 2.0 Flash**; called Elastic MCP
   `fetch_recent_logs` + `search_runbooks` and retrieved the DB-pool runbook (a query worded
   "connection pool exhausted" must match the "Database Connection Limit Reached" runbook via RRF);
   called Arize MCP and set an `autonomy_tier`; persisted the incident `awaiting_approval` with a
   `trace_id`.
3. Confirm the **slack-bot posted a plain-text brief** (root cause, historical precedent, proposed
   fix, risk level) with Approve/Reject buttons to your channel. (This needs a real Slack app +
   tunnel — see MANUAL-SETUP. If the human has not set up Slack, fall back to `make approve
   INCIDENT=<id>` to drive the executor, and note the Slack-UI step as human-verified-separately.)
4. Click **Approve** (or run the approve shim). Confirm the deterministic executor: updated the
   mocked infra + resolved the mocked ServiceNow ticket; wrote a closure document to Elastic via
   `write_closure_summary`; logged the outcome to Arize via `log_outcome`; set `status = resolved`.
5. Confirm the **memory loop closes**: `search_runbooks` now retrieves the freshly written closure.

**Acceptance:** the chain runs green; the incident reaches `resolved`; closure is retrievable; the
outcome is logged. Capture log excerpts. **STOP for review.**

---

## TASK 4 — Migrate the agent to real Google ADK  *(DECISION MADE: Option A)*

**Objective:** The spec mandates **Google ADK (Graph Workflows)** with **`McpToolset`** and the
`openinference-instrumentation-google-adk` tracer. The current agent is a hand-rolled orchestrator
(`services/agent/app/graph.py`) using `google-genai` directly and the raw `mcp` SSE client — so ADK
is listed in requirements but **not actually used**, and the ADK auto-tracer captures nothing.

**The human has chosen Option A — use real Google ADK.** Implement it exactly per the detailed,
API-verified plan in **`docs/ADK-MIGRATION.md`** (it was written against the installed
`google-adk` 2.2.0 and gives the real imports, the node→ADK mapping, the file plan, the tracing
wiring, and the gotchas). In summary:
- Build the agent with `LlmAgent` (Gemini 2.0 Flash) + two `McpToolset(SseConnectionParams(url=...))`
  clients for the Phase-2 Elastic and Arize MCP servers, composed in a `SequentialAgent`, executed
  via `Runner` + `InMemorySessionService`.
- Keep `correlation`, `autonomy`, `policy`, `brief`, `persistence`, `executor`, `mock_infra` as the
  deterministic nodes — **the Policy Engine and autonomy decision must stay deterministic; the LLM
  cannot bypass them**. Remediation stays mocked.
- Apply `GoogleADKInstrumentor().instrument(...)` so every tool call / model call / token becomes a
  Phoenix span (this is what makes Exit Criterion 3 truly achievable).
- Remove the now-dead hand-rolled MCP/LLM code (`app/mcp_clients.py`, `app/reasoning.py`, the LLM
  parts of `app/graph.py`) so ADK is genuinely the framework; bump `google-adk>=2.2` in
  `services/agent/requirements.txt`.

**Steps:** implement per `docs/ADK-MIGRATION.md`; keep the deterministic unit tests green; port
`tests/test_graph.py` to the ADK path using a fake/echo model so it runs without a live Gemini key;
`ruff check . && pytest`; `docker compose build agent`; bring the agent up and re-run Task 3.

**Acceptance:** the agent is built on ADK (`LlmAgent` + `McpToolset` + `SequentialAgent` + `Runner`);
deterministic governance unchanged and still unit-tested; a live run shows real ADK/OpenInference
spans in Phoenix; the dead hand-rolled code is gone. **STOP for review.**

---

## TASK 5 — Prove Exit Criterion 3 (observability + secured exception-free frontend)

**Objective:** Demonstrate full tracing and the live dashboard.

**Steps**
1. **Phoenix:** open the Phoenix UI (default http://localhost:6006). Confirm a full run from Task 3
   appears as an OpenInference trace timeline showing tool executions, latency, and token counts.
   Confirm each incident's `trace_id` (persisted on the row) matches a trace in Phoenix.
2. **Frontend live mode:** run the dashboard with `OPSSENTINEL_DATA_MODE=live` against the same
   Postgres. Sign in with Google (the configured OAuth client). Confirm: unauthenticated requests
   are redirected to `/login`; an authenticated user sees the storm's single incident render
   **server-side** on `/incidents` and `/incidents/[id]` with the audit timeline and reliability
   metrics; the Phoenix trace deep-link from the incident opens the correct trace; and the browser
   console shows **zero unhandled exceptions**.
3. Fix the incident-detail Phoenix deep-link URL to match the real Phoenix route if the current
   guessed format is wrong.

**Acceptance:** Phoenix shows the complete trace; the secured dashboard renders the live incident via
SSR with no client-side exceptions; the trace link resolves. Capture screenshots / links. **STOP for
review.**

---

## TASK 6 — Validate the Infrastructure-as-Code and build all images

**Objective:** Make the cloud path real-ish: prove the Terraform is syntactically and
schematically valid and every container builds.

**Steps**
1. For each `infra/<component>` (pubsub, postgres, secret-manager, cloud-run, networking, iam,
   scheduler): `terraform -chdir=infra/<component> init -backend=false` then `terraform -chdir=
   infra/<component> validate`. Fix every error (missing variables, bad attribute names, provider
   version issues, resource arg drift). Run `terraform fmt -recursive infra/`.
2. Build all six service images locally to prove the Dockerfiles work:
   `docker build -f services/webhook-receiver/Dockerfile -t webhook-receiver .` and likewise for
   `mcp-elastic`, `mcp-arize`, `agent`, `slack-bot`, and `docker build -t frontend ./frontend`. Fix
   any build failure. Confirm each image runs as a **non-root** user.

**Acceptance:** every `terraform validate` passes; all six images build and run non-root. **STOP for
review.**

---

## TASK 7 — (Optional) Deploy to Google Cloud Run  *(needs the human's GCP setup)*

**Objective:** Stand the system up on real GCP. Only attempt this after the human has completed the
"Optional: Cloud deployment" section of `docs/MANUAL-SETUP.md` (a GCP project, billing, enabled
APIs, `gcloud auth`, and populated Secret Manager versions).

**Steps (apply order matters):**
1. `infra/secret-manager` → `infra/iam` → `infra/pubsub` → `infra/postgres` → push images to
   Artifact Registry → `infra/cloud-run` → `infra/scheduler` → `infra/networking`. For each:
   `terraform -chdir=infra/<c> init && apply -var project_id=$GOOGLE_CLOUD_PROJECT`.
2. After `infra/postgres`, feed its `database_url` output into the `database-url` secret, then
   `make migrate` against the cloud DB. Populate the remaining Secret Manager versions.
3. Verify the deployed services' `/health`, then re-run the storm against the cloud Pub/Sub.

**Acceptance:** services are deployed behind the L7 LB; the storm validates in the cloud; least-
privilege IAM holds (no Editor). **STOP for review.**

---

## TASK 8 — Polish the metrics and rough edges

**Objective:** Finish the spec's success-metric surfacing.

**Steps**
1. In `frontend/lib/data/incidents.ts` live mode, populate the currently-`null` metrics:
   - **MTTD** — derive from first-signal `received_at` to incident `created_at`.
   - **Correlation precision** — derive from the dedup ratio during a storm (signals folded ÷
     signals received).
2. Confirm MTTR / triage accuracy / approval rate / calibration / autonomy coverage compute
   sensibly against real data. Re-check the reliability view renders them.
3. Any remaining TODO/guessed value (e.g. Phoenix URL format from Task 5) — finalize.

**Acceptance:** the reliability dashboard shows real, sensible values for all MVP success metrics.
**STOP for review.**

---

## TASK 9 — Capture the green-run evidence and write the final report

**Objective:** Produce the spec's required deliverable: a captured green run proving the Exit
Criteria.

**Steps**
1. Run the full `docs/DEMO.md` walkthrough start to finish on the live stack.
2. Capture evidence: terminal output of `make validate` (EC1), log excerpts of the
   retrieve→Slack→Approve→execute chain (EC2), Phoenix trace screenshots/links + a dashboard
   screenshot behind auth (EC3).
3. Save it as `docs/VALIDATION-EVIDENCE.md` (or a `docs/evidence/` folder), and write a short final
   report mapping each Exit Criterion + each success metric to its evidence.

**Acceptance:** `docs/VALIDATION-EVIDENCE.md` exists and demonstrates all three Exit Criteria.
**STOP — Phase 6 complete; the MVP is validated and ready for internal beta.**

---

## Guardrails — do NOT do these

- Do not turn the remediation execution into real cluster mutations — it stays **mocked**.
- Do not add deferred features: Multi-Agent Collaboration, Digital Twin Simulation, Predictive
  Prevention.
- Do not introduce new schemas or Pub/Sub topics — connect only what exists.
- Do not commit any secret, `.env`, `*.tfstate`, or service-account key.
- Do not "pass" an Exit Criterion by mocking the integration it is meant to prove.
```
