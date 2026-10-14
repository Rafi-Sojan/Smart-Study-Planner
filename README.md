# Smart Study Planner

This repository currently contains a reproducible OULAD data-to-baseline-model
vertical slice. The planner, API, simulation, and monitoring areas remain
scaffolds. DVC data versioning and optional DagsHub MLflow tracking are
documented in [docs/mlops.md](docs/mlops.md). Detailed processing rules and
the verified four-model comparison are documented in
[docs/oulad-baseline.md](docs/oulad-baseline.md).
The interactive analysis is in
[notebooks/03_oulad_baseline_comparison.ipynb](<notebooks/03_oulad_baseline_comparison.ipynb>).
The data-processing and feature-extraction walkthrough is in
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

The baseline is not a causal model and does not infer an optimal study
schedule. It needs a prediction-time definition to avoid using information
that would only be known after the course. Next steps are leakage-aware time
splits, a data-dependent pipeline workflow, API/Docker implementation, and
evaluation on a locally supplied OULAD release.

