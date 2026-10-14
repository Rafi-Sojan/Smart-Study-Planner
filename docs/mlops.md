# DVC, DagsHub, and MLflow setup

This repository uses Git for code and configuration, DVC for the OULAD data
and generated model artifact, and DagsHub-hosted MLflow for experiment
tracking. The raw CSV files and trained binary are never committed directly
to Git.

The configured repository target is inferred from the current Git remote:
`Rafi-Sojan/Smart-Study-Planner`. If your DagsHub repository has a different
owner or name, replace those values in the commands below.

## 1. Install the pinned MLOps dependencies

From the project root:

```powershell
python -m pip install -r requirements.txt
```

The pinned additions are `dvc[s3]`, `dagshub`, and `mlflow`.

## 2. Initialize DVC

Run this once in the Git repository:

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

The DagsHub Data/DVC panel provides equivalent commands if the repository
owner or name differs.

## 3. Version the OULAD data

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

Push the data cache only after the DagsHub remote credentials are configured:

```powershell
dvc push -r origin
```

Then commit and push the pointer/configuration files through Git:

```powershell
git add .dvc .gitignore dvc.yaml dvc.lock data/raw/oulad.dvc models/metrics/metrics.json models/metrics/early_warning_metrics.json
git commit -m "Set up DVC data pipeline"
git push origin main
```

Do not use `git add data/raw/oulad` or `git add data/processed/oulad`; those
directories are intentionally ignored.

## 4. Configure DagsHub MLflow

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
  --experiment-name smart-study-planner-oulad
```

The run logs the selected model, split metadata, metrics for all four
classifiers, `metrics.json`, and the trained model artifact. Without
`--mlflow`, the pipeline remains fully local and does not require credentials.

The code also supports the DagsHub client configuration. Instead of setting
`MLFLOW_TRACKING_URI`, set `DAGSHUB_REPO_OWNER` and `DAGSHUB_REPO_NAME`; the
tracking helper then calls `dagshub.init` when `--mlflow` is used.

## 5. Recommended order for the first setup

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
