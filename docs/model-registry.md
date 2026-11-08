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

Every newly registered version includes:

- `quality_gate_passed`;
- `deployment_eligible`;
- `fairness_gate_passed`;
- `evidence_type` and `deployment_claim`;
- `operating_threshold` and `threshold_source`;
- `feature_contract_sha256` and `feature_count`; and
- `selected_for_release` and `model_name` where applicable.

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

The operating threshold is selected on validation evidence. A configured
capacity/cost intervention-policy threshold takes precedence; otherwise the
validation-F1 threshold is recorded. The feature-contract digest is computed
from the fitted raw input names in their trained order.
Only the validation-selected model for a task/cutoff can receive
`deployment_eligible=true`; other registered comparison models remain useful
for audit and reproducibility but cannot inherit the selected model's approval.

## 6. Inference selection and verification

The FastAPI service loads a registry model using an MLflow URI such as:

```text
models:/smart-study-planner-oulad-baseline-hist_gradient_boosting/7
```

Aliases remain useful for candidate review, but production requires an
immutable numeric version. Before loading the artifact, the service resolves
the version and verifies registry readiness, source-run identity, explicit
release selection, quality, deployment eligibility, fairness, evidence tags,
threshold provenance, positive feature count, and feature-contract hash. It
then loads the resolved numeric URI and compares the actual fitted feature
count and contract digest with the registry metadata.

The same verification can be run before a release:

```powershell
python -m pipeline.verify_registered_model `
  --model-uri "models:/<registered-name>/<version>" `
  --expected-threshold 0.35 `
  --output artifacts/validation/registry-verification.json
```

The numeric value is configuration syntax, not an approved project threshold.
Local pickle loading remains available for research only and is rejected when
`APP_ENV=production`.

### Approved user-selectable models

A deployment may expose more than one reviewed model through
`MODEL_CATALOG_JSON`. Each catalog entry assigns a stable, non-sensitive
`model_id` and user-facing explanation to one immutable numeric MLflow model
version. `DEFAULT_MODEL_ID` identifies the recommended option. For example,
an institution may expose the approved 30-, 60-, and 90-day OULAD
early-warning versions so that a reviewer can compare evidence windows.

The browser first retrieves `GET /v1/models`, then submits only the selected
`model_id`. It cannot submit a model path, registry URI, alias, or threshold.
The API resolves the identifier against the bounded server-side allowlist and
uses that model's own feature contract and approved operating threshold. An
unknown identifier is rejected with HTTP 422; omitting the identifier retains
backward compatibility by selecting the configured default.

Before production rollout, `pipeline.verify_model_catalog` applies the same
immutability, quality, deployment-eligibility, fairness, threshold,
feature-contract, and forbidden-feature checks to every catalog entry. If any
entry fails, the release fails as a whole. The selector therefore changes
which already approved model serves a request; it is not a mechanism for
loading arbitrary artifacts.

Copy `configs/model-catalog.example.json` to a private local configuration,
replace each placeholder with its real numeric registry version, and load it
without committing credentials or environment-specific version choices:

```powershell
$env:MODEL_PATH = ""
$env:MODEL_URI = ""
$env:MODEL_CATALOG_JSON = Get-Content -Raw configs/model-catalog.local.json
$env:DEFAULT_MODEL_ID = "oulad-day-30"
```

## 7. Rollback and de-registration

Rollback must select a previously reviewed model version or deployment image.
Do not delete a registered version merely because it is no longer active;
retain it for reproducibility, audit, and incident investigation. Revoke or
rotate registry credentials if exposure is suspected, and record the event in
the operational incident log.
