# PHASE 5 — Workflow Integration & Feedback Loop (All Members)

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Owner:        All four members, coordinated (Slack HITL led by Member 3)
Source of truth: "OpsSentinel: Master Architecture and Minimum Viable Product Specification"
Build phase:  Phase 5 of 5 — "Workflow Integration and Feedback Loop"
Runs after:   Phases 1–4 — the Queue Layer + incident store + Secret Manager + opssentinel-actions
              + networking (Phase 1); the Elastic & Arize MCP servers + seeded memory + the Alert
              Simulator (Phase 2); the ADK agent that produces incidents, the execution brief, the
              deterministic execution path, and OpenInference traces (Phase 3); the Google-
              authenticated, server-side-rendered dashboard (Phase 4).
Enables:      Internal beta sign-off — this phase proves every Exit Criterion.
How to use:   Open Claude Code at the repo root, ensure ./docs/mvp.pdf is present, then paste THIS
              ENTIRE FILE as your message. Assign the sub-sections to their owners, integrate, then
              run the validation suite.
```

> **Build discipline (read first).** Implement this phase **strictly as written in the
> OpsSentinel MVP specification**. Do **not** substitute technologies, re-architect, or add
> features beyond what the spec's Phase 5 and Exit Criteria require. Every component below comes
> directly from the specification. If a detail is unspecified, choose the simplest implementation
> that satisfies the spec's stated intent, note the assumption, and do not expand scope.

---

## 1. Project context (from the specification)

The four work-streams now exist in isolation. **Phase 5 connects them into one observable
workflow and proves the MVP is real.** Per the spec's implementation milestones, Phase 5's core
objective is to *connect the Slack integration for approval webhooks and run end-to-end
simulations of cascading alert storms to validate deduplication logic*. The MVP development cycle
is considered complete — and the project authorized for internal beta — **only when the rigorous
Exit Criteria are met** (Section 7).

The one workflow to make whole, end to end: *cascading alert storm → time-windowed correlation
into a single incident (no dropped events) → Elastic MCP retrieval of the closest historical
runbook + last 30 minutes of logs → Arize MCP self-evaluation of category accuracy → a remediation
proposal → a Slack decision brief to a human → Approve → the deterministic execution path updates
the mocked infrastructure state and resolves the ticket → closure written back to Elastic + outcome
logged to Arize → every step an OpenInference trace in Phoenix → the dashboard renders the incident
state under Google auth with zero client-side exceptions.*

**What Phase 5 deliberately does NOT do:** introduce any spec-deferred capability — **Multi-Agent
Collaboration, Digital Twin Simulation, Predictive Prevention** — and it does **not** turn the
execution path into real cluster mutations: remediation remains **mocked**, per the Exit Criteria's
own wording ("updates the *mocked* infrastructure state").

---

## 2. Non-negotiable principles Phase 5 must honor (directly from the spec)

1. **Slack is the asynchronous approve/reject gate.** The Slack bot serves as *the asynchronous
   approve and reject gate where human engineers interact with the agent's proposals*, delivering
   **plain-text decision briefs, complete with calculated risk levels and binary execution
   capabilities (Approve / Reject)**. The agent may take a high-risk/destructive action **only when
   explicitly authorized by a senior engineer via the Slack webhook**.
2. **Approval triggers the deterministic execution path** built in Phase 3 — *execute the webhook to
   restart the pool, update the (mocked) ServiceNow ticket, and permanently log the successful
   outcome into the Elastic knowledge base and the Arize trace history*.
3. **Zero alert loss + deduplication under load.** A storm of **≥ 50 duplicate signals** ingested
   via Pub/Sub must be **dynamically deduplicated and synthesized into a single incident entity
   without a single dropped event**, proving high availability and scalability under load.
4. **Absolute observability.** **Every phase** of the stress test must be an **OpenInference trace**
   in the **Arize Phoenix** UI, clearly delineating **tool executions, latency metrics, and token
   consumption**.
5. **Secured, exception-free frontend.** The Next.js frontend must **securely load behind Google
   Authentication** and **render the incident state via server-side data fetching with zero
   unhandled client-side exceptions**.
6. **Single cloud (GCP); secrets only via Secret Manager** (`slack-bot-token`,
   `slack-signing-secret` from Phase 1, injected at runtime — never hardcoded); **least privilege**
   for the Slack bot's service account (no project Editor).

---

## 3. Interfaces Phase 5 wires together

- **Slack bot** (`services/slack-bot/`, Member 3): exposes (a) an internal **`POST /notify`** that
  the agent calls when an incident reaches `awaiting_approval` (payload: `{incident_id}`); the bot
  reads the persisted brief from the Phase-1 incident store and posts it to the designated Slack
  channel; and (b) **`POST /slack/interactions`** — Slack's interactivity request URL,
  **signature-verified with `slack-signing-secret`** — handling the **Approve / Reject** buttons.
- **Approval → execution:** on **Approve**, the bot publishes to the Phase-1 **`opssentinel-actions`**
  topic (the channel the Phase-3 deterministic executor already consumes) and appends to
  `audit_log`; on **Reject**, it sets the incident `status = rejected` and appends to `audit_log`.
- **Agent hook (Phase-3 ↔ Phase-5 wiring, Member 2 + Member 3):** the agent's existing "emit the
  brief for human delivery" step (node 8) is connected to call the Slack bot's `/notify`.
- **Alert Simulator** (`services/alert-simulator/`, Phase 2): drives the storm onto
  `opssentinel-alerts`.
- **Dashboard** (Phase 4): renders the resulting incident state and links each incident's
  `trace_id` to the Phoenix trace.

No new schemas or topics are introduced — Phase 5 only connects what Phases 1–4 published.

---

## 4. Working method for Claude Code

Build in **small, reviewable increments**; after each sub-section, summarize what changed, show how
to verify it, and **stop for review**. Reuse all existing `lib/`, `infra/`, and service code.
Resolve Slack credentials only via the Secret Manager accessor; never print secret values. Keep
remediation **mocked** and every choice faithful to Section 2.

---

## 5. Tasks

### A. Complete the Slack human-in-the-loop gate  *(Member 3, with Member 2)*
Build the full Slack bot in `services/slack-bot/` (multi-stage, non-root container; Phase-1
pattern):
1. **`POST /notify`** (internal): given an `incident_id`, read the persisted brief from the incident
   store and post a **structured plain-text decision brief** to the designated Slack channel —
   **root cause, historical precedent, proposed fix, and the calculated risk level** — with
   **binary Approve / Reject buttons** (carry `incident_id` in the button value) and a link to the
   dashboard incident page.
2. **`POST /slack/interactions`**: verify the Slack request signature with `slack-signing-secret`;
   on **Approve**, publish the approval to **`opssentinel-actions`** (triggering the Phase-3
   deterministic executor) and append to `audit_log`; on **Reject**, set `status = rejected` and
   append to `audit_log`.
3. **Wire the agent hook:** connect the Phase-3 agent's node-8 "emit for human delivery" to call
   `/notify` when an incident reaches `awaiting_approval`.
Resolve `slack-bot-token` / `slack-signing-secret` from Secret Manager; give the bot a
least-privilege SA (Pub/Sub publish-to-actions only) — no Editor. Document local Slack testing
(signing secret + a tunnel for the interactions request URL). **Acceptance:** an awaiting-approval
incident posts a plain-text brief with working buttons; Approve drives the executor to `resolved`;
Reject sets `rejected`; both are audited; signatures are verified.

### B. Build the alert-storm validation harness  *(Member 3, with Member 1)*
Using the Phase-2 Alert Simulator, create a repeatable `scripts/run_storm.py` (wire `make validate`)
that publishes **≥ 50 duplicate/related signals sharing a `correlation_key`** onto
`opssentinel-alerts`, then waits and asserts the system's response. **Acceptance:** the storm runs
on demand and the harness can read back the resulting incident + queue state.

### C. Prove deduplication & zero alert loss  *(Member 2, with Member 1)*
Confirm the agent's time-windowed correlation folds the entire storm into a **single incident** with
**no dropped events** — reconcile published-vs-processed counts and verify the **DLQ is empty**.
**Acceptance:** 50+ signals → exactly one incident; no event lost; back-pressure held.

### D. Prove the autonomous-evaluation path  *(Member 2, with Member 3)*
Confirm the agent **retrieves a mathematically relevant historical runbook via the Elastic MCP
server**, **queries its baseline performance metrics via the Arize Phoenix MCP server**, sets the
correct **autonomy tier**, **formats a remediation proposal** from the synthesized data, and routes
it **to the designated Slack channel** — where a human **Approve** click triggers the **deterministic
execution path** that **updates the mocked infrastructure state and resolves the ticket**.
**Acceptance:** the full retrieve → self-evaluate → propose → Slack → Approve → execute chain runs
green on the seeded DB-pool scenario.

### E. Prove absolute observability  *(Member 2, with Member 3)*
Confirm **every phase** of the stress test appears as an **OpenInference trace** in **Arize
Phoenix**, clearly delineating **tool executions, latency metrics, and token consumption**, and that
each incident's `trace_id` deep-links correctly from the dashboard. **Acceptance:** the Phoenix UI
shows the complete trace timeline for the run; dashboard links resolve.

### F. Prove the secured, exception-free frontend  *(Member 4, with Member 1)*
Confirm the Next.js dashboard **loads behind Google Authentication**, **renders the incident state
via server-side data fetching with zero unhandled client-side exceptions**, shows the audit timeline
and reliability metrics, and links to the Phoenix trace. **Acceptance:** an unauthenticated user is
blocked; an authenticated user sees the storm's single incident render SSR cleanly with no console
exceptions.

### G. End-to-end test + demo script  *(All)*
Author an end-to-end test that asserts the Exit Criteria, plus a runnable `docs/DEMO.md`: inject the
storm → watch correlation into one incident in seconds → Gemini's structured analysis → the brief
posted to Slack → **Approve** → mocked fix applied + ticket resolved + dashboard reflects it → the
Phoenix trace timeline → the closure document written back to Elastic and retrievable. **Acceptance:**
`make validate` plus the end-to-end test pass and the demo runs start to finish.

---

## 6. Local development & verification harness

`make dev` brings up the full stack (Pub/Sub emulator + Postgres + Elastic + Phoenix + both MCP
servers + agent + Alert Simulator + slack-bot + frontend). `make validate` runs the storm and the
Exit-Criteria assertions. This mirrors the Cloud Run deployment target; it does not replace the IaC.

---

## 7. Exit Criteria — ALL must pass (verbatim intent from the spec)

1. **End-to-end tracing under load.** A synthetic alert storm of **no fewer than fifty duplicate
   signals** is ingested via the Pub/Sub queue, **dynamically deduplicated, and synthesized into a
   single incident entity without a single dropped event** — proving high availability and
   scalability under load.
2. **Autonomous evaluation works flawlessly.** The Gemini ADK agent **retrieves a mathematically
   relevant historical runbook via the Elastic MCP server**, **queries its own baseline performance
   metrics via the Arize Phoenix MCP server**, and **accurately formats a remediation proposal**
   from this synthesized data; the proposal is **routed to a designated Slack channel**, where a
   human operator **clicking Approve triggers a deterministic execution path that correctly updates
   the mocked infrastructure state and resolves the ticket**.
3. **Observability is absolute.** **Every phase** of the stress test is accurately represented as an
   **OpenInference trace in the Arize Phoenix UI** (tool executions, latency, token consumption);
   **concurrently**, the **Next.js frontend securely loads behind Google Authentication and renders
   the incident state via server-side data fetching with zero unhandled client-side exceptions**.

Meeting these signifies a viable, robust, and highly reliable initial product ready for operational
testing.

---

## 8. Validation checklist against the MVP success metrics

- **MTTD:** correlated analysis completes within **~30 seconds** of first signal.
- **Alert correlation precision:** the storm yields the targeted **~85% reduction** in duplicate
  P1/P2 incidents (one incident instead of dozens).
- **Governance held:** the Policy Engine blocked any high-risk/destructive action from auto-execution
  — human approval was required and honored.
- **Adaptive autonomy matched the data:** the autonomy tier reflected the Arize-reported accuracy
  for the category.
- **Memory loop closed:** the closure summary written to Elastic is **immediately retrievable** by
  `search_runbooks` for the next incident.

---

## 9. Deliverables

- The complete **Slack approval gate** (`/notify` plain-text brief + signature-verified
  `/slack/interactions`), wired to the agent and to `opssentinel-actions`.
- `scripts/run_storm.py` + `make validate`, and an **end-to-end test** asserting the three Exit
  Criteria.
- `docs/DEMO.md` — the start-to-finish walkthrough.
- A captured **green run** (logs / screenshots / Phoenix trace links) evidencing the Exit Criteria.

---

## 10. Guardrails — keep scope frozen

- Remediation execution stays **mocked** — no real cluster mutations (the Exit Criteria say "mocked
  infrastructure state").
- Do not add any spec-deferred feature: **Multi-Agent Collaboration, Digital Twin Simulation,
  Predictive Prevention**.
- Introduce **no new schemas or topics** — connect only what Phases 1–4 published.
- Slack remains a **binary Approve/Reject** gate with a **plain-text** brief — do not expand it into
  a richer conversational interface beyond the spec.

Keep every choice faithful to the OpsSentinel MVP specification — no technology substitutions and no
scope beyond what Phase 5 and the Exit Criteria require.
