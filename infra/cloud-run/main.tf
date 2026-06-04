provider "google" {
  project = var.project_id
  region  = var.primary_region
}

# Single Artifact Registry repo for all service images.
resource "google_artifact_registry_repository" "containers" {
  location      = var.primary_region
  repository_id = "opssentinel"
  format        = "DOCKER"
  description   = "OpsSentinel service container images"
}

# Webhook receiver deployed redundantly across parallel regions for fault tolerance — the spec's
# "redundant Cloud Run regions in parallel" availability principle. The L7 load balancer
# (infra/networking) fronts these for a single ingress.
resource "google_cloud_run_v2_service" "webhook_receiver" {
  for_each = toset(var.regions)

  name     = var.service_name
  location = each.value
  ingress  = "INGRESS_TRAFFIC_ALL" # reachable by external monitoring webhooks and the L7 LB

  template {
    service_account = var.service_account_email

    scaling {
      min_instance_count = var.min_instances
      max_instance_count = var.max_instances
    }

    containers {
      image = var.image

      ports {
        container_port = 8080
      }

      # Non-secret runtime config. Secrets (none needed by this service) would be wired as
      # secret env refs via Secret Manager — see lib/secrets.get_secret().
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "PUBSUB_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "OPSSENTINEL_ALERTS_TOPIC"
        value = "opssentinel-alerts"
      }
      env {
        name  = "OPSSENTINEL_USE_SECRET_MANAGER"
        value = "true"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get {
          path = "/ready"
          port = 8080
        }
      }
      liveness_probe {
        http_get {
          path = "/health"
          port = 8080
        }
      }
    }
  }
}

# External monitoring tools post webhooks, so invocations are unauthenticated at the IAM layer.
# Defense in depth = per-source signature verification in the app + Cloud Armor on the L7 LB.
resource "google_cloud_run_v2_service_iam_member" "public_invoker" {
  for_each = google_cloud_run_v2_service.webhook_receiver

  name     = each.value.name
  location = each.value.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
