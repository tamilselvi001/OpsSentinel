# infra/postgres — Incident Store (Cloud SQL for PostgreSQL, CP-tuned)

The primary store for structured incident metadata, state tracking, and relational data —
the **Consistency + Partition-tolerance (CP)** side of the system.

## Spec mapping

| Spec requirement | Realization here |
|---|---|
| Active-Passive (Master-Slave) replication | `availability_type = "REGIONAL"` — a synchronously-replicated standby in a second zone |
| Continuous heartbeats + automatic failover, standby assumes the primary's IP | Cloud SQL regional HA behind a single shared connection name / IP |
| 99.99% availability target | Regional HA + PITR backups + SSD autoresize |
| Strong ACID consistency (no race / duplicate remediation) | Single-transaction writes + `INSERT ... ON CONFLICT` upsert in [`lib/db.py`](../../lib/db.py) |

## Schema

Authored as Alembic migrations in [`migrations/`](../../migrations) (not in Terraform, so it is
versioned and replayable). `0001_initial_schema` creates four tables — `incidents`,
`incident_events`, `audit_log`, `sla_policies` — with the Section-3 enums, jsonb columns, and
indexes on `status`, `severity`, `correlation_key` (on `incident_events`) and `created_at`, plus
the SLA seed rows (P1 respond ≤ 15 min, P2 ≤ 60 min).

> The master-index contract also defines a `blast_radius` column on `incidents`; it is
> intentionally omitted to match the Phase-1 spec exactly, and can be added when Phase 3 needs it.

## Apply

```bash
terraform -chdir=infra/postgres init
terraform -chdir=infra/postgres validate
terraform -chdir=infra/postgres apply -var project_id=$GOOGLE_CLOUD_PROJECT

# Feed the generated DSN into Secret Manager (never into a file):
terraform -chdir=infra/postgres output -raw database_url | \
  gcloud secrets versions add database-url --data-file=-

# Then apply the schema:
make migrate            # alembic upgrade head  (resolves DATABASE_URL via lib/secrets)
```

## Production note

The MVP uses a public IP gated by authorized networks for simplicity. For production, switch to
a **private IP** (VPC + Serverless VPC Access connector) so Cloud Run reaches the database over
private networking; the `ip_configuration` block is where that changes.
