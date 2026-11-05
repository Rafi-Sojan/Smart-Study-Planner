# Deployment and inference operations

## Release boundary

The repository contains deployable mechanics, but the current retrospective
OULAD and synthetic models are not production eligible. The production
workflow requires prospective institutional evidence, a configured
intervention policy, and a passing formal fairness gate. Registration or high
benchmark accuracy is not approval.

## Local container verification

For local research, the API can load a trusted pickle from the read-only model
mount. An explicit threshold is recommended:

```powershell
$env:GRAFANA_ADMIN_PASSWORD = "replace-with-a-local-secret"
$env:MODEL_PATH = "/models/model.pkl"
$env:MODEL_THRESHOLD = "0.35"
$env:ALLOW_TRUSTED_PICKLE_MODEL = "1"
docker compose up --build
```

Compose starts the API, Prometheus, Pushgateway, Alertmanager, and Grafana on
localhost-only ports 8000, 9090, 9091, 9093, and 3000. Local pickle loading is
disabled when `APP_ENV=production`. The serving container uses a read-only root
filesystem and redirects runtime home/cache writes to its temporary `/tmp`
mount, which is size-limited in Kubernetes.

## Production prerequisites

Create a protected GitHub `production` environment with required reviewers.
Configure these environment variables:

| Variable | Purpose |
|---|---|
| `MODEL_URI` | Immutable `models:/<name>/<numeric-version>` URI |
| `MODEL_THRESHOLD` | Must exactly match the registry `operating_threshold` tag |
| `APP_HOST` | DNS hostname served through HTTPS |
| `PRODUCTION_BASE_URL` | HTTPS origin used by scheduled monitoring |
| `TLS_SECRET_NAME` | Kubernetes TLS secret/cert-manager certificate name |
| `INGRESS_CLASS_NAME` | Ingress class; defaults to `nginx` |
| `CERT_MANAGER_CLUSTER_ISSUER` | Cluster issuer; defaults to `letsencrypt-prod` |

Configure these protected secrets:

| Secret | Purpose |
|---|---|
| `KUBE_CONFIG_DATA` | Base64-encoded least-privilege kubeconfig |
| `MLFLOW_TRACKING_URI` | DagsHub/MLflow tracking endpoint |
| `MLFLOW_TRACKING_USERNAME` | Registry account |
| `MLFLOW_TRACKING_PASSWORD` | Registry token |
| `API_KEY` | Long random API credential |
| `GHCR_USERNAME` | Account allowed to read the private image |
| `GHCR_TOKEN` | Fine-grained or classic token with `read:packages` |

The cluster must have an ingress controller, a metrics server for the HPA,
cert-manager or a pre-provisioned TLS secret, and a network-policy provider.
If the ingress or monitoring namespaces differ from `ingress-nginx` and
`monitoring`, review `deploy/kubernetes/networkpolicy.yaml` before deployment.
Before the first release, a platform administrator must create the namespace
with `kubectl apply -f deploy/kubernetes/namespace.yaml`. The deployment
credential is then limited to namespaced resources and does not need permission
to create or modify cluster-scoped namespaces.

## Controlled deployment

1. Push the reviewed commit and wait for CI and the Docker workflow.
2. Confirm GHCR contains the full 40-character commit-SHA tag.
3. Confirm the numeric model version has all required registry tags.
4. Open **Actions > Deploy inference service** and enter the full lowercase
   commit SHA.

The workflow then:

1. validates every required protected value;
2. downloads the registered model and verifies quality, deployment,
   fairness, threshold, and feature-contract metadata;
3. validates cluster permissions;
4. creates or rotates the GHCR pull secret;
5. creates an immutable release-specific application secret;
6. renders and applies TLS, workload, availability, and network manifests;
7. waits for rollout and certificate readiness;
8. verifies public HTTPS readiness; and
9. uploads registry, manifest, image-digest, and rollout evidence.

The release-specific secret binds model URI and threshold to the Kubernetes
deployment revision. This prevents an image rollback from silently retaining a
newer model configuration.

## Verification

```powershell
kubectl -n smart-study-planner get deployment,pod,service,ingress,hpa,pdb
kubectl -n smart-study-planner rollout status deployment/smart-study-planner-api
curl.exe https://<production-host>/healthz
curl.exe https://<production-host>/readyz
curl.exe -H "x-api-key: <api-key>" https://<production-host>/v1/model-metadata
```

The metadata response must show the approved model version, registry threshold,
non-zero feature count, and 64-character contract hash.

## Recovery

Use **Actions > Production recovery and rollback**. `status` is read-only;
`rollback` and `restart` require protected-environment approval and the exact
confirmation `RECOVER`. Provide a Kubernetes revision when a specific release
is required. The workflow verifies HTTPS readiness and uploads before/after
evidence. Full policy and backup boundaries are documented in
`docs/monitoring-and-recovery.md`.

## What remains external

The source repository cannot create institutional approval, DNS, a production
cluster, valid credentials, prospective evidence, or a successful restore
drill. Do not report deployment as complete until external workflow logs,
resource identifiers, certificate state, image digest, model version, and
approval evidence exist.
