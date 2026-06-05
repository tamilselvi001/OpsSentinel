variable "project_id" {
  type    = string
  default = "opssentinel-mvp"
}

variable "secret_names" {
  type        = list(string)
  description = "Every secret in the shared contract. Created empty; versions added out-of-band."
  default = [
    "gemini-api-key",
    "elastic-url",
    "elastic-api-key",
    "phoenix-collector-endpoint",
    "phoenix-api-key",
    "slack-bot-token",
    "slack-signing-secret",
    "google-oauth-client-id",
    "database-url",
    "session-secret",
  ]
}
