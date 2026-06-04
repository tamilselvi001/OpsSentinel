# Phase-2 identities & bindings (additive to Phase 1; same least-privilege rules — no Editor).
# The mcp-elastic / mcp-arize SAs were declared in main.tf; here they get narrow, resource-scoped
# secret access. Per-secret grants require infra/secret-manager applied first.

# ── Alert simulator: Pub/Sub publish only (reuse the webhook publisher custom role) ──────────
resource "google_service_account" "alert_simulator" {
  account_id   = "sa-alert-simulator"
  display_name = "OpsSentinel alert-simulator"
  description  = "Publishes mock normalized alerts to Pub/Sub"
}

resource "google_project_iam_member" "alert_simulator_publish" {
  project = var.project_id
  role    = google_project_iam_custom_role.webhook_publisher.id
  member  = "serviceAccount:${google_service_account.alert_simulator.email}"
}

# ── mcp-elastic: read ONLY its two secrets ───────────────────────────────────────────────────
resource "google_secret_manager_secret_iam_member" "mcp_elastic_secrets" {
  for_each  = toset(["elastic-url", "elastic-api-key"])
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.svc["mcp-elastic"].email}"
}

# ── mcp-arize: read its secrets + connect to Cloud SQL (agent_outcomes) ──────────────────────
resource "google_secret_manager_secret_iam_member" "mcp_arize_secrets" {
  for_each  = toset(["phoenix-collector-endpoint", "phoenix-api-key", "database-url"])
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.svc["mcp-arize"].email}"
}

resource "google_project_iam_custom_role" "mcp_arize_runtime" {
  role_id     = "opssentinelMcpArizeRuntime"
  title       = "OpsSentinel mcp-arize Runtime"
  description = "Connect to Cloud SQL to read/write agent_outcomes."
  permissions = [
    "cloudsql.instances.connect",
    "cloudsql.instances.get",
  ]
}

resource "google_project_iam_member" "mcp_arize_cloudsql" {
  project = var.project_id
  role    = google_project_iam_custom_role.mcp_arize_runtime.id
  member  = "serviceAccount:${google_service_account.svc["mcp-arize"].email}"
}
