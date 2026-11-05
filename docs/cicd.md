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
6. DVC graph validation;
7. structural validation of all repository notebooks;
8. generation of a small synthetic smoke dataset;
9. a synthetic baseline run;
10. the model-quality gate for every generated cutoff;
11. a loaded-model FastAPI inference smoke request;
12. formal fairness calculations and gate behavior through controlled tests;
13. deployment and monitoring YAML plus Compose validation;
14. execution of the synthetic analysis notebooks; and
15. synthetic relational-integrity validation.

The synthetic smoke run is a reproducibility and software-integrity check. It
does not validate the synthetic data as real student evidence.

The OULAD, EdNet, KU Leuven, and cross-dataset statistical-validation notebooks
are structurally validated in the ordinary CI checkout but are not executed
there because their licensed raw inputs are intentionally absent. Notebook 12
also requires the full synthetic release and real-world comparison inputs. A
data-qualified local or scheduled run can execute them with
`python -m pipeline.validate_notebooks --execute` after the permitted data has
been obtained.

## 3. Container verification and publication

`.github/workflows/docker.yml` builds the container on pull requests and on
pushes to `main`. Pull requests build without publishing. A push to `main`
publishes image tags for `latest`, a short SHA, and the full commit SHA to GitHub Container
Registry.

The deployment should use the immutable commit-SHA tag or an image digest,
not `latest`. The Dockerfile runs as a non-root user and does not copy raw
datasets or model artifacts into the image. Runtime model loading is configured
through the registry or a read-only mounted artifact.

## 4. Manual deployment

`.github/workflows/deploy.yml` is triggered manually with the full 40-character
commit SHA. It verifies and downloads the immutable numeric MLflow version,
checks its deployment, fairness, threshold, and feature-contract tags, creates
private-GHCR and release-specific application secrets, applies the TLS ingress
and workload controls, verifies public readiness, and retains deployment
evidence. Required protected values are listed in `docs/deployment.md`.

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

## 6. Scheduled validation and monitoring

`.github/workflows/data-validation.yml` performs a credentialed weekly DVC
restore and reproduces OULAD/synthetic statistical evidence. The separate
`.github/workflows/monitoring.yml` checks production HTTPS liveness, readiness,
threshold metadata, and feature-contract metadata every 15 minutes. These
jobs require protected DagsHub and production configuration; they do not place
restricted data in Git.

## 7. Rollback

Kubernetes retains deployment revisions and their release-specific model
configuration. The supported path is the protected
`.github/workflows/recovery.yml` workflow, which requires explicit confirmation
for mutation and uploads before/after evidence. Operators may inspect history
locally with:

```powershell
kubectl -n smart-study-planner rollout history deployment/smart-study-planner-api
kubectl -n smart-study-planner rollout undo deployment/smart-study-planner-api
```

After rollback, verify `/readyz`, inspect Prometheus error and latency metrics,
confirm the loaded model version, and record the incident. A rollback does not
replace investigation of the model, data, or intervention failure.

## 8. Current verification boundary

The repository can validate source code, tests, quality reports, workflow YAML,
and manifest syntax locally. A real Docker build, registry push, Kubernetes
rollout, DagsHub registration, and production approval require external
services and credentials; they must not be reported as complete unless their
logs and identifiers are available.
