# slack-bot — the human-in-the-loop approval gate

The asynchronous **Approve / Reject** gate where engineers act on the agent's proposals. It posts a
**plain-text decision brief** (root cause, historical precedent, proposed fix, risk level) with
binary buttons, and turns an Approve into the Phase-3 deterministic execution path.

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| POST | `/notify` | Internal: the agent posts `{incident_id}`; the bot reads the persisted brief and posts it to Slack |
| POST | `/slack/interactions` | Slack interactivity URL — **signature-verified**; Approve/Reject buttons |
| GET | `/health` | Liveness |

## Flow

- **Approve** → publish `{incident_id, decision: "approve", approver}` to **`opssentinel-actions`**
  (the Phase-3 executor consumes it → mocked fix + ticket resolved + closure to Elastic + outcome to
  Arize) and append to `audit_log`.
- **Reject** → set `status = rejected` and append to `audit_log`.

Buttons carry `incident_id` in their `value`; `action_id` is `approve_incident` / `reject_incident`.

## Security

`/slack/interactions` is verified with `slack-signing-secret` (Slack v0 HMAC + timestamp-skew, see
[`app/signing.py`](app/signing.py)). `slack-bot-token` / `slack-signing-secret` resolve only via
`lib/secrets.get_secret()`. The bot's SA is least-privilege (publish to `opssentinel-actions` only).

## Local Slack testing

Set `SLACK_SIGNING_SECRET` + `SLACK_BOT_TOKEN` in `.env`, run `make dev`, and expose
`/slack/interactions` via a tunnel (e.g. `ngrok http 8080`) as the app's **Interactivity Request
URL**. `make storm` → the agent posts a brief; click Approve to drive the executor.

## Build

```bash
docker build -f services/slack-bot/Dockerfile -t slack-bot .   # non-root, context = repo root
```
