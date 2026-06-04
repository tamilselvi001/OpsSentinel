output "instance_connection_name" {
  value       = google_sql_database_instance.incident_store.connection_name
  description = "Cloud SQL connection name (for the Cloud SQL Auth Proxy / connector)."
}

output "public_ip_address" {
  value       = google_sql_database_instance.incident_store.public_ip_address
  description = "Instance public IP (MVP). Prefer private IP in production."
}

# The full DSN, including the generated password. Sensitive — feed it into the `database-url`
# Secret Manager secret; never write it to a committed file.
output "database_url" {
  value = format(
    "postgresql+psycopg://%s:%s@%s:5432/%s",
    var.db_user,
    random_password.db.result,
    google_sql_database_instance.incident_store.public_ip_address,
    var.db_name,
  )
  sensitive = true
}
