provider "google" {
  project = var.project_id
}

# Create every secret named in the shared contract — EMPTY (no version). Real values are added
# out-of-band (`gcloud secrets versions add ...`) so no credential is ever committed. Services
# read the latest version at runtime via lib/secrets.get_secret().
resource "google_secret_manager_secret" "secret" {
  for_each  = toset(var.secret_names)
  secret_id = each.value

  replication {
    auto {}
  }
}
