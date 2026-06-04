variable "project_id" {
  type    = string
  default = "opssentinel-mvp"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "instance_name" {
  type    = string
  default = "opssentinel-incident-store"
}

variable "database_version" {
  type    = string
  default = "POSTGRES_15"
}

variable "tier" {
  type        = string
  description = "Machine tier. HA (REGIONAL) requires a dedicated-core tier."
  default     = "db-custom-1-3840"
}

variable "db_name" {
  type    = string
  default = "opssentinel"
}

variable "db_user" {
  type    = string
  default = "opssentinel"
}
