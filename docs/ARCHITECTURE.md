# OpsSentinel — Architecture

Drop the diagram below into your slide deck: paste the Mermaid block into
[mermaid.live](https://mermaid.live) and export **PNG/SVG**, or render it inline on GitHub.
A plain-English legend follows for narration.

## System diagram

```mermaid
flowchart LR
    subgraph ING["1 · Ingestion"]
        SRC["Monitoring sources<br/>(alert-simulator)"]
        ALERTS(["Pub/Sub<br/>opssentinel-alerts"])
        DLQ(["Pub/Sub DLQ<br/>(zero-loss guard)"])
        SRC --> ALERTS
        ALERTS -. poison .-> DLQ
    end

    subgraph AGENT["2 · Agent — Google ADK"]
        CORR["Time-windowed<br/>correlation<br/>(storm to 1 incident)"]
        LLM["LlmAgent · Gemini 2.5 Flash<br/>retrieve to propose"]
        GOV["Deterministic governance<br/>autonomy + policy engine<br/>(off-LLM)"]
        EXEC["Executor<br/>(remediation mocked)"]
        CORR --> LLM --> GOV
    end

    subgraph TOOLS["3 · MCP tool servers (SSE)"]
        MELAS["mcp-elastic"]
        MARIZE["mcp-arize"]
        ES[("Elasticsearch<br/>runbooks + closures<br/>hybrid KNN+RRF")]
        MELAS <--> ES
    end

    subgraph STORE["4 · State"]
        PG[("PostgreSQL<br/>incidents · audit<br/>agent_outcomes")]
        ACTIONS(["Pub/Sub<br/>opssentinel-actions"])
    end

    subgraph HITL["5 · Human-in-the-loop"]
        SLACK["slack-bot<br/>Approve / Reject<br/>(signature-verified)"]
    end

    subgraph OBS["6 · Observability"]
        PHX["Arize Phoenix<br/>OpenInference traces"]
    end

    subgraph UI["7 · Console"]
        FE["Next.js 16 SSR dashboard<br/>Google OAuth · live metrics"]
    end

    ALERTS --> CORR
    LLM <-->|search_runbooks<br/>fetch_recent_logs| MELAS
    LLM <-->|accuracy · calibration<br/>novelty| MARIZE
    MARIZE <--> PG
    GOV --> PG
    GOV -->|notify| SLACK
    SLACK -->|approve| ACTIONS
    ACTIONS --> EXEC
    EXEC -->|resolve| PG
    EXEC -->|write closure| ES
    EXEC -->|log_outcome| MARIZE
    AGENT -.OTLP spans.-> PHX
    FE <-->|read-only| PG
    FE -.trace deep-link.-> PHX

    classDef store fill:#1f2937,stroke:#6b7280,color:#e5e7eb;
    classDef bus fill:#0e7490,stroke:#155e75,color:#ecfeff;
    class ES,PG store;
    class ALERTS,DLQ,ACTIONS bus;
```

## How to narrate it (the data's journey)

1. **Ingestion** — monitoring signals land on the `opssentinel-alerts` Pub/Sub topic. A dead-letter
   queue catches anything unprocessable, so the pipeline can prove **zero alert loss**.
2. **Correlate** — the agent's time-windowed correlator folds a storm of 50+ related signals into a
   **single incident** (Exit Criterion 1).
3. **Reason (RAG, real tool-use)** — a Google **ADK `LlmAgent`** on Gemini 2.5 Flash calls two
   **MCP tool servers** over SSE: `mcp-elastic` does hybrid (KNN + RRF) runbook retrieval and log
   lookup from Elasticsearch; `mcp-arize` returns the agent's own historical category accuracy,
   calibration, and novelty. The proposal's root cause and fix are **grounded in the retrieved
   runbook**, not hallucinated.
4. **Govern (safe autonomy)** — deterministic, off-LLM logic sets the **autonomy tier** and policy
   (severity floor, approval requirement). The decision is auditable and not at the model's mercy.
5. **Human-in-the-loop** — the brief posts to Slack with **Approve / Reject** buttons
   (signature-verified). Approval flows back through the `opssentinel-actions` topic.
6. **Execute + remember** — the executor runs the (mocked) remediation, resolves the incident, writes
   a **closure summary back into Elasticsearch**, and logs the **outcome to Arize** — closing the
   memory loop so the next incident retrieves this resolution (Exit Criterion 2).
7. **Observe + render** — every step is an **OpenInference trace in Phoenix**; the **Next.js SSR
   dashboard** (Google-authenticated) renders live incidents and reliability metrics and deep-links
   each incident to its Phoenix trace (Exit Criterion 3).

> Everything ships to **Google Cloud** via Terraform (Cloud Run, Cloud SQL, Pub/Sub, Secret Manager,
> a global load balancer + Cloud CDN) — see `docs/DEPLOYMENT-GCP.md`.
