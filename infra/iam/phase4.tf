# Phase-4 IAM: least-privilege for the frontend Cloud Run service. The sa-frontend-backend service
# account is defined in main.tf; here it gets read-only secret access + Cloud SQL connect. No Editor.

resource "google_secret_manager_secret_iam_member" "frontend_secrets" {
  for_each  = toset(["google-oauth-client-id", "database-url", "session-secret"])
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.svc["frontend-backend"].email}"
}

resource "google_project_iam_custom_role" "frontend_runtime" {
  role_id     = "opssentinelFrontendRuntime"
  title       = "OpsSentinel Frontend Runtime"
  description = "Connect to Cloud SQL for read-only incident reads."
  permissions = [
    "cloudsql.instances.connect",
    "cloudsql.instances.get",
  ]
}

resource "google_project_iam_member" "frontend_cloudsql" {
  project = var.project_id
  role    = google_project_iam_custom_role.frontend_runtime.id
  member  = "serviceAccount:${google_service_account.svc["frontend-backend"].email}"
}
