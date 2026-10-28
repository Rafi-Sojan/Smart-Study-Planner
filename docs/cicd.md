# CI/CD and release operations

## 1. Purpose

GitHub Actions provides repeatable verification and controlled delivery for
the repository. CI is the authoritative automated gate for source changes.
The deployment workflow is deliberately manual because deployment requires
institutional approval, cluster credentials, registry secrets, and a reviewed
model version.

## 2. Continuous integration

`.github/workflows/ci.yml` runs on pushes and pull requests targeting `main`
or `develop`, and on manual dispatch. It performs:

1. installation of the pinned Python dependencies;
2. Ruff linting;
3. the complete PyTest suite;
4. whitespace validation;
5. Python dependency auditing with the documented DVC DiskCache exception;
6. generation of a small synthetic smoke dataset;
7. a synthetic baseline run;
8. the model-quality gate for every generated cutoff; and
9. synthetic relational-integrity validation.

The synthetic smoke run is a reproducibility and software-integrity check. It
does not validate the synthetic data as real student evidence.

## 3. Container verification and publication

`.github/workflows/docker.yml` builds the container on pull requests and on
pushes to `main`. Pull requests build without publishing. A push to `main`
publishes image tags for `latest` and the commit SHA to GitHub Container
Registry.

The deployment should use the immutable commit-SHA tag or an image digest,
not `latest`. The Dockerfile runs as a non-root user and does not copy raw
datasets or model artifacts into the image. Runtime model loading is configured
through the registry or a read-only mounted artifact.

## 4. Manual deployment

`.github/workflows/deploy.yml` is triggered manually with an `image_tag`
input. It requires the protected environment secrets:

- `KUBE_CONFIG_DATA`: base64-encoded kubeconfig;
- `KUBE_NAMESPACE`: target namespace; and
- the Kubernetes secret `smart-study-planner-secrets`, containing MLflow
  connection values, the model URI, API key, and model version.

The workflow applies `deploy/kubernetes`, sets the deployment image to the
requested tag, and waits for rollout completion. Configure the GitHub
environment with required reviewers before allowing production deployment.

## 5. Required release evidence

Before dispatching deployment, retain:

1. the Git commit and CI run URL;
2. the container image digest;
3. the DVC data and pipeline revision;
4. the MLflow run ID and registered model version;
5. the model-quality report;
6. calibration and subgroup review outputs;
7. approval for the intervention policy; and
8. the rollback target and responsible operator.

If any item is unavailable, the release is not reproducible and must remain a
research or candidate artifact.

## 6. Rollback

Kubernetes retains deployment revisions. Operators can inspect history and
roll back with:

```powershell
kubectl -n smart-study-planner rollout history deployment/smart-study-planner-api
kubectl -n smart-study-planner rollout undo deployment/smart-study-planner-api
```

After rollback, verify `/readyz`, inspect Prometheus error and latency metrics,
confirm the loaded model version, and record the incident. A rollback does not
replace investigation of the model, data, or intervention failure.

## 7. Current verification boundary

The repository can validate source code, tests, quality reports, workflow YAML,
and manifest syntax locally. A real Docker build, registry push, Kubernetes
rollout, DagsHub registration, and production approval require external
services and credentials; they must not be reported as complete unless their
logs and identifiers are available.
