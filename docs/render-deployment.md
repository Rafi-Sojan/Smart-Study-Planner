# Render research-demonstration deployment

## Scope and release boundary

The repository includes a Render Blueprint for an authenticated research
demonstration. It is not a production-approval path. The current OULAD and
synthetic model evidence remains formally blocked from production by the
model-quality assessment, and the Blueprint therefore sets
`APP_ENV=development` explicitly.

The Render adapter does not weaken the API's production checks. Changing
`APP_ENV` to `production` will activate immutable-registry, deployment-
eligibility, fairness, authentication, and serving-policy requirements. The
current model candidates are expected to fail that production boundary.

## Architecture

`Dockerfile.render` builds one Render web service containing two processes:

1. Nginx serves the compiled React application on Render's public `PORT`.
2. FastAPI listens only on container loopback at `API_PORT`.
3. Nginx forwards `/api/`, `/v1/`, `/healthz`, and `/readyz` to FastAPI.

This arrangement preserves the application's same-origin session-cookie and
Origin-check contract. It also avoids creating a billable Render private
service for a research demonstration. The existing separate API/web Compose
and Kubernetes images remain the supported production-oriented topology.

Prometheus, Pushgateway, Alertmanager, and Grafana are deliberately excluded
from this free demonstration service. The local Compose monitoring stack and
the Kubernetes monitoring configuration are unchanged.

## Files

- `render.yaml`: one-service Render Blueprint;
- `Dockerfile.render`: reproducible combined image;
- `deploy/render/nginx.conf.template`: runtime port and loopback proxy;
- `deploy/render/entrypoint.sh`: validated configuration and two-process
  lifecycle supervision.

## Prerequisites

1. Push the reviewed repository revision to the Git provider connected to
   Render.
2. Have a DagsHub/MLflow registered model referenced by an immutable numeric
   URI such as `models:/<name>/<version>`.
3. Confirm that the registry version has the quality, selected-for-release,
   operating-threshold, feature-count, and feature-contract tags required by
   `src/tracking/model_registry.py`.
4. Generate a browser password verifier locally. The plaintext password is
   never stored in Git or entered as an environment variable.

Generate the verifier:

```powershell
.\.venv\Scripts\python.exe -m src.api.auth
```

The command asks for a password twice and prints one PBKDF2 verifier. Preserve
the plaintext password in an appropriate password manager and copy only the
printed verifier to Render.

Before deploying a research candidate, verify the exact numeric model version
and threshold locally:

```powershell
$env:MLFLOW_TRACKING_URI = "<DagsHub MLflow URI>"
$env:MLFLOW_TRACKING_USERNAME = "<DagsHub username>"
$env:MLFLOW_TRACKING_PASSWORD = "<DagsHub token>"

.\.venv\Scripts\python.exe -m pipeline.verify_registered_model `
  --model-uri "models:/<registered-name>/<numeric-version>" `
  --expected-threshold <registry-threshold> `
  --allow-ineligible `
  --allow-missing-fairness
```

The two `--allow-*` arguments classify this as a research-candidate check. They
must not be used as evidence of production eligibility.

## Create the Render service

1. In the Render Dashboard, choose **New > Blueprint**.
2. Connect the Git repository and select the branch containing `render.yaml`.
3. Review the proposed `smart-study-planner-demo` web service.
4. Supply every value that Render prompts for because it has `sync: false`.
5. Create the Blueprint and monitor the build and deploy logs.

The Blueprint uses the Singapore region and Render's free web-service plan. The
free plan has constrained memory, can spin down when idle, and has an ephemeral
filesystem. The application does not rely on local persistence, but loading
MLflow and a fitted model can exceed the free memory limit. If Render reports an
out-of-memory termination, select a larger compute plan; do not remove model or
security validation to reduce memory.

## Prompted values

| Render key | Required value |
|---|---|
| `WEB_AUTH_USERNAME` | Chosen operator/student-demo login name |
| `WEB_AUTH_PASSWORD_HASH` | PBKDF2 verifier printed by `python -m src.api.auth` |
| `MODEL_URI` | Immutable `models:/<name>/<numeric-version>` URI |
| `MODEL_THRESHOLD` | Exact `operating_threshold` value stored on that registry version |
| `MLFLOW_TRACKING_URI` | DagsHub repository MLflow tracking URL |
| `MLFLOW_TRACKING_USERNAME` | DagsHub account name |
| `MLFLOW_TRACKING_PASSWORD` | DagsHub token, entered as a Render secret |

Render generates `API_KEY` and `SESSION_SECRET`. `ALLOWED_HOSTS` is populated
from Render's own external hostname. No DagsHub token, plaintext browser
password, API key, or session secret belongs in `render.yaml` or `.env.example`.

Render makes runtime environment variables available during Docker builds as
build arguments. `Dockerfile.render` intentionally does not consume any secret
build arguments, preventing credentials from being embedded in an image layer.

## Verification

After the deployment is live, use the assigned HTTPS URL:

```powershell
$renderUrl = "https://<service-name>.onrender.com"
curl.exe "$renderUrl/healthz"
curl.exe "$renderUrl/readyz"
curl.exe -I "$renderUrl/"
```

Expected evidence:

- `/healthz` returns HTTP 200 when the API process is running;
- `/readyz` returns HTTP 200 only after a trusted model is loaded;
- `/` returns the React application with the Nginx security headers;
- browser login accepts the chosen username and the plaintext password that
  corresponds to `WEB_AUTH_PASSWORD_HASH`;
- model metadata identifies the configured numeric registry version.

If `/readyz` fails, inspect Render logs for registry-tag, threshold,
feature-contract, DagsHub authentication, or memory errors. Do not change the
health check to `/healthz` merely to hide an unavailable model.

## Production promotion

This Blueprint must not be relabelled as production merely because it is
publicly reachable. Production requires the external prerequisites and model
evidence in `docs/production-readiness.md`, including prospective institutional
validation and an approved intervention policy. The separate Kubernetes release
workflow remains the governed production design.

Render's current Docker, Blueprint, environment-secret, port, and health-check
contracts are documented by Render:

- <https://render.com/docs/docker>
- <https://render.com/docs/blueprint-spec>
- <https://render.com/docs/configure-environment-variables>
- <https://render.com/docs/health-checks>
- <https://render.com/docs/free>
