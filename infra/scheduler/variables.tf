variable "project_id" {
  type    = string
  default = "opssentinel-mvp"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "inference_daily_cap" {
  type        = number
  description = "Hard daily ceiling on LLM/API invocations (enforced by the Agent in Phase 3)."
  default     = 5000
}

variable "timezone" {
  type    = string
  default = "Etc/UTC"
}
