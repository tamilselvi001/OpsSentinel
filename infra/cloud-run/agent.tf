# Phase-3 addition: the ADK agent as an internal Cloud Run service.
# It is a Pub/Sub pull worker, so it is pinned to >=1 instance with CPU always allocated (the
# background reasoning + execution loops must keep running between requests). Credentials resolve
# at runtime via lib/secrets.get_secret() from Secret Manager (the SA holds per-secret accessor
# grants in infra/iam) — no secret values are wired here.

resource "google_cloud_run_v2_service" "agent" {
  name     = "agent"
  location = var.primary_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = var.agent_sa

    scaling {
      min_instance_count = 1 # pinned: the agent runs background pull loops
      max_instance_count = 3
    }

    containers {
      image = var.agent_image
      ports {
        container_port = 8080 # /health for Cloud Run liveness
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
        name  = "OPSSENTINEL_ALERTS_SUB"
        value = "opssentinel-alerts-sub"
      }
      env {
        name  = "OPSSENTINEL_ACTIONS_TOPIC"
        value = "opssentinel-actions"
      }
      env {
        name  = "MCP_ELASTIC_URL"
        value = "http://mcp-elastic:8080/sse"
      }
      env {
        name  = "MCP_ARIZE_URL"
        value = "http://mcp-arize:8081/sse"
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "1Gi"
        }
        cpu_idle = false # CPU always allocated — required for the background pull loops
      }

      startup_probe {
        http_get {
          path = "/health"
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
