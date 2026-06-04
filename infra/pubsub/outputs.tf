output "alerts_topic" {
  value       = google_pubsub_topic.alerts.id
  description = "Ingest topic id."
}

output "alerts_subscription" {
  value       = google_pubsub_subscription.alerts_sub.id
  description = "Agent pull subscription id."
}

output "dlq_topic" {
  value       = google_pubsub_topic.dlq.id
  description = "Dead-letter topic id."
}

output "actions_topic" {
  value       = google_pubsub_topic.actions.id
  description = "Approved-action topic id."
}
