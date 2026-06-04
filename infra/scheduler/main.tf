provider "google" {
  project = var.project_id
  region  = var.region
}

# Control topics the scheduler drives. The Agent Layer (Phase 3) subscribes and acts on these:
#  - inference-cap-reset: rolls the daily LLM-invocation budget back to the cap.
#  - sla-check:           triggers an SLA sweep that escalates overdue incidents.
resource "google_pubsub_topic" "inference_cap_reset" {
  name = "opssentinel-inference-cap-reset"
}

resource "google_pubsub_topic" "sla_check" {
  name = "opssentinel-sla-check"
}

# ── Cost governance: hard daily cap on inference (runaway-storm protection) ───
# Scaffolds the cap. The daily tick resets the budget to `inference_daily_cap`; the Agent
# enforces "refuse further LLM calls once the budget is exhausted" in Phase 3.
resource "google_cloud_scheduler_job" "inference_cap_reset" {
  name        = "opssentinel-inference-cap-reset"
  description = "Daily reset of the LLM inference budget (hard cost cap)."
  schedule    = "0 0 * * *" # midnight daily
  time_zone   = var.timezone

  pubsub_target {
    topic_name = google_pubsub_topic.inference_cap_reset.id
    data       = base64encode(jsonencode({ action = "reset_budget", daily_cap = var.inference_daily_cap }))
  }
}

# ── SLA enforcement: escalate overdue incidents every 15 minutes ─────────────
resource "google_cloud_scheduler_job" "sla_check" {
  name        = "opssentinel-sla-check"
  description = "Every 15 min: escalate incidents past their SLA response/resolution window."
  schedule    = "*/15 * * * *"
  time_zone   = var.timezone

  pubsub_target {
    topic_name = google_pubsub_topic.sla_check.id
    data       = base64encode(jsonencode({ action = "sla_sweep" }))
  }
}
