# Monitoring, alerting, and recovery operations

## Monitoring layers

The service exposes aggregate request counts and latency histograms at
`/metrics`. Prometheus scrapes the API and Pushgateway; Grafana visualizes the
time series; Alertmanager groups active alerts. The local Compose stack binds
all management interfaces to localhost.

`monitoring/alerts.yml` defines alerts for API unavailability, server-error
rate, p95 latency, missing or stale batch heartbeats, and aggregate drift
warnings. Alertmanager's repository configuration retains alerts in its UI.
An operator must configure an institution-approved email, pager, or webhook
receiver before claiming out-of-band notification.

`.github/workflows/monitoring.yml` performs a separate HTTPS check every 15
minutes. It verifies liveness, readiness, the model threshold, and the feature
contract hash. Configure the protected production environment with
`PRODUCTION_BASE_URL` and `API_KEY`. A failed workflow is an operational alert
through GitHub Actions; it does not replace cluster monitoring.

Privacy-preserving drift checks can be run with:

```powershell
python -m pipeline.monitoring_pipeline `
  --reference reference_features.csv `
  --current current_features.csv `
  --output artifacts/monitoring/drift.json `
  --pushgateway-url http://localhost:9091 `
  --fail-on-warning
```

Only aggregate change counts are pushed. Row-level features and student
identifiers are not exported to Prometheus.

## Recovery and rollback

Every deployment uses an immutable image tag, numeric MLflow model version,
and release-specific Kubernetes secret. The deployment revision therefore
retains the image, model URI, threshold, and contract configuration needed for
a coherent rollback. Release secrets are not deleted automatically.

Use **Actions > Production recovery and rollback** with `status` for a
read-only audit. `rollback` and `restart` require the exact confirmation
`RECOVER` and the protected production environment approval. The workflow
captures pre- and post-operation deployment state, rollout history, resource
status, events, and HTTPS readiness evidence. A specific revision can be
provided; otherwise Kubernetes selects the preceding revision.

After a successful rollback, operators must verify the model metadata endpoint,
review Prometheus and Alertmanager, record the incident, and decide whether to
revoke the failed model version or image. Do not delete the failed evidence.

## Backup and restore boundary

Git and DVC provide source and dataset version history; DagsHub MLflow retains
run artifacts and registered versions; GHCR retains images; and Kubernetes
retains deployment revisions and release secrets. Before real deployment, the
institution must configure retention and independent backup policies for each
external system and perform a restore drill in a non-production cluster.

The repository does not fabricate a recovery-time objective, recovery-point
objective, successful backup, or successful restore. Those values require the
actual cluster, registry, DVC remote, access policy, and measured drill logs.
Release approval remains blocked until ownership, retention, RTO/RPO, and a
dated restore result are recorded.
