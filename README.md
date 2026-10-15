# Smart Study Planner

## Project overview

Smart Study Planner is an educational analytics project for enrollment-level
academic-risk classification using the Open University Learning Analytics
Dataset (OULAD). The current repository provides a reproducible data-to-model
baseline and a leakage-controlled early-warning evaluation. The planner,
application programming interface, simulation, and monitoring components remain
future implementation areas.

The processing methodology, feature definitions, measured results, and
limitations are documented in [docs/oulad-baseline.md](docs/oulad-baseline.md).
Data versioning and experiment tracking procedures are documented in
[docs/mlops.md](docs/mlops.md).

## Analysis notebooks

- [01 — OULAD data exploration](notebooks/01_oulad_data_exploration.ipynb)
- [02 — OULAD processing and feature extraction](notebooks/02_oulad_processing_and_features.ipynb)
- [03 — Full-course baseline comparison](notebooks/03_oulad_baseline_comparison.ipynb)
- [04 — Leakage-safe early-warning evaluation](notebooks/04_oulad_early_warning_evaluation.ipynb)

All notebooks contain executed outputs, including tables, metric plots, and
confusion matrices. The full-course notebook reports the retrospective
benchmark before cutoff application. The early-warning notebook reports
separate confusion matrices for the 30-, 60-, and 90-day observation cutoffs.

## Installation and data requirements

The project requires Python 3.12. Install the pinned runtime and development
dependencies from the repository root:

```powershell
python -m pip install -r requirements.txt
```

The OULAD CSV release must be obtained from the official Open University
Learning Analytics Dataset source and extracted into `data/raw/oulad/`. The
following files are required:

- `studentInfo.csv`
- `assessments.csv`
- `studentAssessment.csv`

`studentRegistration.csv`, `vle.csv`, and `studentVle.csv` are optional. When
available, registration and activity aggregates are included in feature
construction. VLE clicks represent recorded activity counts and must not be
interpreted as direct measurements of study duration. Raw and processed data
are excluded from Git and must be supplied locally.

## Reproducible commands

Clean the available OULAD tables:

```powershell
python -m src.data.cleaner --input-dir data/raw/oulad --output-dir data/processed/oulad
```

Train and compare the four deterministic baseline models:

```powershell
python -m pipeline.training_pipeline --data-dir data/raw/oulad
```

The comparison includes logistic regression, random forest, extra trees, and
histogram gradient boosting. The selected model and measured metrics are
written to `models/metrics/metrics.json`. The baseline notebook also displays
confusion matrices before cutoff application.

Reproduce the data-to-model stages with DVC after configuring the DagsHub
remote:

```powershell
dvc repro
```

Log a completed full-course baseline run to DagsHub MLflow when tracking
credentials are configured in the current shell:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --mlflow `
  --experiment-name smart-study-planner-oulad
```

Add `--register-models` to register all four full-course baseline model
artifacts in MLflow. The selected full-course model remains
`hist_gradient_boosting` based on the measured comparison.

Evaluate the four models using only observations available by course day 30,
60, and 90, with the latest course presentation held out:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/early_warning_metrics.json `
  --cutoffs-days 30 60 90
```

The early-warning metrics are versioned in
`models/metrics/early_warning_metrics.json`. The `early_warning` stage is also
defined in `dvc.yaml`; therefore, `dvc repro early_warning` reruns the command
when its data or code dependencies change.

With DagsHub MLflow credentials configured, add `--mlflow --register-models`
to log the run and register the selected model separately for each cutoff.

Run the same checks used by CI:

```powershell
ruff check src pipeline tests
pytest -v
```

The model target is enrollment-level risk: `Fail` or `Withdrawn` is encoded as
1, while `Pass` or `Distinction` is encoded as 0. Metrics are generated from
the supplied dataset at execution time; no dataset, metric, or test result is
fabricated in the repository. The OULAD archive remains local and is excluded
from version control.

## Limitations and future work

The full-course baseline is a retrospective benchmark and is not a causal
model. The early-warning evaluation applies 30-, 60-, and 90-day observation
cutoffs and holds out the latest course presentation, but it still uses final
course outcomes as labels. Future work includes prospective validation,
probability calibration, intervention-threshold selection, API and container
implementation, monitoring, and evaluation on additional locally supplied
OULAD releases.

