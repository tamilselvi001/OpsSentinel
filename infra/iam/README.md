# infra/iam — Least-privilege IAM

A **dedicated service account per service** with **custom roles** scoped to the minimum,
non-destructive permissions each needs. The default project **Editor role is never granted** to
any service account.

## Service account → role mapping

| Service account | Custom role | Permissions | Granted in |
|---|---|---|---|
| `sa-webhook-receiver` | `opssentinelWebhookPublisher` | `pubsub.topics.publish`, `pubsub.topics.get` | Phase 1 |
| `sa-agent` | `opssentinelAgentRuntime` | `pubsub.subscriptions.consume/get`, `pubsub.topics.publish`, `cloudsql.instances.connect/get`, `secretmanager.versions.access` | Phase 1 |
| `sa-mcp-elastic` | per-secret `secretAccessor` (`elastic-url`, `elastic-api-key`) | read only its 2 secrets | Phase 2 (`phase2.tf`) |
| `sa-mcp-arize` | `secretAccessor` (`phoenix-*`, `database-url`) + `opssentinelMcpArizeRuntime` | read its secrets + Cloud SQL connect | Phase 2 (`phase2.tf`) |
| `sa-alert-simulator` | `opssentinelWebhookPublisher` | Pub/Sub publish only | Phase 2 (`phase2.tf`) |
| `sa-slack-bot` | — (narrow roles attached in Phase 5) | per-secret `secretAccessor`, `pubsub.topics.publish` | Phase 5 |
| `sa-frontend-backend` | — (narrow roles attached in Phase 4) | `cloudsql.instances.connect`, per-secret `secretAccessor` | Phase 4 |
| `sa-scheduler` | — (invoker role attached in Phase 1 scheduler) | `run.invoker` / `pubsub.publisher` on the cap/SLA topics | Phase 1 (`infra/scheduler`) |

## Principles enforced

- **No Editor** (or other broad primitive roles) anywhere.
- **Custom roles** aggregate only the specific, non-destructive actions a service performs.
- SAs whose permissions belong to a later phase are **created empty** here and bound narrowly when
  that phase lands — so identities are stable but privileges never precede need.
- **Future tightening:** the Phase-1 custom-role bindings are project-scoped; they can be narrowed
  to resource-scoped bindings (specific topic / subscription / secret) as the resources stabilize.

## Apply

```bash
terraform -chdir=infra/iam init
terraform -chdir=infra/iam validate
terraform -chdir=infra/iam apply -var project_id=$GOOGLE_CLOUD_PROJECT
```
