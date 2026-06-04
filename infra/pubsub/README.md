# infra/pubsub — Queue Layer (Google Cloud Pub/Sub, AP-tuned)

Provisions the **Queue Layer**: the system's shock absorber, tuned for **Availability +
Partition tolerance**. It must accept *all* incoming alerts even if the database indexing them
falls momentarily behind — guaranteeing **zero alert loss** and applying **back-pressure**.

## Resources

| Resource | Purpose |
|---|---|
| `opssentinel-alerts` (topic) | Ingest topic — the normalized event queue. 24h retention safety net. |
| `opssentinel-alerts-sub` (subscription) | Agent Layer pull subscription. Backoff retry + dead-letter + 7-day retention + never-expire. |
| `opssentinel-alerts-dlq` (topic) | Dead-letter topic — captures poison messages so an alert is never dropped. |
| `opssentinel-alerts-dlq-sub` (subscription) | Keeps dead-lettered alerts inspectable. |
| `opssentinel-actions` (topic) | Outbound approved-action channel (used by Phase 3/5; provisioned here per the contract). |

**Back-pressure** is realized client-side in [`lib/pubsub.py`](../../lib/pubsub.py) via
`FlowControl(max_messages=...)` — the agent consumes at a controlled, sustainable rate. The
subscription's exponential backoff turns a transient downstream stall into back-pressure rather
than loss; the dead-letter policy forwards a message to the DLQ after `max_delivery_attempts`.

## Apply

```bash
terraform -chdir=infra/pubsub init
terraform -chdir=infra/pubsub validate
terraform -chdir=infra/pubsub plan  -var project_id=$GOOGLE_CLOUD_PROJECT
terraform -chdir=infra/pubsub apply -var project_id=$GOOGLE_CLOUD_PROJECT
```

## Local equivalent

`docker-compose` runs the **Pub/Sub emulator**; `make publish-test` publishes a sample normalized
event and reads it back. The emulator mirrors this topology (topics + subscription) but ignores
IAM and some retention semantics — the Terraform here remains the authoritative cloud target.
