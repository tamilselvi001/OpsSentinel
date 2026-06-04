variable "project_id" {
  type        = string
  description = "GCP project id."
  default     = "opssentinel-mvp"
}

variable "region" {
  type        = string
  description = "Primary region."
  default     = "us-central1"
}

variable "alerts_topic" {
  type        = string
  description = "Ingest topic — the normalized event queue."
  default     = "opssentinel-alerts"
}

variable "alerts_subscription" {
  type        = string
  description = "Agent Layer pull subscription."
  default     = "opssentinel-alerts-sub"
}

variable "dlq_topic" {
  type        = string
  description = "Dead-letter topic — a poison message can never drop an alert."
  default     = "opssentinel-alerts-dlq"
}

variable "actions_topic" {
  type        = string
  description = "Outbound approved-action channel (consumed in Phase 3/5; provisioned here per the Queue-Layer contract)."
  default     = "opssentinel-actions"
}

variable "max_delivery_attempts" {
  type        = number
  description = "Deliveries before a message is dead-lettered."
  default     = 5
}

variable "ack_deadline_seconds" {
  type        = number
  description = "Ack deadline for the agent subscription."
  default     = 60
}
