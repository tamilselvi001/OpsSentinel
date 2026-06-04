output "inference_cap_topic" {
  value       = google_pubsub_topic.inference_cap_reset.id
  description = "Topic the Agent subscribes to for daily budget resets."
}

output "sla_check_topic" {
  value       = google_pubsub_topic.sla_check.id
  description = "Topic the Agent subscribes to for the 15-min SLA sweep."
}
