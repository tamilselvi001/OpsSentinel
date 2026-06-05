# OpsSentinel — end-to-end demo (Phase 5)

This walks the one workflow that proves the MVP: **cascading alert storm → single incident →
RAG-grounded proposal → Slack approval → mocked remediation → closure + outcome logged → traced in
Phoenix → rendered on the Google-authenticated dashboard.**

> Local prerequisites: Docker (compose stack), and the secrets in `.env` (`GEMINI_API_KEY`,
> `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `GOOGLE_OAUTH_CLIENT_ID`). Without Docker, run the unit
> suite (`make test`) which proves the deterministic logic of every step below.

## 0. Bring up the full stack

```bash
cp .env.example .env          # fill in real secret values
make dev                      # emulator + Postgres + Elastic + Phoenix + MCPs + agent + slack-bot + frontend
make migrate                  # incident store + agent_outcomes
make seed                     # runbooks (incl. the DB-pool runbook), logs, ~91% Arize history
```

## 1. Inject a cascading alert storm

```bash
make storm                    # 50+ signals sharing one correlation_key → opssentinel-alerts
# or the validating harness:
make validate                 # publishes the storm, then reconciles counts + asserts the DLQ is empty
```

**Expect (Exit Criterion 1):** the agent's time-windowed correlation folds all 50+ signals into
**one** incident — no dropped events, DLQ empty. (`tests/test_storm_dedup.py` proves this at the
logic level: 50 signals → 1 incident, every event id retained.)

## 2. Watch the agent reason (within ~30s)

The agent: classifies the incident with **Gemini 2.0 Flash**; `fetch_recent_logs` + `search_runbooks`
over the **Elastic MCP** server retrieve the closest runbook (a query worded "connection pool
exhausted" still matches the "Database Connection Limit Reached" runbook via **RRF**); the **Arize
MCP** server reports ~91% category accuracy → **autonomy tier**; the **Policy Engine** floors
severity to P1 (production + payment) and, because the fix is high-risk, **requires human approval**;
the incident is persisted `awaiting_approval` with a `trace_id`.

## 3. Approve in Slack

The agent calls the slack-bot `/notify`; a **plain-text brief** (root cause, historical precedent,
proposed fix, risk level) posts to the channel with **Approve / Reject** buttons.

- **Approve** → the bot (after **verifying the Slack signature**) publishes to `opssentinel-actions`.
- Without Slack configured, simulate it: `make approve INCIDENT=<incident_id>`.

## 4. Deterministic execution (mocked)

The Phase-3 executor consumes the approval and runs the **idempotent** path: updates the **mocked**
infrastructure (restart pool / raise limit), **resolves the mocked ServiceNow ticket**, writes the
**closure back to Elastic** (`write_closure_summary` — immediately retrievable by the next
`search_runbooks`), logs the **outcome to Arize** (`log_outcome`), and sets `status = resolved`.

## 5. Observe + render

- **Phoenix** shows the full **OpenInference trace** — every tool call, latency, and token count.
- The **dashboard** (http://localhost:3000) loads behind **Google sign-in**, server-renders the
  single incident, its audit timeline, and the reliability metrics, and deep-links the `trace_id` to
  Phoenix — **zero unhandled client-side exceptions**.

## Exit Criteria → where each is proven

| Exit Criterion | Proof |
|---|---|
| 1. Storm dedups into one incident, zero loss | `make validate` + `tests/test_storm_dedup.py` |
| 2. Retrieve → self-evaluate → propose → Slack → Approve → execute | `tests/test_graph.py`, `tests/test_slack_*`, `tests/test_executor.py` |
| 3. Absolute observability + secured exception-free frontend | Phoenix trace UI + `npm run build` (SSR) + auth guard |
