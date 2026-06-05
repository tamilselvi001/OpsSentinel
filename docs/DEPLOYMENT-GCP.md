# OpsSentinel — GCP Deployment Plan

This is the production deployment runbook for the platform that is already **feature-complete and
validated locally** (see `docs/VALIDATION-EVIDENCE.md`). Nothing here changes application code — it
provisions the real Google Cloud equivalents of the docker-compose stack and rolls the same images out
to Cloud Run.

> **Why this is a separate step.** The local toolchain has no `gcloud`, no container registry, and
> Terraform is only `validate`-ed, never `apply`-ed. Everything below runs in **your** GCP environment.
> Secrets are never committed — Terraform creates the secrets *empty* and you add versions out-of-band.

---

## 0. What gets deployed (grounded in `infra/`)

| Terraform component (`infra/<dir>`) | Provisions |
|---|---|
| `secret-manager` | 10 empty secrets (the shared contract — see §3) |
| `iam` | One least-privilege service account per service (phase2–5 files) |
| `postgres` | Cloud SQL Postgres instance + `opssentinel` db + user |
| `pubsub` | Topics `opssentinel-alerts` / `-dlq` / `-actions` + subscriptions + DLQ IAM |
| `cloud-run` | 6 services: `agent`, `frontend`, `webhook-receiver`, `mcp-elastic`, `mcp-arize`, `slack-bot` |
| `networking` | Serverless NEG → frontend, backend service + Cloud CDN, URL map, managed SSL, global LB IP |
| `scheduler` | `inference_cap_reset` + `sla_check` Cloud Scheduler jobs |

**External managed dependencies** (not Terraformed here — provision separately, then store their
endpoints as secrets):
- **Elasticsearch** — Elastic Cloud deployment (or self-managed) → `elastic-url`, `elastic-api-key`.
- **Arize Phoenix** — Arize-hosted or self-hosted Phoenix collector → `phoenix-collector-endpoint`,
  `phoenix-api-key`.

---

## 1. Prerequisites (one-time)

```bash
# A GCP project with billing enabled
gcloud config set project <PROJECT_ID>

# Enable the APIs the stack uses
gcloud services enable \
  run.googleapis.com artifactregistry.googleapis.com sqladmin.googleapis.com \
  pubsub.googleapis.com secretmanager.googleapis.com cloudscheduler.googleapis.com \
  compute.googleapis.com iam.googleapis.com

# Artifact Registry repo for the images
gcloud artifacts repositories create opssentinel \
  --repository-format=docker --location=<REGION>
gcloud auth configure-docker <REGION>-docker.pkg.dev
```

**Terraform remote state (recommended):** create a GCS bucket and add a `backend "gcs"` block to each
component so state is shared and locked, instead of the local state used during validation. Never
commit `*.tfstate`.

---

## 2. Build & push the images

The five app images + frontend, tagged for Artifact Registry. Run from the repo root:

```bash
REG=<REGION>-docker.pkg.dev/<PROJECT_ID>/opssentinel
for s in agent slack-bot mcp-elastic mcp-arize webhook-receiver; do
  docker build -f services/$s/Dockerfile -t $REG/$s:v1 .   # backend images build from repo root
  docker push $REG/$s:v1
done
docker build -f frontend/Dockerfile -t $REG/frontend:v1 frontend
docker push $REG/frontend:v1
```

> The frontend `Dockerfile` uses `npm install` (not `npm ci`) — keep that; it's the fix for the
> Windows-lockfile/Alpine `@emnapi` mismatch. The `/login` page reads the OAuth client id at runtime
> via `await connection()`, so you do **not** need a build-time `NEXT_PUBLIC_` value.

---

## 3. Create + populate secrets

Apply the secret-manager component (creates all 10 **empty**), then add a version to each. Values come
from you / the external services — none are invented or committed.

```bash
cd infra/secret-manager && terraform init && terraform apply   # creates empty secrets
```

| Secret | Value source |
|---|---|
| `gemini-api-key` | Google AI Studio key (the validated model is `gemini-2.5-flash`) |
| `elastic-url`, `elastic-api-key` | Elastic Cloud deployment |
| `phoenix-collector-endpoint`, `phoenix-api-key` | Arize Phoenix collector |
| `slack-bot-token`, `slack-signing-secret` | Slack app (bot needs the **`chat:write`** scope — see `docs/MANUAL-SETUP.md`) |
| `google-oauth-client-id` | your OAuth client (`885702205248-…apps.googleusercontent.com`) |
| `session-secret` | `openssl rand -hex 32` |
| `database-url` | filled **after** §4 (Cloud SQL) |

```bash
printf '%s' "<value>" | gcloud secrets versions add gemini-api-key --data-file=-
# …repeat per secret
```

---

## 4. Provision data plane (Cloud SQL + Pub/Sub + IAM)

```bash
cd ../iam      && terraform init && terraform apply   # service accounts first
cd ../postgres && terraform init && terraform apply   # Cloud SQL instance + db + user
cd ../pubsub   && terraform init && terraform apply   # topics + subscriptions + DLQ
```

After Cloud SQL is up, compose its connection string and store it:

```bash
# Use the Cloud SQL connector socket form for Cloud Run:
#   postgresql+psycopg://opssentinel:<pw>@/opssentinel?host=/cloudsql/<INSTANCE_CONNECTION_NAME>
printf '%s' "<database-url>" | gcloud secrets versions add database-url --data-file=-
```

Then run the **Alembic migrations** against Cloud SQL (via the Cloud SQL Auth Proxy), and **seed** the
knowledge base + Arize history — the same scripts used locally:

```bash
alembic upgrade head
python scripts/seed.py          # Elasticsearch runbooks (canonical categories — critical for autonomy)
python scripts/seed_arize.py    # agent_outcomes priors
```

---

## 5. Deploy services + edge

```bash
cd ../cloud-run  && terraform init && terraform apply \
  -var "agent_image=$REG/agent:v1" -var "frontend_image=$REG/frontend:v1" \
  -var "mcp_elastic_image=$REG/mcp-elastic:v1" -var "mcp_arize_image=$REG/mcp-arize:v1" \
  -var "slack_bot_image=$REG/slack-bot:v1" -var "image=$REG/webhook-receiver:v1" \
  -var "project_id=<PROJECT_ID>"
cd ../networking && terraform init && terraform apply   # NEG→frontend, LB, CDN, managed SSL
cd ../scheduler  && terraform init && terraform apply   # inference cap reset + SLA check jobs
```

Set the frontend Cloud Run env `OPSSENTINEL_DATA_MODE=live` (the data layer reads Cloud SQL via the
injected `database-url`). Cloud Run injects every secret from §3 as env vars.

**Post-deploy wiring (human):**
- Add the load balancer's domain + `https://<frontend-run-url>` to the OAuth client's **Authorized
  JavaScript origins**.
- Point the Slack app's **Interactivity Request URL** at `https://<slack-bot-run-url>/slack/interactions`.
- Confirm the managed SSL cert is `ACTIVE` (DNS A-record → the global LB IP from `networking` outputs).

---

## 6. Verify in cloud (same 3 Exit Criteria as the local run)

1. **EC1** — publish a 50-signal storm to `opssentinel-alerts` (`scripts/run_storm.py` pointed at the
   real project, no emulator) → one incident, 50 folded, DLQ empty.
2. **EC2** — confirm retrieve→propose→Slack(real `chat:write` post)→Approve button→execute→resolve, with
   the Arize outcome + Elastic closure written back.
3. **EC3** — open the Phoenix UI for the incident's `trace_id`; sign in to the dashboard over HTTPS and
   view live incidents + reliability metrics.

---

## 7. Cost & hardening notes

- **Scale-to-zero:** keep `min_instances=0` on non-critical services; the agent may want `min=1` to
  avoid cold-start on the first alert.
- **mcp-elastic / mcp-arize** are internal — restrict ingress to internal + the agent's SA only (the
  IAM module already separates SAs; tighten `ingress` to `INTERNAL`).
- **DNS-rebinding:** the MCP servers run with `enable_dns_rebinding_protection=False` because Cloud Run
  routes by service URL, not Host header — keep this; it's the documented fix from the migration.
- **Secrets:** rotate via new secret versions; Cloud Run picks up `latest`. Never commit values.
- **Budget alert** on the project; Gemini + Cloud SQL + LB are the main cost drivers.
```
