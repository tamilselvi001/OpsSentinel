# infra/networking — Serverless NEG + L7 LB + Cloud CDN

Stands up the **basic networking** foundation: a **Serverless Network Endpoint Group (NEG)** that
securely connects an **external Layer-7 (HTTP/S) load balancer** to a Cloud Run service, with L7
routing (host/path), TLS termination, and **Cloud CDN (Pull strategy + TTL headers)** for static
assets. Phase 1 builds the foundation; the **frontend is attached in Phase 4** (Member 4, assisted
by Member 1).

## Components

| Resource | Role |
|---|---|
| `serverless_neg` | NEG targeting the Cloud Run frontend (`var.frontend_service`) |
| `backend_service` | CDN-enabled (`CACHE_ALL_STATIC`, TTL headers, negative caching) |
| `url_map` | L7 routing by application-layer info (host/path) |
| `managed_ssl_certificate` | Google-managed TLS for `var.domain` |
| `target_https_proxy` + `global_forwarding_rule` + `global_address` | Global HTTPS entrypoint (anycast IP, :443) |

## Apply order

```bash
terraform -chdir=infra/networking init
terraform -chdir=infra/networking validate
# Apply AFTER the target Cloud Run frontend exists (Phase 4); the NEG references it by name.
terraform -chdir=infra/networking apply \
  -var project_id=$GOOGLE_CLOUD_PROJECT -var frontend_service=opssentinel-frontend -var domain=$DOMAIN
```

After apply: point the domain's `A` record at the `load_balancer_ip` output; the managed
certificate then provisions automatically. **Ready for the Phase-4 frontend attach.**
