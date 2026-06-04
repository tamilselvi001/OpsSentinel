variable "project_id" {
  type    = string
  default = "opssentinel-mvp"
}

variable "primary_region" {
  type    = string
  default = "us-central1"
}

variable "regions" {
  type        = list(string)
  description = "Deploy the service redundantly across these regions (parallel availability)."
  default     = ["us-central1", "us-east1"]
}

variable "service_name" {
  type    = string
  default = "webhook-receiver"
}

variable "image" {
  type        = string
  description = "Container image (Artifact Registry). Built+pushed before apply."
  default     = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/webhook-receiver:latest"
}

variable "service_account_email" {
  type        = string
  description = "Least-privilege runtime SA (Pub/Sub publish only). Created in infra/iam."
  default     = "sa-webhook-receiver@opssentinel-mvp.iam.gserviceaccount.com"
}

variable "min_instances" {
  type    = number
  default = 0
}

variable "max_instances" {
  type    = number
  default = 10
}

# ── Phase 2: MCP server images + runtime identities ──────────────────────────
variable "mcp_elastic_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/mcp-elastic:latest"
}

variable "mcp_arize_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/mcp-arize:latest"
}

variable "mcp_elastic_sa" {
  type        = string
  description = "Least-privilege SA (per-secret accessor for elastic-*). Created in infra/iam."
  default     = "sa-mcp-elastic@opssentinel-mvp.iam.gserviceaccount.com"
}

variable "mcp_arize_sa" {
  type        = string
  description = "Least-privilege SA (per-secret accessor + Cloud SQL connect). Created in infra/iam."
  default     = "sa-mcp-arize@opssentinel-mvp.iam.gserviceaccount.com"
}
