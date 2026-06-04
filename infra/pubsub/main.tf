provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Topics ───────────────────────────────────────────────────────────────────
resource "google_pubsub_topic" "alerts" {
  name = var.alerts_topic
  # 24h server-side retention is a safety net backing the "zero alert loss" guarantee.
  message_retention_duration = "86400s"
}

resource "google_pubsub_topic" "dlq" {
  name = var.dlq_topic
}

# Outbound approved-action channel. Provisioned in Phase 1 per the Queue-Layer contract; the
# Agent Layer (Phase 3) publishes approvals here and consumes them to execute remediations.
resource "google_pubsub_topic" "actions" {
  name = var.actions_topic
}

# ── Agent pull subscription (AP-tuned: zero loss + back-pressure) ─────────────
resource "google_pubsub_subscription" "alerts_sub" {
  name  = var.alerts_subscription
  topic = google_pubsub_topic.alerts.id

  ack_deadline_seconds       = var.ack_deadline_seconds
  message_retention_duration = "604800s" # 7 days
  retain_acked_messages      = false

  # Throughput-first: no global ordering. The Agent correlates by correlation_key, so it does
  # not depend on Pub/Sub message order; disabling ordering preserves maximum ingest throughput.
  enable_message_ordering = false

  # Never expire — the agent may be briefly offline during a partition; the queue must wait.
  expiration_policy {
    ttl = ""
  }

  # Exponential backoff turns a transient downstream stall into back-pressure, not loss.
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "600s"
  }

  # Dead-letter after N attempts so a poison message is captured, never dropped.
  dead_letter_policy {
    dead_letter_topic     = google_pubsub_topic.dlq.id
    max_delivery_attempts = var.max_delivery_attempts
  }
}

# Subscription on the DLQ so dead-lettered alerts are retained and inspectable.
resource "google_pubsub_subscription" "dlq_sub" {
  name                       = "${var.dlq_topic}-sub"
  topic                      = google_pubsub_topic.dlq.id
  message_retention_duration = "604800s"

  expiration_policy {
    ttl = ""
  }
}

# ── IAM required for dead-lettering to function ──────────────────────────────
# Pub/Sub's own service agent must publish to the DLQ and subscribe to the source subscription.
data "google_project" "this" {}

locals {
  pubsub_service_agent = "serviceAccount:service-${data.google_project.this.number}@gcp-sa-pubsub.iam.gserviceaccount.com"
}

resource "google_pubsub_topic_iam_member" "dlq_publisher" {
  topic  = google_pubsub_topic.dlq.id
  role   = "roles/pubsub.publisher"
  member = local.pubsub_service_agent
}

resource "google_pubsub_subscription_iam_member" "sub_subscriber" {
  subscription = google_pubsub_subscription.alerts_sub.id
  role         = "roles/pubsub.subscriber"
  member       = local.pubsub_service_agent
}
