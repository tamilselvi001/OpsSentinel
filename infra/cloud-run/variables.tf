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

# ── Phase 3: agent image + runtime identity ──────────────────────────────────
variable "agent_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/agent:latest"
}

variable "agent_sa" {
  type        = string
  description = "Least-privilege agent SA (Pub/Sub sub+publish, Cloud SQL, secret accessor). infra/iam."
  default     = "sa-agent@opssentinel-mvp.iam.gserviceaccount.com"
}

# ── Phase 4: frontend image + identity (service name must match the networking NEG target) ───
variable "frontend_service_name" {
  type    = string
  default = "opssentinel-frontend"
}

variable "frontend_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/frontend:latest"
}

variable "frontend_sa" {
  type        = string
  description = "Least-privilege frontend SA (secret accessor + Cloud SQL read). Created in infra/iam."
  default     = "sa-frontend-backend@opssentinel-mvp.iam.gserviceaccount.com"
}

# ── Phase 5: slack-bot image + identity ──────────────────────────────────────
variable "slack_bot_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/opssentinel-mvp/opssentinel/slack-bot:latest"
}

variable "slack_bot_sa" {
  type        = string
  description = "Least-privilege slack-bot SA (publish to actions + Cloud SQL + its secrets). infra/iam."
  default     = "sa-slack-bot@opssentinel-mvp.iam.gserviceaccount.com"
}
