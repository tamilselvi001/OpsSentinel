# mcp-arize — Arize Phoenix MCP server (self-evaluation)

An MCP server (SSE at `/sse`, plus `/health`) exposing the **Observe Layer's** self-evaluation
signals to the agent. It returns **raw metrics only**; the agent (Phase 3) maps them to an
`autonomy_tier` and decides whether to act.

## Tools (fixed contract)

| Tool | Returns |
|---|---|
| `get_category_accuracy(category, window=30)` | Recent LLM-as-a-judge accuracy (fraction) for the category |
| `get_calibration(category)` | `|stated confidence − empirical accuracy|` (target < 0.05) |
| `is_novel_category(category)` | `true` if little/no history exists for the category |
| `log_outcome(trace_id, incident_id, approved, successful)` | Appends a result to the trace/eval history |

## Data model

Backed by the `agent_outcomes` table (Phase-2 migration `0002`). Each row is the queryable
projection of a Phoenix LLM-as-a-judge evaluation. `log_outcome` enriches the row with the
incident's `category` and `confidence` (for calibration) when the incident exists. The metric math
is pure ([`app/metrics.py`](app/metrics.py)).

## Phoenix + OpenInference

The Phoenix collector runs as its own container (local harness / cloud). The Phase-3 ADK app
applies [`lib/observability.py`](../../lib/observability.py), which configures
`openinference-instrumentation-google-adk` to export every tool call, retrieval, and generated
token as a span to Phoenix.

## Run / build

```bash
make dev    # brings up Phoenix + this server locally
docker build -f services/mcp-arize/Dockerfile -t mcp-arize .   # non-root, context = repo root
```

Credentials (`phoenix-collector-endpoint`, `phoenix-api-key`, `database-url`) resolve only via
`lib/secrets.get_secret()`.
