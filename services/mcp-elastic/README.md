# mcp-elastic — Elastic MCP server (semantic memory)

An MCP server (SSE at `/sse`, plus `/health`) exposing the agent's **semantic memory** over the
Elastic knowledge base. The agent (Phase 3) connects as an MCP client via ADK's `McpToolset`.

## Tools (fixed contract)

| Tool | Behaviour |
|---|---|
| `search_runbooks(query, top_k=3)` | Encodes `query` with **all-MiniLM-L6-v2** (384-dim), runs **KNN** over the `embedding` field **and** a full-text `multi_match`, **fuses with RRF**, returns top-k `{id, title, root_cause, resolution_steps, commands, who_handled, time_to_fix, similarity_score}`. |
| `fetch_recent_logs(service, minutes=30)` | Recent log/APM lines for the service from `opssentinel-logs`. |
| `write_closure_summary(incident_id, summary, tags)` | Embeds + indexes the resolved incident into `opssentinel-knowledge` (institutional memory). |

## Why hybrid (KNN + full-text via RRF)

KNN captures semantic similarity (a query "connection pool exhausted" matches a "database
connection limit reached" runbook); full-text captures exact-term relevance. RRF
([`app/retrieval.py`](app/retrieval.py)) fuses both rankings so neither signal dominates.

## Indices

`index/opssentinel-knowledge.json` (384-dim `dense_vector`, cosine + analyzed text) and
`index/opssentinel-logs.json`. Create them with `python -m app.bootstrap` (run from repo root) or
via `make seed`.

## Run / build

```bash
# Local (via the repo docker-compose stack, which runs Elasticsearch too)
make dev

# Build the container (non-root; context = repo root; pre-bakes the embedding model)
docker build -f services/mcp-elastic/Dockerfile -t mcp-elastic .
```

Credentials (`elastic-url`, `elastic-api-key`) resolve only via `lib/secrets.get_secret()`.
