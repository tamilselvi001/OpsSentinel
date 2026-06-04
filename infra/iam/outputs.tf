output "service_account_emails" {
  value       = { for k, sa in google_service_account.svc : k => sa.email }
  description = "Per-service SA emails (wire these into each service's runtime identity)."
}
