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

Open the integrated React application at `http://localhost:8080`. Compose also
starts the API, Prometheus, Pushgateway, Alertmanager, and Grafana on
localhost-only ports 8000, 9090, 9091, 9093, and 3000. Local pickle loading is
disabled when `APP_ENV=production`. Both application containers use read-only
root filesystems and temporary `/tmp` mounts.

Browser authentication is optional only for an isolated local research run.
To test the protected path, generate a verifier interactively and copy the
single printed value:

```powershell
python -m src.api.auth
$env:WEB_AUTH_USERNAME = "planner-admin"
$env:WEB_AUTH_PASSWORD_HASH = "<printed-pbkdf2-verifier>"
$env:SESSION_SECRET = "<at-least-32-random-characters>"
docker compose up --build
```

The browser receives an HttpOnly session cookie. It never receives `API_KEY`.
The Nginx gateway serves the Vite bundle and proxies `/api/*` to FastAPI while
retaining the established `/healthz`, `/readyz`, and `/v1/*` service paths.

### Configuring selectable models

The legacy `MODEL_PATH` or `MODEL_URI` configuration remains valid and appears
as one selectable option. For multiple options, leave both values empty and set
`MODEL_CATALOG_JSON` to a completed private copy of
`configs/model-catalog.example.json`. Set `DEFAULT_MODEL_ID` to the recommended
option. The catalog accepts at most 12 unique, allowlisted models.

For a local PowerShell session:

```powershell
$env:MODEL_PATH = ""
$env:MODEL_URI = ""
$env:MODEL_CATALOG_JSON = Get-Content -Raw configs/model-catalog.local.json
$env:DEFAULT_MODEL_ID = "oulad-day-30"
docker compose up --build
```

Local catalog entries may use trusted paths under `/model-store`, which is a
read-only mount of the repository's `artifacts/models/` directory. Production rejects
every `model_path`: each entry must use an immutable numeric MLflow
`models:/<name>/<version>` URI. The release workflow downloads and verifies the
governance tags, artifact feature contract, approved threshold, and forbidden
feature policy for every catalog entry before rollout.

## Production prerequisites

Create a protected GitHub `production` environment with required reviewers.
Configure these environment variables:

| Variable | Purpose |
|---|---|
| `MODEL_URI` | Immutable `models:/<name>/<numeric-version>` URI |
| `MODEL_THRESHOLD` | Must exactly match the registry `operating_threshold` tag |
| `MODEL_CATALOG_JSON` | Optional allowlist of selectable immutable model versions; replaces `MODEL_URI` and `MODEL_THRESHOLD` |
| `DEFAULT_MODEL_ID` | Required when a catalog is configured; identifies the recommended default |
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
| `WEB_AUTH_USERNAME` | Protected operator login name |
| `WEB_AUTH_PASSWORD_HASH` | Verifier printed by `python -m src.api.auth`; never plaintext |
| `SESSION_SECRET` | Random value of at least 32 characters used to sign sessions |

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
2. Confirm GHCR contains the full 40-character commit-SHA tag for both the API
   image and the `-web` image.
3. Confirm every numeric model version in the catalog has all required registry tags.
4. Open **Actions > Deploy Smart Study Planner** and enter the full lowercase
   commit SHA.

The workflow then:

1. validates every required protected value and confirms that the requested
   commit is reachable from `main`;
2. verifies both full-SHA GHCR tags, resolves their SHA-256 content digests,
   and uses those immutable digest references for the rollout;
3. downloads every configured registered model and verifies quality,
   deployment, fairness, threshold, feature-contract, and serving-policy metadata;
4. validates cluster permissions;
5. creates or rotates the GHCR pull secret;
6. creates an immutable release-specific application secret;
7. renders and applies TLS, API, React/Nginx, availability, and network manifests;
8. waits for both application rollouts and certificate readiness;
9. verifies public HTTPS readiness; and
10. uploads registry, manifest, image-digest, and rollout evidence.

The release-specific secret binds model URI and threshold to the Kubernetes
deployment revision. This prevents an image rollback from silently retaining a
newer model configuration.

## Verification

```powershell
kubectl -n smart-study-planner get deployment,pod,service,ingress,hpa,pdb
kubectl -n smart-study-planner rollout status deployment/smart-study-planner-api
kubectl -n smart-study-planner rollout status deployment/smart-study-planner-web
curl.exe https://<production-host>/
curl.exe https://<production-host>/healthz
curl.exe https://<production-host>/readyz
curl.exe -H "x-api-key: <api-key>" https://<production-host>/v1/models
curl.exe -H "x-api-key: <api-key>" https://<production-host>/v1/model-metadata
```

The catalog must contain the configured default. Metadata for that default must
show the approved model version, registry threshold, non-zero feature count,
and 64-character contract hash. Query a non-default option with
`/v1/model-metadata?model_id=<allowlisted-id>`.

TLS terminates at the Kubernetes ingress. Public traffic reaches the Nginx web
gateway, which applies browser security headers and forwards API calls over the
cluster network. The API is not assigned a public service. The production
session cookie is Secure, HttpOnly, SameSite=Strict, time-limited, and accepted
for state-changing requests only when the Origin check passes.

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
