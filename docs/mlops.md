# MLOps and experiment-management procedures

## Purpose and responsibilities

This document defines the repository procedures for data versioning,
pipeline reproduction, experiment tracking, and model registration. Git is
used for source code and configuration, DVC is used for the OULAD data and
generated model artifact, and DagsHub-hosted MLflow is used for experiment
tracking and model registration. Raw CSV files and trained binary artifacts
are not committed directly to Git.

The configured repository target is inferred from the current Git remote:
`Rafi-Sojan/Smart-Study-Planner`. If the DagsHub repository has a different
owner or name, replace those values in the commands below.

## Reproducibility rationale

The separation between Git, DVC, and MLflow reflects the different types of
state in the project. Git records the code and configuration that define a
transformation; DVC records the data and generated artifacts used by that
transformation; and MLflow records run parameters, metrics, artifacts, and
registered model versions. This separation permits a reported metric to be
traced to both the implementation and the data version that produced it.

The metrics JSON files are retained as small, reviewable reports. They contain
measured outputs rather than assumptions about model quality. A new experiment
should therefore create a new run and should not overwrite a previous result
without recording the changed data, code, parameters, and evaluation split.
The pipelines also record a deterministic data-directory hash, feature-schema
version, runtime, platform, and Git commit when available. Credentials are
never included in this provenance.

## 1. Install the pinned dependencies

From the project root:

```powershell
python -m pip install -r requirements.txt
```

The pinned additions are `dvc[s3]`, `dagshub`, and `mlflow`.

## 2. Configure DVC

Run the following commands once from the Git repository root:

```powershell
dvc init
dvc remote add -d origin s3://dvc
dvc remote modify origin endpointurl https://dagshub.com/Rafi-Sojan/Smart-Study-Planner.s3
```

The endpoint and remote name are safe to commit. Do not put a token in
`.dvc/config`; keep credentials in the machine-local DVC config:

```powershell
dvc remote modify --local origin access_key_id <DAGSHUB_TOKEN>
dvc remote modify --local origin secret_access_key <DAGSHUB_TOKEN>
```

The DagsHub Data/DVC panel provides equivalent commands when the repository
owner or name differs.

## 3. Version the OULAD data and pipeline outputs

The supplied archive must already be extracted to `data/raw/oulad/`:

```powershell
dvc add data/raw/oulad
dvc repro
dvc status
```

`dvc add` creates the small Git-tracked pointer
`data/raw/oulad.dvc`; the CSV content remains in DVC storage. The generated
metrics JSON remains a small Git-tracked report, while DVC versions the raw
and processed data plus the model artifact. `dvc repro`
runs the stages in `dvc.yaml`:

1. `clean` creates `data/processed/oulad/` from the raw tables.
2. `train` compares the four baselines and writes the selected model and
   metrics.
3. `early_warning` evaluates the same four baselines at course-relative days
   30, 60, and 90 using the time-aware presentation holdout, and writes
   `models/metrics/early_warning_metrics.json`.

Push the DVC cache only after the DagsHub remote credentials have been
configured:

```powershell
dvc push -r origin
```

Commit and push the pointer and configuration files through Git:

```powershell
git add .dvc .gitignore dvc.yaml dvc.lock data/raw/oulad.dvc models/metrics/metrics.json models/metrics/early_warning_metrics.json
git commit -m "Set up DVC data pipeline"
git push origin main
```

Do not use `git add data/raw/oulad` or `git add data/processed/oulad`; those
directories are intentionally ignored.

## 4. Configure DagsHub MLflow tracking

DagsHub provides an MLflow tracking endpoint at:

```text
https://dagshub.com/Rafi-Sojan/Smart-Study-Planner.mlflow
```

For the current PowerShell session, set the endpoint and credentials without
writing the token to the repository:

```powershell
$env:MLFLOW_TRACKING_URI = "https://dagshub.com/Rafi-Sojan/Smart-Study-Planner.mlflow"
$env:MLFLOW_TRACKING_USERNAME = "Rafi-Sojan"
$env:MLFLOW_TRACKING_PASSWORD = "<DAGSHUB_TOKEN>"
```

Then run the pipeline with tracking explicitly enabled:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/metrics.json `
  --model-output models/baseline.pkl `
  --mlflow `
  --experiment-name smart-study-planner-oulad `
  --register-models
```

The run logs the selected model, split metadata, metrics for all four
classifiers, `metrics.json`, and the trained model artifact. Without
`--mlflow`, the pipeline remains fully local and does not require tracking
credentials. With `--register-models`, all four full-course model artifacts
are saved in MLflow-compatible format and registered as versioned models.
Registration is not promotion: the model remains a candidate until the risk
register release gates are completed.

For the leakage-safe early-warning pipeline, use:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/early_warning_metrics.json `
  --cutoffs-days 30 60 90 `
  --mlflow `
  --register-models
```

This logs all four model comparisons at each cutoff and registers the selected
model as a separate versioned MLflow model for days 30, 60, and 90. The
registration path uses uploaded MLflow-format artifacts and a `runs:/` model
URI, which is compatible with the connected DagsHub MLflow server.

For the synthetic planner baseline pipeline, use the following local command:

```powershell
python -m pipeline.synthetic_baseline_pipeline `
  --data-dir data/raw/synthetic `
  --metrics-output models/metrics/synthetic_baseline_metrics.json `
  --model-dir models/synthetic_baseline `
  --cutoffs-days 30 60 90
```

To log the run and register all four candidate models at each cutoff:

```powershell
python -m pipeline.synthetic_baseline_pipeline `
  --data-dir data/raw/synthetic `
  --mlflow `
  --register-models `
  --experiment-name smart-study-planner-synthetic-baseline `
  --run-name synthetic-baseline-registered-models
```

The registered names use the form
`smart-study-planner-synthetic-baseline-day-<cutoff>-<model>`. This produces
twelve registered versions per run: four candidate models for each of days
30, 60, and 90. The selected model is recorded in the run parameters, while
all candidate metrics and MLflow-format model artifacts are retained for
comparison. These are synthetic development artifacts, not validated student
support models.

The code also supports the DagsHub client configuration. Instead of setting
`MLFLOW_TRACKING_URI`, set `DAGSHUB_REPO_OWNER` and `DAGSHUB_REPO_NAME`; the
tracking helper then calls `dagshub.init` when `--mlflow` is used.

## 5. Configure Grafana monitoring

Grafana is an operational monitoring layer and is intentionally separate from
DVC and MLflow. DVC versions data and generated artifacts; MLflow records
experiments and registered models; Prometheus stores time-series monitoring
values; and Grafana visualizes those values.

The repository provisions Grafana, Prometheus, and Pushgateway through
`docker-compose.yaml`. Start the stack from the project root:

```powershell
docker compose up -d
```

The services are available at:

```text
Grafana:     http://localhost:3000
Prometheus:  http://localhost:9090
Pushgateway: http://localhost:9091
```

The Prometheus data source and the starter dashboard are provisioned from
`monitoring/grafana/provisioning/` and
`monitoring/grafana/dashboards/smart-study-planner.json`.

The training and early-warning pipelines are short-lived batch jobs. They
publish metrics to Pushgateway only when a URL is explicitly supplied or the
`PROMETHEUS_PUSHGATEWAY_URL` environment variable is set:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --pushgateway-url http://localhost:9091

python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --cutoffs-days 30 60 90 `
  --pushgateway-url http://localhost:9091
```

The exporter reports sample counts, last-success timestamps, full-course model
metrics, and cutoff-specific early-warning metrics. The integration is
opt-in so that ordinary local and DVC runs remain independent of Docker.
Pushgateway retains pushed series until they are removed, so stale batch-job
series must be managed if the monitoring stack is used continuously.

The monitoring utilities also support privacy-preserving schema, missingness,
and numeric-quantile drift checks. They report aggregates and do not write
student identifiers or row-level values. Monitoring does not replace a review
of calibration, subgroup performance, intervention outcomes, or data quality.

## 6. Initial setup sequence

```powershell
python -m pip install -r requirements.txt
dvc init
dvc remote add -d origin s3://dvc
dvc remote modify origin endpointurl https://dagshub.com/Rafi-Sojan/Smart-Study-Planner.s3
dvc remote modify --local origin access_key_id <DAGSHUB_TOKEN>
dvc remote modify --local origin secret_access_key <DAGSHUB_TOKEN>
dvc add data/raw/oulad
dvc repro
dvc push -r origin
```

Run the MLflow command separately after setting its session environment
variables. This keeps data versioning and experiment tracking independently
reproducible.

Official references: [DagsHub DVC integration](https://dagshub.com/docs/integration_guide/dvc/), [DagsHub MLflow tracking](https://dagshub.com/docs/integration_guide/mlflow_tracking/), and [DagsHub setup functions](https://dagshub.com/docs/client/reference/setup).
