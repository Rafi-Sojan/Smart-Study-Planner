# Smart Study Planner

## Project overview

Smart Study Planner is an educational analytics project for enrollment-level
academic-risk classification using the Open University Learning Analytics
Dataset (OULAD). The current repository provides a reproducible data-to-model
baseline and a leakage-controlled early-warning evaluation. A reproducible
synthetic Indian-university data generator supports planner and recommendation
development; its schema and limitations are documented in
[data/simulated/README.md](data/simulated/README.md). The planner and
application programming interface remain future implementation areas.

The processing methodology, feature definitions, measured results, and
limitations are documented in [docs/oulad-baseline.md](docs/oulad-baseline.md).
The complete raw-table column dictionary and derived-feature map are documented
in [docs/oulad-data-dictionary.md](docs/oulad-data-dictionary.md).
Data versioning and experiment tracking procedures are documented in
[docs/mlops.md](docs/mlops.md).
The EdNet exploratory analysis, scope, feature rationale, and limitations are
documented in [docs/ednet.md](docs/ednet.md).
The formal synthetic-data methodology, function reference, statistical
definitions, and rationale for each generated field are documented in
[docs/synthetic-data.md](docs/synthetic-data.md).
The synthetic feature contract, baseline-model comparison, metric definitions,
confusion-matrix interpretation, and model-selection rule are documented in
[docs/synthetic-baseline.md](docs/synthetic-baseline.md).
The formal risk register and release controls are documented in
[docs/risk-register.md](docs/risk-register.md).

## Analysis notebooks

- [01 — OULAD data exploration](notebooks/01_oulad_data_exploration.ipynb)
- [02 — OULAD processing and feature extraction](notebooks/02_oulad_processing_and_features.ipynb)
- [03 — Full-course baseline comparison](notebooks/03_oulad_baseline_comparison.ipynb)
- [04 — Leakage-safe early-warning evaluation](notebooks/04_oulad_early_warning_evaluation.ipynb)
- [05 — EdNet exploratory analysis](notebooks/05_ednet_eda.ipynb)
- [06 — Synthetic data exploration](notebooks/06_synthetic_data_exploration.ipynb)
- [07 — Synthetic processing and feature extraction](notebooks/07_synthetic_processing_and_features.ipynb)
- [08 — Synthetic baseline testing](notebooks/08_synthetic_baseline_testing.ipynb)

The OULAD notebooks contain executed outputs, including tables, metric plots,
and confusion matrices. The full-course notebook reports the retrospective
benchmark before cutoff application. The early-warning notebook reports
separate confusion matrices for the 30-, 60-, and 90-day observation cutoffs.
Notebook 05 contains the existing EdNet exploratory outputs and formal
interpretation of the activity, exposure, content, and metadata analyses. EdNet
is documented as a TOEIC-specific complementary dataset rather than as a
replacement for the OULAD academic-risk task. Notebooks 06–08 document the
synthetic planner track: relational EDA, leakage-aware cutoff processing, and
student-disjoint baseline model testing with confusion matrices. Synthetic
metrics are development benchmarks only and are not real student evidence.

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

## Generate the synthetic planner dataset

The synthetic generator creates relational CSV tables for a configurable
Indian-university planning scenario. The records are simulated and must not be
presented as real student observations. The default run creates 1,000 students
across three academic terms and 16 weeks per term, with multiple course types,
attendance and assessment records, study sessions, recommendations, sleep,
screen-time, break, and wellbeing records. A formal description of the
generation functions and required statistics is provided in
[docs/synthetic-data.md](docs/synthetic-data.md).

The current snapshot contains 36 relational CSV tables. It includes an explicit
course-prerequisite bridge, lagged academic-history inputs for cutoff features,
student-context fields for subgroup auditing, configurable seed-controlled
missingness, and `early_warning_targets.csv` for task-specific simulated
labels. These additions improve development realism but do not convert the
dataset into observed institutional evidence.

Run it from the repository root:

```powershell
python -m src.simulation.simulator --config configs/simulation.yaml --overwrite
```

The generated records are written to `data/raw/synthetic/`, which is
intentionally ignored by Git and kept separate from the real OULAD archive in
`data/raw/oulad/`. The same command is
registered as the `simulate` stage in `dvc.yaml`; use `dvc repro simulate` in a
normal writable checkout to reproduce and version the generated output with
DVC. Use `--overwrite` only when deliberately regenerating an existing output
directory.

## Statistical interpretation and methodological rationale

The unit of analysis is an enrollment: one student registered on one course
presentation. It is not a unique-student unit. Consequently, row counts,
percentages, outcome rates, and model metrics are interpreted at the enrollment
level, and every rate must be read with its corresponding enrollment
denominator. A student appearing in multiple presentations may contribute more
than one enrollment.

The four OULAD outcome categories are retained during exploration. For binary
risk classification, `Fail` and `Withdrawn` are encoded as 1, while `Pass` and
`Distinction` are encoded as 0. This grouping supports a defined risk-
screening task while preserving the original labels for descriptive analysis.
It does not imply that all unsuccessful outcomes have identical causes or
intervention requirements.

Descriptive counts and proportions summarize the supplied dataset; they are
not population estimates and do not establish statistical significance or
causality. Assessment means, medians, ranges, and activity totals describe
observed records only. Missing scores remain unknown rather than being treated
as zero, because absence of a score does not establish absence of performance.
VLE click totals are activity counts and are not estimates of study duration.

The baseline metrics have the following interpretations:

- accuracy is the proportion of correctly classified enrollments;
- precision is the proportion of predicted-risk enrollments that are actually
  in the risk class;
- recall is the proportion of risk enrollments identified by the model;
- F1 is the harmonic mean of precision and recall;
- balanced accuracy is the mean of sensitivity and specificity, giving equal
  weight to both classes; and
- ROC-AUC measures ranking quality across classification thresholds.
- PR-AUC summarizes precision-recall performance under class imbalance;
- Brier score measures the squared error of predicted probabilities.

Confusion matrices report actual classes by predicted classes. They make false
positives and false negatives visible and are therefore necessary for judging
whether a model is appropriate for a support-screening workflow. The model
selection rule prioritizes validation PR-AUC, then validation ROC-AUC,
validation balanced accuracy, and validation F1, while the confusion matrices
provide the operational context for that ranking.

Imputation and categorical encoding are fitted within each model pipeline
after the split. Model selection uses a validation partition, and the final
metrics are reported once on a locked test partition. OULAD partitions are
student-grouped so one learner cannot contribute rows to both sides of a
partition. The early-warning evaluation additionally removes observations
after days 30, 60, and 90 and uses an earlier presentation for validation and a
later presentation for testing. This is stricter than the previous single
holdout comparison and may reduce the measured scores.

The selected feature families are tied to the planner's intended decision
context. Demographic and enrollment attributes provide baseline context for
stratification and fairness review; assessment aggregates summarize observed
academic progress and incomplete participation; registration fields describe
the timing of enrollment; and VLE aggregates provide measurable indicators of
online engagement. These variables are targeted because they are available in
OULAD and can support prioritization of learners for attention. They are not
treated as direct measures of motivation, ability, study hours, or causal
effect. Identifiers are excluded because they identify records rather than
generalizable learning signals.

The 30-, 60-, and 90-day cutoffs are introduced to represent staged decision
points during a course. Day 30 provides an early opportunity for support, day
60 tests whether additional mid-course evidence improves discrimination, and
day 90 evaluates performance when a later but still actionable observation
window is available. These checkpoints are a sensitivity analysis of
information availability, not a claim that they are universally optimal. The
comparison shows the trade-off between earlier intervention and the amount of
evidence available to the model. Any production cutoff should ultimately be
selected using prospective validation, calibration, intervention capacity, and
the relative cost of missed and unnecessary support.

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
artifacts in MLflow. The selected model is determined from validation data at
runtime; the locked test partition is not used for model selection.

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

The early-warning selection is determined independently at each cutoff using
validation PR-AUC, validation ROC-AUC, validation balanced accuracy, and
validation F1. Numeric results must be regenerated after the grouped
train-validation-locked-test contract changed; no previous model ranking is
carried forward as a current claim.

Run the same checks used by CI:

```powershell
ruff check src pipeline tests
pytest -v
```

CI also generates a small seed-controlled synthetic fixture and runs the
synthetic baseline pipeline without DVC or MLflow credentials. This verifies
the end-to-end generator-to-model path while keeping large raw data and
external secrets out of GitHub Actions.

Run the synthetic baseline pipeline locally:

```powershell
python -m pipeline.synthetic_baseline_pipeline `
  --data-dir data/raw/synthetic `
  --metrics-output models/metrics/synthetic_baseline_metrics.json `
  --model-dir models/synthetic_baseline `
  --cutoffs-days 30 60 90
```

The pipeline trains all four baseline models using the student-disjoint
cutoff protocol, writes the measured comparison to
`models/metrics/synthetic_baseline_metrics.json`, and saves the selected model
for each cutoff under `models/synthetic_baseline/`. The local run does not
contact DagsHub unless `--mlflow` or `--register-models` is supplied.

The metrics file also stores fixed-threshold diagnostics and subgroup audit
metrics. Threshold diagnostics are descriptive test-set comparisons, not a
production threshold-selection procedure; any deployment threshold must be
chosen using training/validation data, intervention capacity, and reviewed
false-negative and false-positive costs.

Register every synthetic baseline model at every cutoff in DagsHub MLflow:

```powershell
python -m pipeline.synthetic_baseline_pipeline `
  --data-dir data/raw/synthetic `
  --mlflow `
  --register-models `
  --experiment-name smart-study-planner-synthetic-baseline `
  --run-name synthetic-baseline-registered-models
```

This registers twelve models using names of the form
`smart-study-planner-synthetic-baseline-day-30-logistic_regression`. The
experiment records all four model comparisons for days 30, 60, and 90. The
models remain synthetic development artifacts and must not be presented as
validated production models.

## Grafana monitoring

The repository includes an optional Grafana stack for visualizing completed
training and early-warning runs. It uses Prometheus as the Grafana data source
and Pushgateway as the intermediary for the short-lived batch pipelines.

Start the stack with Docker Desktop running:

```powershell
docker compose up -d
```

Open Grafana at `http://localhost:3000`. The Prometheus data source and the
`Smart Study Planner — OULAD Monitoring` dashboard are provisioned
automatically. To publish a completed pipeline run, pass the Pushgateway URL:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --pushgateway-url http://localhost:9091

python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --cutoffs-days 30 60 90 `
  --pushgateway-url http://localhost:9091
```

The exporter is opt-in. Existing local, DVC, and MLflow runs do not contact
Pushgateway unless `--pushgateway-url` is supplied or
`PROMETHEUS_PUSHGATEWAY_URL` is set. Grafana is used for operational metric
visualization; DVC remains responsible for data and artifact versioning, and
MLflow remains responsible for experiment tracking and model registration.

The model target is enrollment-level risk: `Fail` or `Withdrawn` is encoded as
1, while `Pass` or `Distinction` is encoded as 0. Metrics are generated from
the supplied dataset at execution time; no dataset, metric, or test result is
fabricated in the repository. The OULAD archive remains local and is excluded
from version control.

## Limitations and future work

The full-course baseline is a retrospective benchmark and is not a causal
model. The early-warning evaluation applies 30-, 60-, and 90-day observation
cutoffs and holds out a later presentation, but it still uses final course
outcomes as labels. Prospective validation, calibration, institutional privacy
approval, intervention-threshold review, and fairness review remain release
gates. See [docs/risk-register.md](docs/risk-register.md) before using any
registered artifact.

