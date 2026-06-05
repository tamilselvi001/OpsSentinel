# agent — the ADK graph orchestrator (Agent Layer)

The cognitive brain. A **single generalized orchestrator** (no sub-agents) that pulls normalized
alerts from `opssentinel-alerts-sub`, runs the **ADK 2.0 graph** (Section 4 of the Phase-3 prompt),
and produces a fully-populated incident + execution brief for human approval.

> **Build status:** Phase 3 complete (Tasks 6.1–6.12). Deterministic logic (correlation, policy,
> autonomy, brief, graph routing, mocked execution) is unit-tested green; Gemini reasoning, the MCP
> SSE clients, the OTel/Phoenix tracing, and the Cloud Run deploy are authored (run where the live
> Gemini key / MCP servers / Docker / Terraform exist).

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
