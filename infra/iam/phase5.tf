# Phase-5 IAM: least-privilege for the Slack bot. The sa-slack-bot account is defined in main.tf.
# It may publish approvals to opssentinel-actions, connect to Cloud SQL (reject/audit writes), and
# read only its own secrets. No Editor. Requires infra/secret-manager applied first.

resource "google_project_iam_custom_role" "slack_bot_runtime" {
  role_id     = "opssentinelSlackBotRuntime"
  title       = "OpsSentinel slack-bot Runtime"
  description = "Publish approvals to opssentinel-actions + Cloud SQL connect for reject/audit."
  permissions = [
    "pubsub.topics.publish",
    "cloudsql.instances.connect",
    "cloudsql.instances.get",
  ]
}

resource "google_project_iam_member" "slack_bot_runtime_binding" {
  project = var.project_id
  role    = google_project_iam_custom_role.slack_bot_runtime.id
  member  = "serviceAccount:${google_service_account.svc["slack-bot"].email}"
}

resource "google_secret_manager_secret_iam_member" "slack_bot_secrets" {
  for_each  = toset(["slack-bot-token", "slack-signing-secret", "database-url"])
  secret_id = each.value
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.svc["slack-bot"].email}"
}
