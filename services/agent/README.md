# agent — the ADK graph orchestrator (Agent Layer)

The cognitive brain. A **single generalized orchestrator** (no sub-agents) that pulls normalized
alerts from `opssentinel-alerts-sub`, runs the **ADK 2.0 graph** (Section 4 of the Phase-3 prompt),
and produces a fully-populated incident + execution brief for human approval.

> **Build status (Phase 6, Task 4 — migrated to real Google ADK):** the agent is now built on
> **Google ADK** — an `LlmAgent` (Gemini 2.0 Flash) that is the MCP client via two `McpToolset`
> instances over **SSE** (Elastic + Arize), executed by the ADK `Runner`, instrumented to Phoenix via
> `GoogleADKInstrumentor` (see [`app/adk_app.py`](app/adk_app.py)). The **deterministic governance**
> (autonomy tier + Policy Engine + brief, in [`app/governance.py`](app/governance.py)) runs off-LLM
> after — the LLM cannot bypass the policy gate. The deterministic logic is unit-tested green
> (`test_governance`, `test_policy`, `test_autonomy`, `test_brief`, `test_correlation`,
> `test_executor`); the ADK agent's **live** run (Gemini + MCP tool calls + Phoenix spans) is
> validated on the live stack (Phase-6 Task 3/5, needs Docker + the Gemini key). The hand-rolled
> orchestrator/MCP/reasoning code has been removed.

## Graph (deterministic edges; LLM only where marked)

1. Ingest & parse *(deterministic)* — consume + validate the normalized event.
2. **Correlate** *(deterministic)* — time-windowed spatial correlation on `correlation_key`
   ([`app/correlation.py`](app/correlation.py)); a storm folds into one incident.
3. Reason *(Gemini 2.0 Flash)* — classify type + severity + team, root cause, confidence.
4. Retrieve context *(Elastic MCP)* — `fetch_recent_logs` + `search_runbooks`.
5. Synthesize recommendation *(Gemini, RAG-bound)*.
6. Self-evaluate *(Arize MCP)* — set `autonomy_tier`; degrade safely on hiccups.
7. **Policy gate** *(deterministic)* — hard rules, SLA, governance; LLM cannot bypass.
8. Brief & await approval *(deterministic)*.
9. Execute on approval *(deterministic, mocked infra)*.

## Run

```bash
make dev        # runs the agent against the emulator + Postgres + MCP servers
make signal     # feed it one incident;  make storm  -> 50+ correlated signals (one incident)
```

Credentials (`gemini-api-key`, `database-url`, `elastic-*`, Phoenix endpoint) resolve only via
`lib/secrets.get_secret()`. Dependency versions in `requirements.txt` are best-effort pins for the
ADK / google-genai / mcp stack and may need adjustment to the versions available at build time.
