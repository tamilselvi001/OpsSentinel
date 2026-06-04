variable "project_id" {
  type    = string
  default = "opssentinel-mvp"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "frontend_service" {
  type        = string
  description = "Cloud Run service the serverless NEG targets. Attached in Phase 4 (Member 4)."
  default     = "opssentinel-frontend"
}

variable "domain" {
  type        = string
  description = "Domain for the managed SSL cert (the LB's public hostname)."
  default     = "dashboard.opssentinel.example.com"
}

variable "cdn_default_ttl_seconds" {
  type    = number
  default = 3600
}
