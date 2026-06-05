# Option A — Migrate the agent to real Google ADK (spec fidelity)

**Decision: Option A is chosen.** The spec mandates **Google ADK (Graph Workflows)** with
**`McpToolset`** and the `openinference-instrumentation-google-adk` tracer. Today the agent is a
hand-rolled orchestrator (`services/agent/app/graph.py`) that calls `google-genai` directly and uses
the raw `mcp` SDK — functionally faithful, but it does not use the ADK framework. This document is
the precise plan to fix that. An AI agent should implement it as **Task 4** of
`PROMPTS/06-phase6-integration-validation-and-fidelity.md`.

> **Golden rule that does not change:** the **Policy Engine and the autonomy-tier decision stay
> deterministic** (plain Python, `services/agent/policy/` and `app/autonomy.py`). The LLM gathers
> data and proposes; it must **never** be able to bypass the policy gate. Remediation execution
> stays **mocked**.

---

## 0. Confirmed ADK API (verified against google-adk 2.2.0, installed in this repo's .venv)

```python
from google.adk.agents import LlmAgent, SequentialAgent, BaseAgent          # workflow + reasoning agents
from google.adk.tools.mcp_tool import McpToolset, SseConnectionParams        # MCP client over SSE
from google.adk.runners import Runner, InMemoryRunner                        # executes an agent
from google.adk.sessions import InMemorySessionService                       # session state

# An MCP toolset that connects to one of the Phase-2 MCP servers over SSE and exposes its tools:
elastic_tools = McpToolset(
    connection_params=SseConnectionParams(url="http://mcp-elastic:8080/sse"),
    # optional: tool_filter=["search_runbooks", "fetch_recent_logs", "write_closure_summary"]
)
arize_tools = McpToolset(
    connection_params=SseConnectionParams(url="http://mcp-arize:8081/sse"),
)

# An LLM reasoning node (Gemini 2.0 Flash) that can call those MCP tools:
reasoner = LlmAgent(
    name="reasoner",
    model="gemini-2.0-flash",
    instruction="<the classify + RAG-grounded recommend prompt>",
    tools=[elastic_tools, arize_tools],
    output_schema=...,        # a pydantic model for the structured proposal (optional)
)
```

- A **deterministic node** is a `BaseAgent` subclass that implements `async def _run_async_impl(self,
  ctx) -> AsyncGenerator[Event, None]` and does NOT call the LLM (this is the spec's "bypass the LLM
  for deterministic tasks").
- A **graph/sequence** is a `SequentialAgent(name=..., sub_agents=[node1, node2, ...])` (use
  `ParallelAgent`/`LoopAgent` only if a node genuinely needs it; the OpsSentinel flow is sequential
  with conditional branches you express inside the deterministic nodes).
- **Model key wiring:** ADK reads `GOOGLE_API_KEY` and `GOOGLE_GENAI_USE_VERTEXAI`. In the agent
  container set `GOOGLE_API_KEY` = your Gemini key (the repo already has `GEMINI_API_KEY`; map it) and
  `GOOGLE_GENAI_USE_VERTEXAI=FALSE` so ADK uses the AI-Studio Gemini API, not Vertex.

---

## 1. Dependencies (services/agent/requirements.txt)

Bump/confirm:
```
google-adk>=2.2,<3
google-genai>=1.0
mcp>=1.2.0
openinference-instrumentation-google-adk>=0.1
opentelemetry-sdk>=1.24
opentelemetry-exporter-otlp-proto-http>=1.24
# (keep the existing pubsub / secret-manager / sqlalchemy / psycopg / pydantic pins)
```
Rebuild the agent image after editing.

---

## 2. Target architecture — map the spec's nodes onto ADK

Keep every existing deterministic module; wrap them as ADK nodes. The reasoning + MCP tool calls move
into ADK.

| Spec node | ADK construct | Reuses |
|---|---|---|
| 1 Ingest/parse | stays in `app/consumer.py` (Pub/Sub) — feeds the graph | `lib/events`, `lib/pubsub` |
| 2 Correlate (deterministic, pre-LLM) | `CorrelationNode(BaseAgent)` OR stays upstream in the consumer | `app/correlation.py` |
| 3 Reason (classify) + 4 Retrieve + 5 Synthesize | **`LlmAgent`** (`model="gemini-2.0-flash"`) with `tools=[elastic_tools, arize_tools]` — it calls `fetch_recent_logs`, `search_runbooks`, and the Arize metric tools, then returns a structured proposal | prompts in `app/prompts/`; `output_schema` from `app/models.py` |
| 6 Self-evaluate → autonomy tier | **deterministic** — map the Arize metrics the LLM gathered to a tier | `app/autonomy.py` |
| 7 Policy gate | `PolicyGateNode(BaseAgent)` — **deterministic, LLM cannot bypass** | `policy/engine.py`, `policy/sla.py` |
| 8 Brief + persist + Slack notify | `BriefNode(BaseAgent)` | `app/brief.py`, `app/persistence.py`, `SlackNotifier` |
| 9 Execute on approval | unchanged — separate consumer | `app/executor.py`, `app/execution_consumer.py` |

Compose the reasoning path as, e.g.:
```python
root = SequentialAgent(
    name="opssentinel_incident_graph",
    sub_agents=[reasoner, GovernanceNode(...)],   # GovernanceNode = autonomy + policy + brief + notify
)
```
The `reasoner` is the LLM agent (with the two McpToolsets); `GovernanceNode` is one deterministic
`BaseAgent` that runs `decide_autonomy` → `policy_engine.evaluate` → `build_execution_brief` →
`persist` → `SlackNotifier.notify`. (Splitting it into separate deterministic nodes is fine too.)

> **RAG grounding:** keep the existing `_bind_to_retrieved` rule — the recommendation must reference a
> runbook the Elastic toolset actually returned. Put this enforcement in the deterministic node, not
> the LLM, so it cannot be hallucinated away.

---

## 3. Files

- **New:** `services/agent/app/adk_app.py` — builds the McpToolsets, the `LlmAgent`, the deterministic
  `BaseAgent` nodes, the `SequentialAgent`, and a `Runner(agent=root, session_service=
  InMemorySessionService(), app_name="opssentinel")`. Expose `run_incident(context) -> GraphResult`
  that feeds one correlated `IncidentContext` through the runner and returns the same `GraphResult`
  shape the rest of the code already expects.
- **Refactor:** `app/runtime.py` — `build_deps()`/the entrypoint now constructs the ADK app instead
  of the hand-rolled `GraphDeps`; `enable_tracing()` stays (see §4).
- **Keep as-is and reuse:** `app/correlation.py`, `app/autonomy.py`, `policy/*`, `app/brief.py`,
  `app/persistence.py`, `app/executor.py`, `app/mock_infra.py`, `app/models.py`, `app/consumer.py`,
  `app/execution_consumer.py`, `SlackNotifier`.
- **Retire or shrink:** the hand-rolled `app/graph.py` and `app/mcp_clients.py` / `app/reasoning.py`
  are superseded by ADK (`McpToolset` replaces `mcp_clients`; `LlmAgent` replaces `reasoning`). You
  may keep `graph.py`'s deterministic helpers if the deterministic nodes import them, but the LLM/MCP
  parts should now go through ADK. Delete dead code so `google-adk` is genuinely the agent framework.

Keep the existing **unit tests green** — the deterministic modules (`correlation`, `policy`,
`autonomy`, `brief`, `executor`, `mock_infra`) are unchanged, so `tests/test_correlation.py`,
`test_policy.py`, `test_autonomy.py`, `test_brief.py`, `test_executor.py`, `test_mock_infra.py`,
`test_storm_dedup.py` should still pass. (`tests/test_graph.py` tests the old orchestrator — port it
to assert the new ADK path reaches `awaiting_approval` with an autonomy tier, risk level, retrieved
runbook, and a `trace_id`, using a fake/echo model so it runs without a live Gemini key.)

---

## 4. Tracing → Phoenix (this is why Option A matters for EC3)

In `lib/observability.py` (or agent startup), apply the ADK instrumentor BEFORE building agents:
```python
from openinference.instrumentation.google_adk import GoogleADKInstrumentor
# configure the OTel TracerProvider → Phoenix OTLP endpoint (already in configure_tracing)
GoogleADKInstrumentor().instrument(tracer_provider=provider)
```
Because the agent now actually runs on ADK, this auto-captures **every tool call, model call, and
token count** as OpenInference spans in Phoenix — satisfying Exit Criterion 3. Persist the run's
`trace_id` on the incident (the dashboard deep-links it).

---

## 5. How to verify

1. **Lint + unit tests (no live services):** `ruff check . && pytest`. The deterministic suite stays
   green; the ported `test_graph` runs with a fake model.
2. **Construction smoke test (no Gemini key needed):** a test that imports `adk_app`, builds the
   McpToolsets + `LlmAgent` + `SequentialAgent` + `Runner`, and asserts they construct without error.
3. **Live run (needs the stack + Gemini key):** `make dev`, `make seed`, `make signal` → confirm in
   Phoenix that the run is a full ADK trace (tool spans for `search_runbooks` / `fetch_recent_logs` /
   the Arize tools, model spans with token counts), and the incident reaches `awaiting_approval`.

**Acceptance:** the agent is built on ADK (`LlmAgent` + `McpToolset` + `SequentialAgent` + `Runner`);
deterministic governance is unchanged and still unit-tested; a live run shows real ADK/OpenInference
spans in Phoenix. The hand-rolled MCP/LLM code is removed so ADK is genuinely the framework.

---

## 6. Gotchas

- ADK agents are **async**; the runner drives them with `run_async`. Your Pub/Sub consumer is sync —
  bridge with `asyncio.run(...)` per incident (or run an event loop in the consumer thread).
- `SseConnectionParams` is a pydantic model: pass `url=` (and `headers=`/`timeout=` if needed).
- The MCP servers must be **up and reachable** at the SSE URLs before the McpToolset lists tools; ADK
  connects lazily, but the first incident will fail if the servers aren't running — that's expected,
  fix by ordering `make dev` startup / health-gating.
- Set `GOOGLE_API_KEY` (= your Gemini key) and `GOOGLE_GENAI_USE_VERTEXAI=FALSE` in the agent env.
- Keep the autonomy/policy decisions in Python — do **not** turn the Policy Engine into an LLM tool.
