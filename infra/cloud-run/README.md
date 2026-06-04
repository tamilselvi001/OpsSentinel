# infra/cloud-run — Compute (Cloud Run + Artifact Registry)

Provisions the Artifact Registry repo and deploys the **webhook receiver** (the Phase-1 Cloud Run
workload) **redundantly across parallel regions** — the spec's fault-tolerance principle of
placing redundant Cloud Run regions in parallel. The L7 load balancer in
[`infra/networking`](../networking) fronts them for a single ingress.

## Build, push, deploy

```bash
REGION=us-central1
PROJECT=$GOOGLE_CLOUD_PROJECT
IMAGE=$REGION-docker.pkg.dev/$PROJECT/opssentinel/webhook-receiver:latest

# 1. Build (context = repo root so lib/ is included) and push
docker build -f services/webhook-receiver/Dockerfile -t $IMAGE .
gcloud auth configure-docker $REGION-docker.pkg.dev
docker push $IMAGE

# 2. Deploy via Terraform (creates the repo + a service per region)
terraform -chdir=infra/cloud-run init
terraform -chdir=infra/cloud-run validate
terraform -chdir=infra/cloud-run apply \
  -var project_id=$PROJECT -var image=$IMAGE
```

## Notes

- **Runtime identity** is the least-privilege `sa-webhook-receiver` SA (Pub/Sub publish only),
  created in [`infra/iam`](../iam). No default service account, no Editor.
- **Probes** use `/ready` (startup) and `/health` (liveness).
- **Multi-region:** `var.regions` defaults to `["us-central1","us-east1"]`. Each gets its own
  Cloud Run service; the global L7 LB load-balances across both, so a region outage is absorbed.
- The container runs as a **non-root** user (see the Dockerfile).
