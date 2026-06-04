# infra/secret-manager — Credentials (Google Cloud Secret Manager)

Creates **every** secret in the shared contract — empty, no versions — so credentials are
**injected dynamically at runtime** and **never hardcoded or committed**. Services resolve them
via [`lib/secrets.get_secret()`](../../lib/secrets.py): Secret Manager on GCP, `.env` locally.

## Secrets ↔ env vars ↔ consumers

| Secret | Env var | Used by |
|---|---|---|
| `gemini-api-key` | `GEMINI_API_KEY` | agent |
| `elastic-url` | `ELASTIC_URL` | mcp-elastic |
| `elastic-api-key` | `ELASTIC_API_KEY` | mcp-elastic |
| `phoenix-collector-endpoint` | `PHOENIX_COLLECTOR_ENDPOINT` | agent, mcp-arize |
| `phoenix-api-key` | `PHOENIX_API_KEY` | agent, mcp-arize |
| `slack-bot-token` | `SLACK_BOT_TOKEN` | slack-bot |
| `slack-signing-secret` | `SLACK_SIGNING_SECRET` | slack-bot |
| `google-oauth-client-id` | `GOOGLE_OAUTH_CLIENT_ID` | frontend, backend |
| `database-url` | `DATABASE_URL` | agent, backend API |

## Apply & populate

```bash
terraform -chdir=infra/secret-manager init
terraform -chdir=infra/secret-manager validate
terraform -chdir=infra/secret-manager apply -var project_id=$GOOGLE_CLOUD_PROJECT

# Add real values out-of-band (example):
printf '%s' "$REAL_GEMINI_KEY" | gcloud secrets versions add gemini-api-key --data-file=-
```

Grant access narrowly: only the SA that needs a secret gets `roles/secretmanager.secretAccessor`
on that secret (see [`infra/iam`](../iam)). Never grant project-wide secret access.
