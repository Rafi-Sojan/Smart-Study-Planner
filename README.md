# Smart Study Planner

This repository currently contains a reproducible OULAD data-to-baseline-model
vertical slice. The planner, API, simulation, and monitoring areas remain
scaffolds. DVC data versioning and optional DagsHub MLflow tracking are
documented in [docs/mlops.md](docs/mlops.md). Detailed processing rules and
the verified four-model comparison are documented in
[docs/oulad-baseline.md](docs/oulad-baseline.md).
The interactive analysis is in
[notebooks/03_oulad_baseline_comparison.ipynb](<notebooks/03_oulad_baseline_comparison.ipynb>).
The leakage-safe early-warning evaluation is in
[notebooks/04_oulad_early_warning_evaluation.ipynb](<notebooks/04_oulad_early_warning_evaluation.ipynb>).
The data-cleaning, validation, and feature-extraction walkthrough is in
[notebooks/02_oulad_processing_and_features.ipynb](<notebooks/02_oulad_processing_and_features.ipynb>).
The descriptive data analysis is in
[notebooks/01_oulad_data_exploration.ipynb](<notebooks/01_oulad_data_exploration.ipynb>).

## Setup

Use Python 3.12, then install the pinned runtime and development dependencies:

```powershell
python -m pip install -r requirements.txt
```

Download the OULAD CSV release from the official Open University Learning
Analytics Dataset source and place at least these files in
`data/raw/oulad/`:

- `studentInfo.csv`
- `assessments.csv`
- `studentAssessment.csv`

`studentRegistration.csv`, `vle.csv`, and `studentVle.csv` are optional. When
present, registration and activity aggregates are included. VLE clicks are
activity counts, not study-duration measurements. Raw and processed data are
ignored by Git and must be supplied locally.

## Commands

Clean the available OULAD tables:

```powershell
python -m src.data.cleaner --input-dir data/raw/oulad --output-dir data/processed/oulad
```

Train and compare four deterministic baseline models, then write the selected
model and metrics:

```powershell
python -m pipeline.training_pipeline --data-dir data/raw/oulad
```

The comparison includes logistic regression, random forest, extra trees, and
histogram gradient boosting. The selected model is recorded in
`models/metrics/metrics.json`.
The notebook also displays confusion matrices so the error types behind the
aggregate metrics are visible.

Reproduce the data-to-model stages with DVC after configuring the DagsHub
remote:

```powershell
dvc repro
```

Log a completed baseline run to DagsHub MLflow only when tracking credentials
are configured in the current shell:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --mlflow `
  --experiment-name smart-study-planner-oulad
```

Add `--register-models` to register all four full-course baseline model
artifacts in MLflow. The selected full-course model remains
`hist_gradient_boosting` based on the measured comparison.

Evaluate the same four models using only observations available by course day
30, 60, and 90, with the latest course presentation held out:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/early_warning_metrics.json `
  --cutoffs-days 30 60 90
```

The early-warning metrics are versioned in
`models/metrics/early_warning_metrics.json`. The `early_warning` stage is also
included in `dvc.yaml`, so `dvc repro early_warning` reruns the same command
when its data or code dependencies change.

With DagsHub MLflow credentials configured, add `--mlflow --register-models`
to log the run and register the selected model separately for each cutoff.

Run the same checks used by CI:

```powershell
ruff check src pipeline tests
pytest -v
```

The model target is enrollment-level risk: `Fail` or `Withdrawn` is 1, while
`Pass` or `Distinction` is 0. The reported metrics are generated only when a
real or test dataset is actually passed to the training function. The OULAD
archive is kept local and ignored by Git; it is not committed to the
repository.

## Limitations and next work

The full-course baseline is not a causal model and is a retrospective
benchmark. The early-warning evaluation now defines 30/60/90-day observation
cutoffs and a course-presentation holdout, but it still uses final outcome
labels. Next steps are prospective validation, calibration and intervention
thresholds, API/Docker implementation, and evaluation on additional locally
supplied OULAD releases.

