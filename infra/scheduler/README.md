# infra/scheduler — Cost governance + SLA enforcement (Cloud Scheduler)

Scaffolds two scheduled controls. Both publish to a Pub/Sub control topic; the **Agent Layer
(Phase 3)** subscribes and acts — so the mechanism and hook points exist now, before any agent
code.

| Job | Schedule | Topic | Intent |
|---|---|---|---|
| `opssentinel-inference-cap-reset` | `0 0 * * *` (daily) | `opssentinel-inference-cap-reset` | **Hard daily cap on LLM/API invocations** — resets the budget; the agent refuses further inference once exhausted, surviving runaway alert storms. |
| `opssentinel-sla-check` | `*/15 * * * *` | `opssentinel-sla-check` | **SLA sweep** — escalates incidents past their response/resolution window (`sla_policies`: P1 respond ≤ 15 min, P2 ≤ 60 min). |

## Hook point (Phase 3)

The agent consumes these topics and:
- on `reset_budget` → sets the remaining daily inference budget to `daily_cap`;
- on each inference call → decrements the budget and **refuses** when it reaches zero;
- on `sla_sweep` → finds `open`/`awaiting_approval` incidents older than their `sla_policies`
  window and sets `status = escalated`, appending to `audit_log`.

## Apply

```bash
terraform -chdir=infra/scheduler init
terraform -chdir=infra/scheduler validate
terraform -chdir=infra/scheduler apply \
  -var project_id=$GOOGLE_CLOUD_PROJECT -var inference_daily_cap=5000
```
