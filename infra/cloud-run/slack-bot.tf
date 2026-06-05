# Phase-5 addition: the Slack HITL bot on Cloud Run. Public ingress because Slack POSTs to
# /slack/interactions from the internet — that endpoint is signature-verified with
# slack-signing-secret. (Hardening note: /notify is agent-internal and should be network-restricted
# in production.) Secrets resolve at runtime via lib/secrets.get_secret() from Secret Manager.

resource "google_cloud_run_v2_service" "slack_bot" {
  name     = "slack-bot"
  location = var.primary_region
  ingress  = "INGRESS_TRAFFIC_ALL"

  template {
    service_account = var.slack_bot_sa
    scaling {
      min_instance_count = 0
      max_instance_count = 3
    }
    containers {
      image = var.slack_bot_image
      ports {
        container_port = 8080
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "OPSSENTINEL_USE_SECRET_MANAGER"
        value = "true"
      }
      env {
        name  = "OPSSENTINEL_ACTIONS_TOPIC"
        value = "opssentinel-actions"
      }
      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
      startup_probe {
        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }
}

# Slack's servers cannot authenticate with Google IAM, so invocation is unauthenticated at that
# layer; the request-signature check in the app is the security boundary.
resource "google_cloud_run_v2_service_iam_member" "slack_bot_public" {
  name     = google_cloud_run_v2_service.slack_bot.name
  location = google_cloud_run_v2_service.slack_bot.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
