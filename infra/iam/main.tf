provider "google" {
  project = var.project_id
}

# ── Dedicated service account per service (no shared/default SAs) ─────────────
locals {
  service_accounts = {
    "webhook-receiver" = "Input Layer — publishes normalized alerts"
    "agent"            = "Agent Layer — consumes alerts, writes incidents, executes actions"
    "mcp-elastic"      = "Elastic MCP server"
    "mcp-arize"        = "Arize/Phoenix MCP server"
    "slack-bot"        = "Slack HITL bot"
    "frontend-backend" = "Dashboard read-model backend API"
    "scheduler"        = "Cloud Scheduler invoker"
  }
}

resource "google_service_account" "svc" {
  for_each     = local.service_accounts
  account_id   = "sa-${each.key}"
  display_name = "OpsSentinel ${each.key}"
  description  = each.value
}

# ── Custom roles — minimal, non-destructive permissions only ─────────────────
# The webhook receiver may ONLY publish to Pub/Sub.
resource "google_project_iam_custom_role" "webhook_publisher" {
  role_id     = "opssentinelWebhookPublisher"
  title       = "OpsSentinel Webhook Publisher"
  description = "Publish normalized alerts to Pub/Sub. Nothing else."
  permissions = [
    "pubsub.topics.publish",
    "pubsub.topics.get",
  ]
}

# The agent may subscribe to alerts, publish approved actions, connect to Cloud SQL, and read
# the specific secrets it needs — and nothing destructive.
resource "google_project_iam_custom_role" "agent_runtime" {
  role_id     = "opssentinelAgentRuntime"
  title       = "OpsSentinel Agent Runtime"
  description = "Consume alerts, publish actions, connect Cloud SQL, access secrets."
  permissions = [
    "pubsub.subscriptions.consume",
    "pubsub.subscriptions.get",
    "pubsub.topics.publish",
    "cloudsql.instances.connect",
    "cloudsql.instances.get",
    "secretmanager.versions.access",
  ]
}

# ── Bindings (least privilege) ───────────────────────────────────────────────
resource "google_project_iam_member" "webhook_publisher_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.webhook_publisher.id
  member  = "serviceAccount:${google_service_account.svc["webhook-receiver"].email}"
}

resource "google_project_iam_member" "agent_runtime_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.agent_runtime.id
  member  = "serviceAccount:${google_service_account.svc["agent"].email}"
}

# The remaining SAs (mcp-elastic, mcp-arize, slack-bot, frontend-backend, scheduler) are created
# here with NO project bindings yet; their phases attach narrow, resource-scoped roles (e.g.
# per-secret secretAccessor). The default project Editor role is never granted to any SA.
