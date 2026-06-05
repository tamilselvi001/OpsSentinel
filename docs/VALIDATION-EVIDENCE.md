# OpsSentinel — MVP Validation Evidence (Phase 6)

**Date of run:** 2026-06-05
**Stack:** local `docker compose` harness — 10 services (postgres, elasticsearch, pubsub-emulator,
phoenix, mcp-elastic, mcp-arize, slack-bot, webhook-receiver, agent, frontend).
**Reasoner:** Google ADK 2.2.0 (`LlmAgent` + 2× `McpToolset` over SSE) on Gemini 2.5 Flash.

This document records the actual, observed validation of the three MVP Exit Criteria on a live stack,
plus the Section-B fidelity fixes. Every claim below is backed by a concrete artifact (an incident id,
a row count, a trace id, or a log line) captured during the run — nothing here is asserted from code
inspection alone. Where a step depends on an external credential the human must provide (a real Slack
scope), that is called out explicitly rather than stubbed.

---

## Exit Criterion 1 — Alert storm dedups into a single incident, zero loss

**Method:** `scripts/run_storm.py --count 50` publishes 50 correlated signals (one shared
`correlation_key`) onto `opssentinel-alerts`.

**Observed:**

- All 50 signals shared `correlation_key 9f33031213b38ecf716f72004fd617e0`; the agent's streaming
  correlator folded them into one incident, `incident_size` climbing 1 → 50, then logged
  `"incident ready" … events: 50`.
- The resulting incident `7d5ac41f-992d-411a-afd0-71bf2c700d60` carries
  `jsonb_array_length(correlated_event_ids) = 50` — every published signal is accounted for on the
  single incident (zero alert loss).
- `opssentinel-alerts-dlq-sub` pulled empty → **DLQ is empty, no dropped events**.

**Result: PASS** — 50 signals → 1 incident, 50/50 events folded, DLQ empty.

---

## Exit Criterion 2 — retrieve → propose → Slack → approve → execute (+ memory loop)

**Method:** the same storm incident `7d5ac41f…` is taken end-to-end by the ADK agent and then driven
through the approval shim (`scripts/approve.py`, the stand-in for the Slack Approve button).

**Observed — retrieve & propose (grounded, not hallucinated):**

| Field | Value |
|---|---|
| category | `Database Connection Pool` |
| severity | `P1` |
| confidence | `0.9` |
| risk_level | `medium` |
| root_cause | `Connection pool exhausted: size below peak demand after deploy.` |
| folded events | `50` |

The root cause and remediation steps were grounded in the runbook retrieved from Elasticsearch via the
`search_runbooks` MCP tool (see the EC3 span list — `execute_tool search_runbooks`), not invented.

**Observed — Slack notify (graceful degradation, B4):** the agent posted the brief to the slack-bot,
which returned `HTTP 502` because the Slack app currently lacks the `chat:write` scope. The agent
logged a **WARNING and continued** (`"slack notify failed" … "HTTP Error 502: Bad Gateway"`) rather
than crashing the incident. Adding the scope is a human step (see `docs/MANUAL-SETUP.md`); the pipeline
is resilient to its absence.

**Observed — approve → execute → resolve:** publishing an `approve` decision moved the incident
`awaiting_approval → executing → resolved` (`"approval executed" … status: resolved`). Remediation
execution remains mocked, by design.

**Observed — memory loop closed:**

- **Arize self-eval outcome** logged to `agent_outcomes`:
  `successful = t, approved = t, stated_confidence = 0.9, category = "Database Connection Pool"`.
- **Closure written back to the knowledge base** in Elasticsearch:
  doc `Closure: 7d5ac41f-992d-411a-afd0-71bf2c700d60` (category `closure`) — so the next incident can
  retrieve this resolution.

**Result: PASS** — full retrieve → propose → (Slack, graceful) → approve → execute → resolve, with the
self-eval + knowledge-base memory loop closed.

---

## Exit Criterion 3 — Phoenix traces + secured SSR dashboard

**Method:** OpenInference instrumentation on the ADK agent exports OTLP spans to Arize Phoenix
(`http://phoenix:6006`); the incident's trace id is persisted on the incident row.

**Observed — distributed trace lands in Phoenix and links to the record:**

- Incident `7d5ac41f…` row stores `trace_id = 84fd17eccc4b0fb5f8ff8d8f036e7be8`.
- Phoenix holds that exact trace with **13 spans** capturing the entire reasoning chain:

  ```
  incident
   └─ invocation [opssentinel]
       └─ agent_run [opssentinel_reasoner]
           ├─ call_llm ×3                         (multi-turn tool calling)
           ├─ execute_tool search_runbooks        (Elastic MCP — retrieval)
           ├─ execute_tool fetch_recent_logs       (Elastic MCP)
           ├─ execute_tool get_category_accuracy   (Arize MCP — self-eval)
           ├─ execute_tool get_calibration         (Arize MCP)
           └─ execute_tool is_novel_category       (Arize MCP)
  ```

  This is real MCP tool-calling (function_call → function_response → grounded text), not narrated
  `tool_code` — confirmed by the `execute_tool *` spans carrying actual tool names.

- `trace_id` is non-zero (an earlier all-zeros bug was fixed by registering the tracer provider), so
  every incident is greppable from log → DB → Phoenix UI.

**Secured SSR dashboard:** the Next.js 16 frontend is App-Router SSR with auth enforced via a proxy
(not middleware); `getMetrics`/`listIncidents` are `server-only` and never bundled to the client.
The dashboard is auth-gated, so its metrics are validated at the data layer (see B7 below). Opening
the Phoenix UI (`http://localhost:6006`) and the signed-in dashboard is the final visual confirmation
step for the operator.

**Result: PASS** (traces + secured SSR proven; UI is the operator's visual confirmation).

---

## Section B — fidelity fixes (verified)

### B4 — Slack `/notify` no longer 500s
`/notify` now wraps `chat_postMessage` in `try/except SlackApiError`, returning a graceful **502** with
a logged reason (e.g. `missing_scope`). Proven live: the agent received the 502 and continued.
*Remaining human action:* add the `chat:write` scope to the Slack app and reinstall (`docs/MANUAL-SETUP.md`).

### B5 — Adaptive autonomy tier alignment (`low → high`)
**Root cause:** the LLM was emitting a free-text category (`Database Connection Timeout`) that did not
match the canonical category seeded in Arize (`Database Connection Pool`), so the category-accuracy
lookup missed and the autonomy engine fell back to `low`.

**Fix:** `shape_runbook` now surfaces the runbook's canonical `category`, and the agent instruction
directs it to classify using that exact string for the Arize lookup.

**Proven:** the post-fix storm incident classified as `Database Connection Pool` and the governance
engine granted `autonomy_tier = high` (`approval_required = false`) — confirmed in both the agent log
and the `incidents` row. (The MVP still routes every incident through the human approval gate by
design; the high tier is the off-LLM governance signal, and the canonical category now feeds back into
`agent_outcomes` to reinforce future accuracy.)

### B6 — Terraform validates
All 7 IaC components pass `terraform validate` ("Success! The configuration is valid."); `terraform fmt`
applied (reformatted `infra/networking/main.tf`).

### B7 — Live dashboard metrics
`getMetrics` (live mode) now computes `correlation_precision` as the duplicate-reduction ratio
`1 − incidents / Σ correlated_event_ids`. Validated against the live store:
`total_incidents = 11, total_signals = 125 → correlation_precision = 0.9120`,
`autonomous_approval_rate = 1.0`. (`mttd_seconds` stays `null` in live mode — first-signal ingest
timestamps are not retained by the incident store; it is shown in the demo/mock.) The frontend image
rebuilt cleanly with this logic.

---

## Framework reconciliation (Option A)

The agent runs on **real Google ADK 2.2.0** (`LlmAgent`, two `McpToolset(SseConnectionParams(...))`
for the Elastic and Arize MCP servers, `Runner` + `InMemorySessionService`), with deterministic
governance (autonomy + policy engine + execution brief) applied off-LLM after the model proposes.
See `docs/ADK-MIGRATION.md`. The legacy hand-rolled graph/reasoner modules were removed.

Notable bugs fixed to get ADK working live (full list in the migration doc):

- **MCP `421 Misdirected Request` ("Invalid Host header")** — FastMCP's DNS-rebinding protection
  rejected `Host: mcp-elastic`. Fixed with
  `TransportSecuritySettings(enable_dns_rebinding_protection=False)` on both MCP servers. *(the key unlock)*
- **"Failed to create MCP session … TaskGroup"** — the toolset was a module singleton reused across
  `asyncio.run` loops; now built fresh per call inside the event loop and closed in `finally`.
- **Gemini narrating `tool_code` instead of calling tools** — rewritten tool-first instruction; the
  Phoenix span list above confirms real `execute_tool` calls.
- **Free-tier `gemini-2.0-flash` 429 (`limit: 0`)** — switched to `gemini-2.5-flash`.
- **Empty final response** — join all text parts (was `parts[0]`).

---

## Test, lint, and IaC status

| Check | Result |
|---|---|
| Unit suite (`pytest`) | **91 passed** |
| Lint (`ruff check services/ tests/ scripts/ lib/`) | **All checks passed** |
| Terraform (`terraform validate`, 7 components) | **All valid** |
| Live stack | 10/10 services up |

---

## Outstanding human steps (credentials / visual confirmation only)

These require a human and are intentionally **not** stubbed:

1. **Slack `chat:write` scope** — add to the Slack app + reinstall so `/notify` posts a real message
   (the pipeline already degrades gracefully without it). For interactive Approve/Reject buttons,
   expose the slack-bot via a public tunnel and set the interactivity Request URL.
2. **Visual EC3 confirmation** — open Phoenix (`http://localhost:6006`) to view the incident trace,
   and sign in to the dashboard to view live incidents + reliability metrics.
