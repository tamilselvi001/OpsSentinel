output "secret_ids" {
  value       = [for s in google_secret_manager_secret.secret : s.secret_id]
  description = "All provisioned secret ids (values added out-of-band)."
}
