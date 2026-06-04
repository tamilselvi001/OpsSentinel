provider "google" {
  project = var.project_id
  region  = var.region
}

# Application DB password — generated, never committed. Surface it into the `database-url`
# Secret Manager secret (see infra/secret-manager) rather than into any file.
resource "random_password" "db" {
  length  = 28
  special = false
}

# Cloud SQL for PostgreSQL — GCP's managed realization of the spec's Active-Passive
# (Master-Slave) topology. `REGIONAL` availability provisions a synchronously-replicated
# standby in a second zone with continuous heartbeats and automatic failover behind a shared
# IP, targeting 99.99% availability. This is the CP side of the system (strong ACID consistency).
resource "google_sql_database_instance" "incident_store" {
  name             = var.instance_name
  database_version = var.database_version
  region           = var.region

  settings {
    tier              = var.tier
    availability_type = "REGIONAL" # Active-Passive HA: synchronous standby + automatic failover
    disk_autoresize   = true
    disk_type         = "PD_SSD"

    backup_configuration {
      enabled                        = true
      point_in_time_recovery_enabled = true # WAL archiving for PITR
      transaction_log_retention_days = 7
      start_time                     = "03:00"
    }

    insights_config {
      query_insights_enabled = true
    }

    # MVP: public IP gated by authorized networks. For production, switch to a private IP via
    # a VPC + Serverless VPC Access connector (documented in README).
    ip_configuration {
      ipv4_enabled = true
    }
  }

  # Protect the system of record from accidental destruction.
  deletion_protection = true
}

resource "google_sql_database" "app" {
  name     = var.db_name
  instance = google_sql_database_instance.incident_store.name
}

resource "google_sql_user" "app" {
  name     = var.db_user
  instance = google_sql_database_instance.incident_store.name
  password = random_password.db.result
}
