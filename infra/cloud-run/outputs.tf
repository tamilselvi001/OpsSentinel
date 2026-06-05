output "service_urls" {
  value       = { for region, svc in google_cloud_run_v2_service.webhook_receiver : region => svc.uri }
  description = "Per-region webhook receiver URLs."
}

output "artifact_registry_repo" {
  value       = google_artifact_registry_repository.containers.id
  description = "Artifact Registry repository for service images."
}

output "mcp_elastic_url" {
  value       = google_cloud_run_v2_service.mcp_elastic.uri
  description = "Elastic MCP server URL (internal ingress)."
}

output "mcp_arize_url" {
  value       = google_cloud_run_v2_service.mcp_arize.uri
  description = "Arize Phoenix MCP server URL (internal ingress)."
}

output "agent_url" {
  value       = google_cloud_run_v2_service.agent.uri
  description = "Agent service URL (internal ingress; /health only)."
}

output "frontend_service_name" {
  value       = google_cloud_run_v2_service.frontend.name
  description = "Frontend Cloud Run service name (the networking NEG attaches to this)."
}
