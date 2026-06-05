# Phase-4 addition: the Next.js dashboard on Cloud Run, reachable ONLY via the L7 load balancer
# (the Phase-1 Serverless NEG in infra/networking targets this service by name). Secrets are
# injected from Secret Manager as env vars (the Node frontend reads process.env at runtime).

resource "google_cloud_run_v2_service" "frontend" {
  name     = var.frontend_service_name # must match infra/networking var.frontend_service
  location = var.primary_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_LOAD_BALANCER"

  template {
    service_account = var.frontend_sa

    scaling {
      min_instance_count = 0
      max_instance_count = 5
    }

    containers {
      image = var.frontend_image
      ports {
        container_port = 3000
      }

      env {
        name  = "NODE_ENV"
        value = "production"
      }
      env {
        name  = "OPSSENTINEL_DATA_MODE"
        value = "live"
      }
      env {
        name = "GOOGLE_OAUTH_CLIENT_ID"
        value_source {
          secret_key_ref {
            secret  = "google-oauth-client-id"
            version = "latest"
          }
        }
      }
      env {
        name = "DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = "database-url"
            version = "latest"
          }
        }
      }
      env {
        name = "SESSION_SECRET"
        value_source {
          secret_key_ref {
            secret  = "session-secret"
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }

      startup_probe {
        http_get {
          path = "/login"
          port = 3000
        }
      }
    }
  }
}
