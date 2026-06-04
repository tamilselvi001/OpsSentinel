# PHASE 3 — ADK Agent Architecture (Member 2)

```
Project:      OpsSentinel — self-aware, agentic AI incident-response platform (Google Cloud)
Owner:        Member 2 — AI & Agent Orchestration Engineer
Source of truth: "OpsSentinel: Master Architecture and Minimum Viable Product Specification"
Build phase:  Phase 3 of 5 — "ADK Agent Architecture"
Runs after:   Phase 1 (Pub/Sub event bus + normalized event contract, the PostgreSQL incident
              store + data-access layer, Secret Manager + runtime accessor, the opssentinel-actions
              topic, the Cloud Scheduler inference cap, least-privilege IAM, the local harness) and
              Phase 2 (the Elastic MCP + Arize Phoenix MCP servers over SSE, the seeded semantic
              memory, and the OpenInference instrumentation helper).
How to use:   Open Claude Code at the repo root, ensure ./docs/mvp.pdf is present, then paste THIS
              ENTIRE FILE as your message.
```

> **Build discipline (read first).** Implement this phase **strictly as written in the
> OpsSentinel MVP specification**. Do **not** substitute technologies, re-architect, or add
> features beyond Member 2's reasoning/orchestration scope. Every component, technology choice, and
> design rationale below comes directly from the specification. If a detail is unspecified, choose
> the simplest implementation that satisfies the spec's stated intent, note the assumption, and do
> not expand scope.

---

## 1. Project context (from the specification)

OpsSentinel is structured across five processing layers: Input, Queue, **Agent**, Memory &
Self-Evaluation, and Observe. Phase 1 built the foundation; Phase 2 built the data sources (Elastic
semantic memory + Arize observability, both behind MCP servers). **Phase 3 builds the Agent Layer —
the cognitive and orchestrational brain of OpsSentinel.**

Per the spec's Agent Layer: events pulled from the Pub/Sub queue are fed into the **Google Agent
Development Kit (ADK) orchestrator**, which manages the **multi-step reasoning loop** dictating how
the **Gemini 2.0 Flash** model processes the data; Gemini **correlates the raw signals, classifies
the incident type, determines the root cause, and assigns a severity score**; and operating
alongside the LLM is a **deterministic Policy Engine** that enforces **hard rules, SLA timers, and
governance gates**, ensuring the AI **cannot circumvent human approval for high-risk actions**.

Per the spec's implementation milestones, Phase 3's core objective is to *develop the Python ADK
application and implement the Graph Workflow orchestrator to define execution nodes and integrate
MCP Toolsets*.

**What Phase 3 deliberately does NOT build** (belongs to other phases / members): the **Slack bot,
its Block Kit decision brief, and the approval webhook** (Phase 5 / Member 3 — the agent *produces*
the brief and *consumes* an approval signal, but Slack delivery and the approval button are wired in
Phase 5); the Elastic/Arize MCP servers and embeddings (already built in Phase 2); the Next.js
dashboard (Phase 4 / Member 4); and the full alert-storm validation run (Phase 5). Also out of
scope: the spec-deferred capabilities — **Multi-Agent Collaboration, Digital Twin Simulation,
Predictive Prevention** (the MVP uses a **single generalized orchestrator**, not specialized
sub-agents).

---

## 2. Non-negotiable principles Phase 3 must honor (directly from the spec)

1. **ADK 2.0 Graph-based Workflows, not template loops.** The architecture uses **graph workflows
   with explicit edges and nodes**, chosen over sequential/loop template agents for "precise,
   deterministic control." The graph **bypasses the LLM for strictly deterministic tasks** (e.g.
   parsing an incoming JSON webhook payload) and **invokes Gemini exclusively for complex
   reasoning** (e.g. synthesizing the root cause from disparate logs). This selective routing
   **minimizes token consumption, reduces latency, and mitigates hallucination** on trivial steps.
2. **Correlation happens *before* LLM invocation.** Use **time-windowed spatial correlation
   algorithms** that pre-group related signals **based on service IDs** (the Phase-1
   `correlation_key`), bundling asynchronous signals into a **singular incident context** instead of
   spawning parallel execution threads. This is the defense against alert-correlation failure and
   the engine of storm deduplication.
3. **MCP Client via `McpToolset` over SSE.** The agent **operates as the MCP Client**, connecting to
   the Phase-2 **Elastic** and **Arize Phoenix** MCP servers (independent Docker containers) using
   ADK's **`McpToolset`** over **Server-Sent Events (SSE)**. No bespoke API wrappers.
4. **Strict RAG grounding.** Recommendations are bound to retrieved historical runbooks — **the
   agent cannot act outside the bounds of retrieved historical runbooks** (the anti-hallucination
   control). The agent must `fetch_recent_logs` and `search_runbooks` via the Elastic MCP server
   and ground its proposal in those results.
5. **Adaptive autonomy via Arize.** **Prior to finalizing a recommendation**, the agent queries the
   **Arize MCP server** for its **recent historical accuracy for the incident's category**. If
   Phoenix reports the **LLM-as-a-judge accuracy for that category has degraded**, the agent
   **programmatically lowers its autonomy tier and refuses to act without explicit human
   intervention**. (Calibration target: stated-confidence-vs-empirical-accuracy variance **< 5%**.)
6. **Deterministic Policy Engine governance.** Operating alongside the LLM, it enforces **hard
   rules, SLA timers, and governance gates**; the **AI cannot circumvent human approval for
   high-risk actions**, and is restricted to **specific, non-destructive actions unless explicitly
   authorized by a senior engineer via the (Slack) approval webhook**. The LLM cannot override it.
7. **Cost & loop safety.** Deterministic ADK graph workflows **prevent infinite agent loops**, and
   the agent **respects the Phase-1 Cloud Scheduler hard daily quota** on API invocations.
8. **Performance & scope:** correlated analysis must complete within **~30 seconds (MTTD)**; the
   agent targets **>90% triage/routing accuracy** (correct category, severity, and remediation team)
   and contributes to the **85% reduction in duplicate P1/P2** during storms. Per MVP constraints,
   remediation is **constrained to Kubernetes-class infrastructure failures** and **English-only**.
9. **Single cloud (GCP); core language Python; secrets only via Secret Manager; least privilege**
   for the agent's service account (Pub/Sub subscribe + Cloud SQL client + Secret Manager accessor;
   **no project Editor**).
10. **Absolute observability.** Instrument the ADK app with the Phase-2 **`openinference-
    instrumentation-google-adk`** helper so **every tool call, context retrieval, and generated
    token is a discrete trace span** in **Phoenix**; persist the resulting `trace_id` on the
    incident.

---

## 3. Interfaces Phase 3 consumes and produces

**Consumes (already built):**
- Phase 1: pull subscription `opssentinel-alerts-sub`; the normalized **alert event** model and
  Pub/Sub helpers (`lib/events.py`, `lib/pubsub.py`); the **PostgreSQL incident store** + data-
  access layer (`lib/db.py`: `upsert_incident`, `get_incident`, `add_event`, `append_audit`); the
  `sla_policies` seed; the **`opssentinel-actions`** topic (approval/execution channel); the
  **Secret Manager** accessor (`lib/secrets.py`, secret `gemini-api-key`); the **Cloud Scheduler**
  inference cap; structured logging (`lib/logging.py`).
- Phase 2: **Elastic MCP** SSE `http://mcp-elastic:8080/sse` — `search_runbooks`,
  `fetch_recent_logs`, `write_closure_summary`; **Arize Phoenix MCP** SSE
  `http://mcp-arize:8081/sse` — `get_category_accuracy`, `get_calibration`, `is_novel_category`,
  `log_outcome`; the OpenInference instrumentation helper (`lib/observability.py`).

**Produces:**
- Fully-populated `incidents` rows advanced through their lifecycle (`open → correlating →
  analyzing → awaiting_approval → approved → executing → resolved | rejected | escalated`), with
  `category`, `severity`, remediation-team assignment, `root_cause`, `confidence`,
  `correlated_event_ids`, `recommended_action`, `historical_match_ids`, `risk_level`,
  `autonomy_tier`, and `trace_id`.
- A **structured execution brief** (root cause, historical precedent, proposed fix steps, risk
  level, autonomy/caution note) persisted on the incident for human delivery — **the Slack delivery
  itself is wired in Phase 5**.
- On approval: closure written back via Elastic `write_closure_summary` and the outcome recorded via
  Arize `log_outcome`; on the Observe side, complete **OpenInference traces** in Phoenix.

The `autonomy_tier` enum (`high | moderate | low`), the incident schema, and the normalized event
contract were all published by Phases 1–2; reuse them, do not redefine.

---

## 4. The ADK 2.0 graph workflow (map each node to the spec)

Implement the orchestrator as an **explicit graph** with deterministic edges and conditional
branches. Keep deterministic nodes **off the LLM**; invoke **Gemini 2.0 Flash** only where marked.

1. **Ingest & parse** *(deterministic)* — pull from `opssentinel-alerts-sub`; validate/parse the
   normalized event. *(The spec's canonical "bypass the LLM to parse a JSON webhook payload.")*
2. **Correlate** *(deterministic)* — **time-windowed spatial correlation on `correlation_key` /
   service IDs**, folding related/duplicate signals into a **single incident context**; upsert the
   incident (`status = correlating`). *(Storm → one incident, before any LLM call.)*
3. **Reason** *(Gemini 2.0 Flash)* — correlate the raw signals, **classify the incident type**,
   **determine the root cause**, **assign a severity score**, and **assign the remediation team**;
   emit a calibrated confidence. *(`status = analyzing`.)*
4. **Retrieve context** *(Elastic MCP tool calls, graph-orchestrated)* —
   `fetch_recent_logs(service, 30)` and `search_runbooks(<incident context>, top_k=3)`. *(RAG
   grounding: last 30 minutes of logs + closest historical match via vector search.)*
5. **Synthesize recommendation** *(Gemini, RAG-bound)* — adapt the retrieved runbook to *this*
   incident into a `recommended_action` (ordered steps) with a `risk_level`; **do not propose
   anything outside the retrieved runbooks**.
6. **Self-evaluate / adaptive autonomy** *(Arize MCP tool calls)* — `get_category_accuracy`
   (+ `get_calibration`, `is_novel_category`); set `autonomy_tier`. If accuracy for the category has
   **degraded** (or it is novel), **lower the tier and require human intervention**.
7. **Policy gate** *(deterministic Policy Engine)* — apply hard rules, SLA timers, and governance
   gates; force human approval for **high-risk actions**; allow only **non-destructive** actions
   absent explicit authorization. The LLM cannot bypass this node.
8. **Brief & await approval** *(deterministic)* — generate the structured execution brief (root
   cause, historical precedent, proposed fix, risk, autonomy note); persist incident as
   `awaiting_approval`; emit it for human delivery. *(Slack delivery + the approval button are wired
   in Phase 5; here the brief is produced and persisted.)*
9. **Execute on approval** *(deterministic)* — consume the approval from `opssentinel-actions`; run
   the **deterministic execution path**: update the **mocked infrastructure state** (e.g. restart
   the connection pool, increase max connections), **resolve the mocked ServiceNow ticket**, call
   Elastic `write_closure_summary`, and call Arize `log_outcome`; set `status = resolved`. On reject
   → `status = rejected` + audit entry.

---

## 5. Working method for Claude Code

Build in **small, reviewable increments**. After each numbered task: summarize what you created,
show how to verify it, and **stop for review** before continuing. Reuse all Phase-1/2 `lib/` helpers
and `infra/` patterns; connect to MCP servers and infrastructure using the exact contracts in
Section 3. Resolve the Gemini key only through the secrets accessor; never print secret values. Keep
deterministic nodes off the LLM, and keep every choice faithful to Section 2.

---

## 6. Tasks

### Task 6.1 — Agent scaffold + Pub/Sub consumer
Create `services/agent/` (multi-stage, non-root Dockerfile, Phase-1 pattern). Implement a resilient
consumer on `opssentinel-alerts-sub` with **bounded concurrency (back-pressure), ack/nack, and DLQ**
behavior, so the reasoning engine consumes at a sustainable, controlled rate. Add it to the local
harness. **Acceptance:** the agent starts, connects to the subscription, and logs a received
normalized event.

### Task 6.2 — MCP client wiring via `McpToolset` (SSE)
Configure ADK **`McpToolset`** clients to the Phase-2 **Elastic** and **Arize** MCP servers over
**SSE** and expose their tools to the graph. Handle connection retries/fallbacks gracefully: a
tracing/eval hiccup must **never crash incident handling** — instead **degrade to a safe lower
autonomy tier**. **Acceptance:** from the agent, `search_runbooks`, `fetch_recent_logs`, and the
four Arize tools are callable over SSE and return the Phase-2 shapes.

### Task 6.3 — The ADK 2.0 graph orchestrator
Implement nodes 1–9 from Section 4 as an **explicit ADK graph** with deterministic edges and
conditional branches (low-confidence/novel → human-review branch; high-risk → mandatory-approval
branch). Keep deterministic nodes (ingest/parse, correlate, policy gate, brief, execute) off the
LLM. **Acceptance:** a single simulated event traverses the graph end-to-end and reaches
`awaiting_approval`.

### Task 6.4 — Signal correlation (deterministic, pre-LLM)
Implement the **time-windowed spatial correlation** in node 2: group events arriving within a
configurable window that share `correlation_key` / service+infra into **one** incident; never spawn
parallel reasoning per duplicate. **Acceptance:** feeding many related signals yields exactly one
incident (verified in the next task at storm scale).

### Task 6.5 — Gemini 2.0 Flash reasoning (nodes 3 & 5)
Integrate **Gemini 2.0 Flash** for classification (type + severity + remediation team + calibrated
confidence), root-cause determination, and the RAG-bound recommendation synthesis. Use structured
output / strict schemas so each node returns validated objects; centralize prompts in
`services/agent/prompts/`. **Acceptance:** for the seeded DB-pool incident, Gemini returns a
sensible category/severity/team, a root cause, and a recommendation grounded in the retrieved
runbook.

### Task 6.6 — Deterministic Policy Engine (node 7)
In `services/agent/policy/`, implement the Policy Engine independent of the LLM: **hard rules, SLA
timers (deadlines from the Phase-1 `sla_policies`; mark `escalated` when breached — periodic check
drivable by the Phase-1 Cloud Scheduler), and governance gates** that force human approval for
**high-risk** actions and restrict the agent to **non-destructive** actions absent explicit
authorization. The LLM **cannot** override these gates. **Acceptance:** a high-risk recommendation
is forced to `awaiting_approval`; a breached SLA marks `escalated`.

### Task 6.7 — Adaptive autonomy loop (node 6)
Implement the loop that calls the Arize MCP tools and sets `autonomy_tier`, **lowering it (and
requiring human intervention) when category accuracy has degraded or the category is novel**.
**Acceptance:** the seeded ~91% DB category yields a high/assertive tier; the seeded degraded/novel
category lowers the tier and routes to human review.

### Task 6.8 — Brief generation + persistence + audit (node 8)
Build the structured execution brief (root cause, historical precedent, proposed fix steps, risk,
autonomy note); persist the fully-populated incident as `awaiting_approval`; append an `audit_log`
entry for **every** decision and state change (governance-grade trail). **Acceptance:** the incident
row and audit timeline are complete and human-readable; the brief is retrievable for Phase-5 Slack
delivery.

### Task 6.9 — Deterministic execution path on approval (node 9, mocked infra)
Consume approvals from **`opssentinel-actions`** and run the **idempotent deterministic execution
path**: update a **mocked infrastructure state** (a small in-repo mock representing the
pool/ServiceNow ticket), call Elastic `write_closure_summary`, call Arize `log_outcome`, and set
`status = resolved`; on reject → `status = rejected` + audit. Provide a **test-only approval shim**
(publish to `opssentinel-actions` via a CLI / `make approve INCIDENT=<id>`) so the full path is
exercisable **before** the Phase-5 Slack wiring. **Acceptance:** simulating an approval transitions
the incident to `resolved`, writes a closure document to Elastic, and logs the outcome to Arize.

### Task 6.10 — OpenInference instrumentation → Phoenix (cross-cutting)
Apply the Phase-2 `lib/observability.py` helper so the whole ADK run is traced: **every tool call,
context retrieval, and token** becomes a discrete span in **Phoenix**. Store the `trace_id` on the
incident for the Phase-4 dashboard deep-link. **Acceptance:** a full run appears as an OpenInference
trace in Phoenix with tool executions, latency, and token counts; the `trace_id` is persisted.

### Task 6.11 — Deploy config, secrets & least-privilege IAM
In `infra/cloud-run/`, add the agent's Cloud Run deploy configuration, pulling `gemini-api-key`,
`database-url`, `elastic-url`/`elastic-api-key`, and the Phoenix endpoint from **Secret Manager** via
the Phase-1 accessor. In `infra/iam/`, add the agent's **dedicated service account with a custom
least-privilege role** (Pub/Sub subscribe + publish-to-actions, Cloud SQL client, Secret Manager
accessor) — **no Editor**, **non-destructive by default**. **Acceptance:** the deploy config
validates; credentials resolve only via Secret Manager; IAM is minimal and enumerated.

### Task 6.12 — Tests
Unit-test the deterministic nodes (correlation folds a storm into one incident; policy gates force
approval for high-risk; SLA breach escalates). Provide an integration test that drives one simulated
incident end-to-end (mock or live Gemini) and asserts it reaches `awaiting_approval` with a retrieved
runbook, an `autonomy_tier`, a `risk_level`, and a `trace_id`; then simulate approval and assert
`resolved` + closure write + outcome log. **Acceptance:** the suite passes locally.

---

## 7. Local development & verification harness

Add the **agent** container to the Phase-1/2 `docker-compose.yml` so `make dev` now also runs the
agent against the emulated Pub/Sub + Postgres and the Phase-2 MCP servers. Use the Phase-2 Alert
Simulator (`make signal`, `make storm`) to feed it and the `make approve INCIDENT=<id>` shim to
exercise execution. This harness mirrors the GCP deployment target; it does not replace the Cloud Run
IaC.

---

## 8. Definition of Done — Phase 3 is complete when

- The agent consumes from `opssentinel-alerts-sub` (back-pressure/ack/DLQ) and connects to both MCP
  servers over **SSE** via `McpToolset`.
- The **ADK 2.0 graph** runs with deterministic nodes off the LLM and **Gemini 2.0 Flash** only for
  classification/root-cause/recommendation.
- A simulated **DB-pool incident** flows end-to-end to `awaiting_approval` with a synthesized root
  cause, a **RAG-grounded** recommendation from a retrieved runbook, an `autonomy_tier` set from
  Arize, a `risk_level`, and a persisted `trace_id`.
- A **50+-signal storm** is **deduplicated into a single incident** (no parallel reasoning, no
  dropped events).
- The **Policy Engine** forces human approval for high-risk actions, restricts the agent to
  non-destructive actions, and escalates SLA breaches; the LLM cannot bypass it.
- Simulating an approval runs the **deterministic execution path**: mocked infra resolved, Elastic
  `write_closure_summary` written, Arize `log_outcome` recorded, `status = resolved`.
- Every run appears as an **OpenInference trace** in **Phoenix**.
- The agent deploy config validates; credentials come only from Secret Manager; least-privilege IAM
  (no Editor) is in place.

---

## 9. Handoff to Phases 4 & 5

Phase 3 hands the team: a working agent that produces fully-populated incidents (the `/api`-shaped
read model the **Phase-4** dashboard renders), complete **Arize/Phoenix traces** (with `trace_id`
deep-links), the **execution brief** persisted on each incident, and the **`opssentinel-actions`**
execution path — ready for **Phase 5** to wire the **Slack** decision brief + approval button and to
run the full **alert-storm** validation.

---

## 10. Guardrails — do NOT build in Phase 3

- No Slack bot, Block Kit brief, or approval webhook (Phase 5 / Member 3) — produce + persist the
  brief and consume an approval signal only.
- No Elastic/Arize MCP server internals or embeddings (built in Phase 2) — call them as a client.
- No Next.js dashboard (Phase 4).
- No real cluster mutations — the execution path stays **mocked**.
- No multiple/specialized sub-agents — a **single generalized orchestrator** only.
- None of the spec-deferred features: Multi-Agent Collaboration, Digital Twin Simulation,
  Predictive Prevention.

Keep every choice faithful to the OpsSentinel MVP specification — no technology substitutions and no
scope beyond Member 2's reasoning and orchestration responsibilities for this phase.
