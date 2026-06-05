# Phase-3 IAM: scope the agent's secret access to exactly the secrets it reads (resource-scoped
# secretAccessor), tightening the project-level grant in the Phase-1 `agent_runtime` custom role.
# The sa-agent service account and the agent_runtime custom role (Pub/Sub subscribe + publish,
# Cloud SQL connect) are defined in main.tf. Requires infra/secret-manager applied first.

resource "google_secret_manager_secret_iam_member" "agent_secrets" {
  for_each = toset([
    "gemini-api-key",
    "database-url",
    "elastic-url",
    "elastic-api-key",
    "phoenix-collector-endpoint",
    "phoenix-api-key",
  ])
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.svc["agent"].email}"
}
