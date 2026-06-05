# OpsSentinel — Live Demo Runbook

The one workflow that proves the MVP, framed as **three acts that map to the three Exit Criteria**:

> **cascading alert storm → one correlated incident → RAG-grounded proposal → human approval →
> mocked remediation → memory loop (Arize + Elastic) → Phoenix trace → secured live dashboard.**

It runs on **real Google ADK** (`LlmAgent` + MCP tool servers) on **Gemini 2.5 Flash**. See
`docs/ARCHITECTURE.md` for the system diagram and `docs/VALIDATION-EVIDENCE.md` for the captured
evidence of a green run.

---

## 0. Stage setup (do this BEFORE you present)

```bash
docker compose up -d            # bring up all 10 services
# first time only:
python scripts/bootstrap_pubsub.py     # topics + subscriptions on the emulator
alembic upgrade head                   # incident store + agent_outcomes
python scripts/seed.py                 # runbooks (incl. the DB-pool runbook) + recent logs
python scripts/seed_arize.py           # ~91% Arize accuracy history (canonical categories)
```

Prerequisites in `.env`: `GEMINI_API_KEY` (or `GOOGLE_API_KEY`), `GOOGLE_OAUTH_CLIENT_ID`, and — only
if you want real Slack posts — `SLACK_BOT_TOKEN` (bot needs the **`chat:write`** scope) +
`SLACK_SIGNING_SECRET`. The dashboard is set to **live** mode (`OPSSENTINEL_DATA_MODE=live`).

**Pre-flight checklist for the stage:**
- [ ] `docker compose ps` → all services up.
- [ ] Sign in to `http://localhost:3000` once (add `http://localhost:3000` to the OAuth client's
      Authorized JavaScript origins first) so you're not doing OAuth live.
- [ ] Pre-open browser tabs: `/incidents`, `/reliability`, and Phoenix `http://localhost:6006`.
- [ ] **Record a screen capture of a full green run as backup** — never demo live without one.

---

## 1. The one-command demo (recommended for stage)

Run this and narrate the three acts as they print:

```bash
python scripts/demo.py
```

It fires a 50-signal storm, waits for the agent, prints the grounded proposal, approves it, confirms
the memory loop, and prints the Phoenix + dashboard deep-links. Real captured output:

```
  ACT 1 — An alert storm hits   [EC1 · correlate & dedup]
  Published 50 correlated signals (correlation_key 9f3303...)
  ✓ 50 signals → 1 incident (50 events folded, 0 lost)
  ✓ DLQ empty — zero alert loss

  ACT 2 — The agent reasons, then we govern it   [EC2 · retrieve → propose → approve → execute]
    Incident:        a698cfcd-c978-4408-a549-a9525f76fa4a
    Category:        Database Connection Pool
    Severity:        P1
    Confidence:      0.91
    Autonomy tier:   high
    Root cause:      Connection pool exhausted: size below peak demand after deploy.
  ✓ Remediation executed (mocked) → incident RESOLVED
  ✓ Memory loop closed:
      • Arize self-eval logged → successful=True, approved=True, category='Database Connection Pool'
      • Closure summary written back to Elasticsearch (retrievable by the next incident)

  ACT 3 — Every decision is observable   [EC3 · Phoenix trace + secured dashboard]
      Phoenix trace  -> http://localhost:6006/projects?traceId=b879bbeb...
      Dashboard      -> http://localhost:3000/incidents/a698cfcd-...
      Reliability    -> http://localhost:3000/reliability
```

Flags: `--count 60` (bigger storm), `--no-approve` (stop at `awaiting_approval` so you can click
**Approve** in Slack/the UI live).

---

## 2. What to show on screen, in order

| Beat | Show | Say |
|---|---|---|
| **Act 1** | the terminal as `demo.py` streams the storm | "50 alerts at once — a human drowns. It folds them into **one** incident, zero loss." |
| **Act 1** | dashboard **`/incidents`** | "One card for the whole storm." |
| **Act 2** | dashboard **`/incidents/{id}`** | grounded root cause, retrieved runbook, **autonomy: high**, audit timeline. |
| **Act 2** | *(optional)* Slack brief + Approve button | "Deterministic, off-LLM governance keeps a human in the loop." |
| **Act 3** | **Phoenix** trace (the 13-span waterfall) | "**It's a real agent** — here it calls `search_runbooks`, then self-evaluates via Arize. Glass-box." |
| **Act 3** | dashboard **`/reliability`** | correlation precision ~0.94, approval rate, autonomy coverage — "outcomes, not vibes." |

**The money shot is the Phoenix trace** — it visually proves autonomous MCP tool-use, which is what
separates this from a prompt wrapper. Lead with it for a technical audience.

---

## 3. Manual fallback (if you'd rather drive each step yourself)

```bash
python scripts/run_storm.py --count 50 --wait 30      # Act 1: storm + DLQ check
# read the incident id from the dashboard /incidents, then:
python scripts/approve.py --incident <incident_id>     # Act 2: approve → execute → resolve
# (or reject:  python scripts/approve.py --incident <id> --reject)
```

Each step is also covered by the unit suite (`pytest`, 91 passing) — useful if Docker is unavailable
on the demo machine.

---

## Exit Criteria → where each is proven

| Exit Criterion | Proof |
|---|---|
| **EC1** — storm dedups into one incident, zero loss | `scripts/demo.py` Act 1 + `tests/test_storm_dedup.py`; evidence in `docs/VALIDATION-EVIDENCE.md` |
| **EC2** — retrieve → self-evaluate → propose → approve → execute → memory loop | `scripts/demo.py` Act 2 + `tests/test_adk_app.py`, `test_governance.py`, `test_executor.py` |
| **EC3** — full observability + secured SSR dashboard | Phoenix trace (13 spans) + auth-gated Next.js SSR; `docs/VALIDATION-EVIDENCE.md` §EC3 |

---

## Troubleshooting on the day

| Symptom | Fix |
|---|---|
| No incident appears | `docker compose logs agent --tail 40` — check Gemini key / MCP session. Bump `--ready-timeout`. |
| Slack post 502 | The bot lacks the `chat:write` scope — the pipeline still proceeds; approve via `scripts/approve.py` or the UI. |
| Dashboard says "OAuth client id not configured" | Already fixed (login is dynamic) — rebuild the frontend image; hard-refresh. |
| Login button errors in console | Add `http://localhost:3000` to the OAuth client's Authorized JavaScript origins. |
| Gemini 429 / quota | The validated model is `gemini-2.5-flash`; confirm `GEMINI_MODEL` and key quota. |
