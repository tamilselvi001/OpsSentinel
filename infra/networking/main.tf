provider "google" {
  project = var.project_id
  region  = var.region
}

# ── Serverless NEG → Cloud Run ───────────────────────────────────────────────
# Securely connects the external L7 load balancer to a Cloud Run service. The frontend service
# is attached here in Phase 4; the NEG + LB foundation is stood up now.
resource "google_compute_region_network_endpoint_group" "serverless_neg" {
  name                  = "opssentinel-frontend-neg"
  network_endpoint_type = "SERVERLESS"
  region                = var.region

  cloud_run {
    service = var.frontend_service
  }
}

# ── Backend service with Cloud CDN (Pull strategy + TTL headers) ─────────────
resource "google_compute_backend_service" "default" {
  name                  = "opssentinel-frontend-backend"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  protocol              = "HTTP"
  enable_cdn            = true

  cdn_policy {
    cache_mode       = "CACHE_ALL_STATIC" # pull/origin strategy: cache static assets, honor TTL headers
    client_ttl       = var.cdn_default_ttl_seconds
    default_ttl      = var.cdn_default_ttl_seconds
    max_ttl          = 86400
    negative_caching = true

    cache_key_policy {
      include_host         = true
      include_protocol     = true
      include_query_string = true
    }
  }

  backend {
    group = google_compute_region_network_endpoint_group.serverless_neg.id
  }
}

# ── L7 routing (HTTP host/path → backend) ────────────────────────────────────
resource "google_compute_url_map" "default" {
  name            = "opssentinel-urlmap"
  default_service = google_compute_backend_service.default.id
}

# ── TLS termination + global entrypoint ──────────────────────────────────────
resource "google_compute_managed_ssl_certificate" "default" {
  name = "opssentinel-cert"
  managed {
    domains = [var.domain]
  }
}

resource "google_compute_target_https_proxy" "default" {
  name             = "opssentinel-https-proxy"
  url_map          = google_compute_url_map.default.id
  ssl_certificates = [google_compute_managed_ssl_certificate.default.id]
}

resource "google_compute_global_address" "default" {
  name = "opssentinel-lb-ip"
}

resource "google_compute_global_forwarding_rule" "https" {
  name                  = "opssentinel-https-fr"
  load_balancing_scheme = "EXTERNAL_MANAGED"
  target                = google_compute_target_https_proxy.default.id
  ip_address            = google_compute_global_address.default.id
  port_range            = "443"
}
