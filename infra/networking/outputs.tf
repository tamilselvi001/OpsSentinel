output "load_balancer_ip" {
  value       = google_compute_global_address.default.address
  description = "Global anycast IP. Point the domain's A record here, then the managed cert provisions."
}

output "serverless_neg" {
  value       = google_compute_region_network_endpoint_group.serverless_neg.id
  description = "Serverless NEG the Phase-4 frontend attaches to."
}
