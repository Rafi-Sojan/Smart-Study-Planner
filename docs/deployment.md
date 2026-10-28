# Deployment and inference operations

## Scope

The repository now contains a containerized FastAPI inference service and a
Kubernetes deployment template. These files are deployment mechanics, not
evidence that the student-risk model is approved for live use. The release
policy in `docs/risk-register.md` still requires prospective validation,
calibration, fairness review, institutional approval, and a documented human
intervention process.

## Model source

The API accepts exactly one model source:

- `MODEL_URI=models:/<registered-name>@candidate` loads a model from the
  configured MLflow/DagsHub registry. This is the preferred deployment path.
- `MODEL_PATH=/models/model.pkl` loads a trusted local pickle only when
  `ALLOW_TRUSTED_PICKLE_MODEL=1`. Set `MODEL_SHA256` to verify the artifact.

The two variables must not be configured together. A registry alias such as
`candidate` is not production approval; promotion requires the quality and
governance gates documented in the risk register.

## Local Docker Compose

The compose file starts the API, Prometheus, Pushgateway, and Grafana. The
local fallback auto-discovers `models/pretrained/model.pkl`; alternatively,
set `MODEL_URI` and MLflow credentials in a machine-local `.env` file. If a
different local artifact is required, set `MODEL_PATH` explicitly.

```powershell
$env:GRAFANA_ADMIN_PASSWORD = "change-this-locally"
$env:ALLOW_TRUSTED_PICKLE_MODEL = "1"
docker compose up --build
```

Useful endpoints are `http://127.0.0.1:8000/healthz`,
`http://127.0.0.1:8000/readyz`, and `http://127.0.0.1:8000/metrics`.
Prometheus is at port 9090 and Grafana is at port 3000. Keep these ports on
localhost unless authentication and network controls are configured.

## Kubernetes deployment

### Automated GitHub Actions deployment

The supported release path is:

1. Push the reviewed changes to `main`.
2. Wait for the Docker workflow to publish the image to GitHub Container
   Registry. It publishes both `latest` and the commit-SHA tag.
3. Use the commit SHA as the deployment image tag. Do not deploy `latest`.
4. In GitHub, open **Settings > Environments**, create or select the
   `production` environment, and add the protected secret
   `KUBE_CONFIG_DATA`.
5. Generate the secret value locally with PowerShell:

```powershell
[Convert]::ToBase64String(
  [IO.File]::ReadAllBytes("$env:USERPROFILE\.kube\config")
)
```

The value is a base64-encoded kubeconfig and must not be committed to Git.
Configure required reviewers on the `production` environment before using it.

6. Open **Actions > Deploy inference service > Run workflow**.
7. Enter the full commit SHA in the `image_tag` field and start the workflow.

The workflow renders `deploy/kubernetes`, replaces the placeholder image with
`ghcr.io/<owner>/<repository>:<image_tag>`, applies the manifests to the
`smart-study-planner` namespace, and waits for the API rollout. The Kubernetes
secret described below must already exist in that namespace; the GitHub
workflow intentionally does not transmit application secrets.

To find the current commit SHA:

```powershell
git rev-parse HEAD
```

After the workflow succeeds, verify the rollout:

```powershell
kubectl -n smart-study-planner get pods
kubectl -n smart-study-planner get service smart-study-planner-api
kubectl -n smart-study-planner rollout status deployment/smart-study-planner-api
```

For temporary local access to the service:

```powershell
kubectl -n smart-study-planner port-forward service/smart-study-planner-api 8000:8000
```

Then check `http://127.0.0.1:8000/healthz` and
`http://127.0.0.1:8000/readyz`.

Create the deployment secret outside Git. The MLflow URI should reference a
registered model that has passed the applicable release gates.

```powershell
kubectl create namespace smart-study-planner
kubectl -n smart-study-planner create secret generic smart-study-planner-secrets `
  --from-literal=MODEL_URI="models:/smart-study-planner-oulad-baseline-hist_gradient_boosting@candidate" `
  --from-literal=MLFLOW_TRACKING_URI="https://dagshub.com/<owner>/<repo>.mlflow" `
  --from-literal=MLFLOW_TRACKING_USERNAME="<username>" `
  --from-literal=MLFLOW_TRACKING_PASSWORD="<token>" `
  --from-literal=API_KEY="<long-random-api-key>" `
  --from-literal=MODEL_VERSION="candidate"
kubectl apply -k deploy/kubernetes
kubectl -n smart-study-planner rollout status deployment/smart-study-planner-api
```

The manifests use two replicas, non-root execution, a read-only root
filesystem, dropped Linux capabilities, resource limits, readiness/liveness
probes, and a service account without an automatically mounted token. Put a
TLS-capable ingress and an authenticated gateway in front of the service
before exposing it outside the cluster.

## Rollback

```powershell
kubectl -n smart-study-planner rollout history deployment/smart-study-planner-api
kubectl -n smart-study-planner rollout undo deployment/smart-study-planner-api
```

Record the image digest, model registry version, metrics artifact, Git commit,
DVC revision, and deployment approval together for every release.
