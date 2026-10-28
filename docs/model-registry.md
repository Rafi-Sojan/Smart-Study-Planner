# Model registry and lifecycle specification

## 1. Purpose and system boundary

DagsHub-hosted MLflow is the system of record for experiment runs, MLflow
model artifacts, and registered model versions. Git remains the system of
record for source code and configuration. DVC remains the system of record for
versioned datasets and generated artifacts. Prometheus and Grafana are used
for operational observations and are not model registries.

This separation makes it possible to identify the code revision, DVC data
revision, evaluation report, and registered model version associated with a
run. No registry credential or token may be committed to this repository.

## 2. Registration lifecycle

The controlled lifecycle is:

1. train the model with a reproducible pipeline;
2. write the metrics and provenance report;
3. run the model-quality gate;
4. log the run and MLflow-format model artifact;
5. register the version with evidence and quality tags;
6. review the candidate against the release policy; and
7. promote only after prospective, institutional, safety, and governance
   requirements are satisfied.

The implementation in `src/tracking/model_registry.py` registers a model,
attaches tags, and assigns the `candidate` alias. The alias identifies the
current reviewed candidate for a registry name; it is not production approval.

## 3. Naming conventions

Full-course OULAD models use the form:

```text
smart-study-planner-oulad-baseline-<model-name>
```

Early-warning selected models use:

```text
smart-study-planner-oulad-early-warning-day-<cutoff>
```

Synthetic comparison models use:

```text
smart-study-planner-synthetic-baseline-day-<cutoff>-<model-name>
```

The registered name identifies the task and model family. The MLflow run and
version identify the exact training event and artifact.

## 4. Required tags and restrictions

Full-course registrations include:

- `quality_gate_passed`;
- `deployment_eligible`;
- `evidence_type`; and
- `deployment_claim`.

Early-warning and synthetic registrations additionally include
`development_only`, `cutoff_days`, and `model_name` where applicable. These
tags preserve the distinction between retrospective, synthetic, and
prospective evidence inside the registry.

Synthetic models must remain development-only. A model must not be deployed
because it has the highest benchmark score, because it has a high accuracy,
or because it is registered.

## 5. DagsHub configuration

Use a machine-local PowerShell session or a secret manager:

```powershell
$env:MLFLOW_TRACKING_URI = "https://dagshub.com/<owner>/<repo>.mlflow"
$env:MLFLOW_TRACKING_USERNAME = "<username>"
$env:MLFLOW_TRACKING_PASSWORD = "<DAGSHUB_TOKEN>"
```

Run registration explicitly:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --mlflow `
  --register-models
```

For synthetic development comparisons:

```powershell
python -m pipeline.synthetic_baseline_pipeline `
  --data-dir data/raw/synthetic `
  --mlflow `
  --register-models
```

The command must be run only after the data and code state have been recorded.
The exact run identifier, Git commit, DVC revision, and metrics artifact must
be retained in the experiment record.

## 6. Inference selection

The FastAPI service loads a registry model using an MLflow URI such as:

```text
models:/smart-study-planner-oulad-baseline-hist_gradient_boosting@candidate
```

The service accepts either an MLflow `models:/` or `runs:/` URI, or a verified
trusted local pickle. `MODEL_URI` and `MODEL_PATH` are mutually exclusive.
Local pickle loading requires `ALLOW_TRUSTED_PICKLE_MODEL=1` and may require a
matching `MODEL_SHA256` value.

## 7. Rollback and de-registration

Rollback must select a previously reviewed model version or deployment image.
Do not delete a registered version merely because it is no longer active;
retain it for reproducibility, audit, and incident investigation. Revoke or
rotate registry credentials if exposure is suspected, and record the event in
the operational incident log.
