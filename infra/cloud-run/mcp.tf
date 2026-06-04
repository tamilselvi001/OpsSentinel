# Phase-2 additions: the two MCP servers as independent, internal-only Cloud Run services.
# Credentials resolve at runtime via lib/secrets.get_secret() from Secret Manager (the SAs hold
# per-secret accessor grants in infra/iam) — so no secret values are wired here.

resource "google_cloud_run_v2_service" "mcp_elastic" {
  name     = "mcp-elastic"
  location = var.primary_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY" # only the agent (internal) calls the MCP servers

  template {
    service_account = var.mcp_elastic_sa
    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }
    containers {
      image = var.mcp_elastic_image
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
      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi" # holds the all-MiniLM-L6-v2 model in memory
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

resource "google_cloud_run_v2_service" "mcp_arize" {
  name     = "mcp-arize"
  location = var.primary_region
  ingress  = "INGRESS_TRAFFIC_INTERNAL_ONLY"

  template {
    service_account = var.mcp_arize_sa
    scaling {
      min_instance_count = 0
      max_instance_count = 4
    }
    containers {
      image = var.mcp_arize_image
      ports {
        container_port = 8081
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
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
          path = "/health"
          port = 8081
        }
      }
    }
  }
}
