# PHASE 4 — Frontend Development & Security (Member 4)

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Owner:        Member 4 — Frontend & Security Engineer
Source of truth: "OpsSentinel: Master Architecture and Minimum Viable Product Specification"
Build phase:  Phase 4 of 5 — "Frontend Development and Security"
Runs after:   Phase 1 (the repo skeleton; the Cloud Run + Artifact Registry deploy scaffolding;
              the basic networking foundation — Serverless NEG + Layer-7 load balancer + Cloud CDN
              config; Secret Manager + the secrets that include google-oauth-client-id and
              database-url; least-privilege IAM) and Phase 3 (the agent that populates the
              PostgreSQL incident store with the incident state + trace_id this dashboard renders).
              The UI shell + authentication may be scaffolded in parallel during Phase 3 against
              mock data; live data rendering needs Phase 3's incidents.
How to use:   Open Claude Code at the repo root, ensure ./docs/mvp.pdf is present, then paste THIS
              ENTIRE FILE as your message.
```

> **Build discipline (read first).** Implement this phase **strictly as written in the
> OpsSentinel MVP specification**. Do **not** substitute technologies, re-architect, or add
> features beyond Member 4's frontend, authentication, and client-side-delivery scope. Every
> component, technology choice, and design rationale below comes directly from the specification.
> If a detail is unspecified, choose the simplest implementation that satisfies the spec's stated
> intent, note the assumption, and do not expand scope.

---

## 1. Project context (from the specification)

OpsSentinel is structured across five processing layers: Input, Queue, Agent, Memory &
Self-Evaluation, and Observe. The backend (Phases 1–3) handles asynchronous orchestration; **Phase
4 builds the front of house** — per the spec, *the frontend serves as the management and
observability console for engineering directors and SREs*. It is the human-facing window onto the
incident state the agent produces and the reliability telemetry the Observe Layer captures.

Per the spec's implementation milestones, Phase 4's core objective is to *develop the Next.js
dashboard, containerize it using a multi-stage Alpine Dockerfile, and implement Google Identity
Services for authentication*. As the Frontend & Security Engineer, Member 4 also owns
**client-side delivery** — deploying the container to Cloud Run behind the Phase-1 **Serverless
NEG + Layer-7 load balancer** and integrating **Google Cloud CDN** (Pull strategy + TTL).

This dashboard is what the spec's **Engineering Manager / Director** persona needs to close their
core pain point ("complete lack of visibility into automation reliability and operational risk"):
*real-time observability dashboards demonstrating AI decision accuracy, calibration, and overall
operational health.*

**What Phase 4 deliberately does NOT build** (belongs to other phases / members): any backend
reasoning, the ADK agent, the Policy Engine, or signal correlation (Phase 3 / Member 2); the
Elastic/Arize MCP servers (Phase 2 / Member 3); the **Slack human-in-the-loop bot and approval
webhook** (Phase 5 / Member 3); and the full alert-storm validation run (Phase 5). Also out of
scope: the spec-deferred capabilities — **Multi-Agent Collaboration, Digital Twin Simulation,
Predictive Prevention**.

---

## 2. Non-negotiable principles Phase 4 must honor (directly from the spec)

1. **Next.js with the App Router**, optimized for serverless deployment on **Google Cloud Run**.
2. **Containerization is a multi-stage Docker build using Dockerfiles, not Buildpacks** (the spec
   requires Dockerfiles for granular optimization). The image uses **Alpine Linux** as the base to
   shrink the footprint; Next.js runs in **standalone output mode** (the compiler traces deps and
   bundles only what production needs); and the Dockerfile **creates and runs as a non-root user**
   to mitigate privilege escalation. These four properties are mandatory.
3. **Client-side delivery networking:** a **Serverless Network Endpoint Group (NEG)** securely
   connects the **external Layer-7 (HTTP/S) load balancer** to the Cloud Run service (L7 routing on
   HTTP headers/cookies). Static assets are served via **Google Cloud CDN using a Pull strategy** —
   on first request the CDN pulls the asset from the Cloud Run origin and caches it per
   **Time-to-Live (TTL) headers** for low-latency delivery to all subsequent users. (The NEG + LB +
   CDN foundation was provisioned in Phase 1; Phase 4 attaches the frontend and sets the TTL/caching
   behavior, assisted by Member 1.)
4. **Authentication via Google Identity Services.** ID tokens are retrieved **client-side**, then
   transmitted to **the backend**, where they are **cryptographically verified using official
   Google API client libraries to prevent spoofing**. The **subject (`sub`) claim** from the
   decoded token is the **immutable primary key for user mapping**, ensuring **strict separation of
   authentication protocols from infrastructure authorization scopes**, and is used for **role
   separation** of the dashboard's views.
5. **Server-side data fetching, zero client-side exceptions.** Per the Exit Criteria, the frontend
   must **securely load behind Google Authentication** and **render the incident state via
   server-side data fetching with zero unhandled client-side exceptions**.
6. **Single cloud (GCP only); secrets only via Secret Manager** (`google-oauth-client-id`, and any
   data-store credential, are injected at runtime — never hardcoded or committed); **least
   privilege** for the frontend's Cloud Run service account (no project Editor).

---

## 3. Interfaces Phase 4 consumes and produces

**Consumes (already built):**
- Phase 1: the **Cloud Run + Artifact Registry** deploy scaffolding; the **basic networking** in
  `infra/networking/` (Serverless NEG + L7 HTTPS load balancer + Cloud CDN config), provisioned and
  documented as "ready for the Phase-4 frontend attach"; **Secret Manager** holding
  `google-oauth-client-id` (and `database-url`); the least-privilege IAM pattern.
- Phase 3 (via Phase 1's store): the **PostgreSQL incident store** (`incidents`, `incident_events`,
  `audit_log`), populated by the agent, including each incident's `status`, `severity`, `category`,
  remediation-team assignment, `root_cause`, `confidence`, `risk_level`, `recommended_action`,
  `historical_match_ids`, `autonomy_tier`, `approval_status`, `resolution_summary`, and **`trace_id`**.
- Phase 2: the **Phoenix** trace UI that the dashboard deep-links to via each incident's `trace_id`.

**The "backend" the spec refers to for token verification and data fetching is the Next.js App
Router server layer itself** (route handlers / server components running on Cloud Run, Node
runtime). Implement token verification and **server-side reads of the incident store** there — do
**not** invent a separate API microservice (the spec names only the Next.js frontend and "the
backend"). Reads are **read-only**; the dashboard never mutates incident state (approval/execution
is the Slack/agent path).

**Produces:** a deployed, **Google-authenticated** Next.js dashboard that **server-side-renders**
the incident state and the reliability/observability metrics, fronted by the Serverless NEG + L7 LB
+ Cloud CDN.

---

## 4. The dashboard surface (grounded in the spec)

Keep pages focused on what the spec calls for — incident state + AI reliability telemetry:
- **Incident list** — the current incident state: per incident show `severity`, `category`,
  remediation team, `status`, `confidence`, `autonomy_tier`, `risk_level`, and age; filter by
  `status` and `severity`. (Satisfies the Exit Criterion "render the incident state.")
- **Incident detail** — root cause, correlated evidence, confidence, historical precedent
  (`historical_match_ids`), proposed `recommended_action` steps, `risk_level`, the autonomy/caution
  note, the `audit_log` timeline, and a **deep link to the Arize Phoenix trace** (`trace_id`).
- **Reliability & observability dashboard** — *AI decision accuracy, calibration, and overall
  operational health*: the MVP success metrics — **MTTD, MTTR, triage/routing accuracy, alert
  correlation precision, autonomous approval rate, and the Arize confidence-calibration variance**.
- **Operational health / connected sources** — a simple status view of the platform's health.

Role separation (from the `sub`-mapped user): e.g. directors land on the reliability dashboard;
SREs land on the incident list. Keep it simple and driven by the verified token, not client state.

---

## 5. Working method for Claude Code

Build in **small, reviewable increments**. After each numbered task: summarize what you created,
show how to verify it, and **stop for review** before continuing. Reuse the Phase-1 `infra/cloud-run`
and `infra/networking` IaC and the Secret Manager conventions. Resolve `google-oauth-client-id` and
any data-store credential **only** at runtime via Secret Manager; never hardcode or log secrets.
Keep every choice faithful to Section 2.

---

## 6. Tasks

### Task 6.1 — Scaffold the Next.js App Router app  *(may start in parallel with Phase 3)*
Create `frontend/` as a **Next.js (App Router) + TypeScript** project configured with
**`output: 'standalone'`**, ESLint/Prettier, and a clean component structure. Define TypeScript
types for the incident read-model that mirror the Phase-1 incident schema (keep them in
`frontend/lib/types/`). Add the dev server to the Phase-1/2/3 `docker-compose.yml`. **Acceptance:**
the app builds and runs locally; standalone output is enabled.

### Task 6.2 — Authentication with Google Identity Services  *(may start in parallel)*
Implement **Google Identity Services** sign-in on the client to obtain an **ID token**. On the
**Next.js server layer**, **cryptographically verify** the token with the **official Google
authentication client library** (against `google-oauth-client-id` from Secret Manager), reject
invalid/spoofed tokens, and establish a **secure server-side session** (httpOnly cookie — do not
keep the raw token in client-accessible storage). Map the verified **`sub` claim** to the user and
drive **role separation** from it. Add a server-side guard so unauthenticated requests cannot reach
dashboard routes. **Acceptance:** unauthenticated users are blocked; a valid Google sign-in yields a
verified session keyed by `sub`; tampered tokens are rejected.

### Task 6.3 — Build the dashboard UI with a typed mock  *(may start in parallel)*
Build the layout and the four views from Section 4 against a **typed mock** of the incident
read-model and metrics, so UI work is not blocked on live data. Use server components for structure
and add **loading and error boundaries** everywhere so a data hiccup degrades gracefully rather than
throwing on the client. **Acceptance:** all four views render from mock data with no client-side
exceptions.

### Task 6.4 — Server-side data fetching from the incident store  *(needs Phase 3)*
Replace the mock with **server-side reads** (route handlers / server components on the Node runtime)
of the **Phase-1 PostgreSQL incident store** populated by the Phase-3 agent — list, detail, and the
metrics aggregation — forwarding only within the verified session. Render incident detail **server-
side (SSR)** so first paint is exception-free, with robust error/empty/loading states. Wire the
incident-detail page's **Phoenix trace deep-link** from `trace_id`. **Acceptance:** the list and the
**server-rendered** detail show real agent-produced incidents with **zero unhandled client-side
exceptions**; the trace link opens the correct Phoenix trace; the metrics view shows live values.

### Task 6.5 — Containerize: multi-stage Alpine, standalone, non-root
Write the production **Dockerfile**: a multi-stage build (deps/build stage → minimal runtime stage)
on an **Alpine Linux** base, copying the Next.js **standalone** output, creating and running as a
**non-root user**, and exposing the Cloud Run port. Keep the image lean (the spec's footprint goal).
Confirm it builds and runs locally. **Acceptance:** the image builds, runs as non-root, serves the
authenticated dashboard, and is demonstrably smaller than a naive single-stage build.

### Task 6.6 — Deploy to Cloud Run + attach Serverless NEG + L7 LB + Cloud CDN
Using the Phase-1 `infra/cloud-run` and `infra/networking` IaC, deploy the container to **Cloud
Run**, attach the **Serverless NEG** to the **external Layer-7 HTTPS load balancer**, and enable
**Cloud CDN with the Pull strategy**, setting **TTL/cache-control headers** on static assets for
low-latency delivery. Inject `google-oauth-client-id` (and any data-store credential) from **Secret
Manager** at runtime. Document the apply order and the cache headers. **Acceptance:** the deploy/
networking IaC validates / dry-runs cleanly; the service is reachable behind the L7 LB; static
assets are served from Cloud CDN with the documented TTL.

### Task 6.7 — Least-privilege IAM for the frontend
In `infra/iam/`, give the frontend's Cloud Run service its **own service account with a custom
least-privilege role** (Secret Manager accessor for the OAuth client id + the read-only data-store
credential; Cloud SQL client for read access) — **no project Editor**. Document the SA → role
mapping. **Acceptance:** the frontend SA is minimal and enumerated; no Editor anywhere.

---

## 7. Local development & verification harness

Add the **frontend** dev server to the `docker-compose.yml` so `make dev` runs it against the
emulated stack. Provide a **mock-data mode** (env-flagged) so the UI and auth can be developed and
demoed without a live agent, and a **live mode** that reads the Phase-1 Postgres incident store once
Phase 3 is producing incidents. This harness mirrors the Cloud Run deployment target; it does not
replace the IaC.

---

## 8. Definition of Done — Phase 4 is complete when

- The **Next.js App Router** app builds with **standalone output** and runs locally and on Cloud Run.
- **Google Identity Services** sign-in works; the **server layer cryptographically verifies** the ID
  token with the official Google library, rejects spoofed tokens, keys the session on the **`sub`
  claim**, and enforces **role separation**; unauthenticated access is blocked.
- The dashboard **renders incident state via server-side data fetching with zero unhandled
  client-side exceptions**, including the incident list, the SSR incident detail with the **Phoenix
  `trace_id` deep-link**, and the **reliability/observability metrics** (MTTD, MTTR, triage accuracy,
  correlation precision, autonomous approval rate, Arize calibration).
- The production image is a **multi-stage Alpine** build of the **standalone** output running as a
  **non-root** user, deployed to **Cloud Run** behind the **Serverless NEG + L7 load balancer** with
  **Cloud CDN (Pull + TTL)** serving static assets.
- All credentials come only from **Secret Manager**; the frontend SA is **least-privilege** (no
  Editor).

---

## 9. Handoff to Phase 5

Phase 4 hands the team a deployed, **Google-authenticated** dashboard that **server-side-renders**
the live incident state and reliability metrics — exactly the surface Phase 5's end-to-end
validation checks ("the Next.js frontend must securely load behind Google Authentication, rendering
the incident state via server-side data fetching with zero unhandled client-side exceptions"). Phase
5 will also wire the Slack approval gate whose outcomes (resolved incidents, updated state) this
dashboard then reflects.

---

## 10. Guardrails — do NOT build in Phase 4

- No backend reasoning, ADK agent, Policy Engine, or correlation logic (Phase 3) — read-only.
- No Elastic/Arize MCP servers or embeddings (Phase 2).
- No Slack bot, Block Kit brief, or approval webhook (Phase 5) — the dashboard does not approve or
  execute remediations; it only renders state and links to the Phoenix trace.
- No separate API microservice — use the Next.js server layer as "the backend."
- No client-accessible token storage (e.g. localStorage) for auth — use a secure httpOnly session.
- None of the spec-deferred features: Multi-Agent Collaboration, Digital Twin Simulation,
  Predictive Prevention.

Keep every choice faithful to the OpsSentinel MVP specification — no technology substitutions and no
scope beyond Member 4's frontend, authentication, and client-side-delivery responsibilities.
