# OULAD processing, feature engineering, and model evaluation

## Document status

This document records the reproducible OULAD processing and model-evaluation
workflow implemented in the repository. Reported values correspond to the
locally supplied OULAD release and the commands described below. They should
be regenerated when the input data, dependency versions, or pipeline logic
changes.

## Scope

The workflow was executed from the supplied `oulad-dataset.zip`. It covers
data ingestion, cleaning, feature extraction, evaluation of four baseline
classifiers, and selection of the reference model.

The task is enrollment-level risk classification:

- `1`: `Fail` or `Withdrawn`
- `0`: `Pass` or `Distinction`

An enrollment is identified by a student and course presentation. OULAD does
not provide a direct ground truth for the optimal study schedule, so this
model is a risk-prediction baseline rather than a scheduling optimizer.

## Data and reproducibility

The archive contained all seven standard OULAD tables. The raw archive was
extracted locally to `data/raw/oulad/`, and cleaned CSVs were written to
`data/processed/oulad/`. Both data directories are ignored by Git.

The field-by-field raw schema and the mapping from raw columns to derived model
features are documented in
[`docs/oulad-data-dictionary.md`](oulad-data-dictionary.md).

| Table | Raw rows | Clean rows |
|---|---:|---:|
| `studentInfo` | 32,593 | 32,593 |
| `studentRegistration` | 32,593 | 32,593 |
| `studentAssessment` | 173,912 | 173,912 |
| `assessments` | 206 | 206 |
| `courses` | 22 | 22 |
| `vle` | 6,364 | 6,364 |
| `studentVle` | 10,655,280 | 10,655,280 |

The cleaning stage can be reproduced with:

```powershell
python -m src.data.cleaner `
  --input-dir data/raw/oulad `
  --output-dir data/processed/oulad
```

The four-model comparison can be reproduced with:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/metrics.json `
  --model-output models/baseline.pkl
```

## Cleaning and validation

The loader requires `studentInfo.csv`, `assessments.csv`, and
`studentAssessment.csv`. Registration and VLE tables are optional for the
minimal pipeline but were available in this run.

Cleaning rules are deliberately conservative:

1. Required columns are checked and missing files fail with an actionable
   error.
2. Identifier, date, weight, registration, and activity fields are coerced to
   numeric values where appropriate.
3. Assessment scores outside `[0, 100]` become missing values. Missing scores
   are not converted to zero.
4. Invalid or missing final outcomes are excluded from supervised training.
5. Duplicate assessment definitions are reduced by `id_assessment`.
6. VLE activity is retained as click/activity data. Clicks are not interpreted
   as study hours.

The cleaning notebook makes these decisions auditable. It first records raw
table sizes, schemas, duplicate complete rows, missing key fields, and overall
cell missingness. It then calls the same `clean_oulad_tables` implementation
used by the CLI, displays raw-to-clean row reconciliation, checks identifier
and score invariants, verifies that missing scores remain unknown, reloads the
written CSVs, and validates the generated `manifest.json`. The notebook also
plots the number of rows removed per table so any cleaning impact is visible
rather than hidden inside a preprocessing step.

In the supplied data, all 173,912 assessment records were retained; 173,739
had known scores and 173 had missing scores. The observed score range was
0–100. Outcome counts were 12,361 Pass, 10,156 Withdrawn, 7,052 Fail, and
3,024 Distinction.

## Feature extraction

The feature builder creates one row per student-course presentation and keeps
the final outcome only as the target metadata. The model excludes identifiers
and the raw final outcome.

Features include:

- student demographics and enrollment attributes from `studentInfo`, such as
  gender, education, age band, disability, previous attempts, and studied
  credits;
- assessment count, mean, standard deviation, minimum, maximum, and missing
  score count, joined through `assessments`;
- registration date fields from `studentRegistration`;
- optional VLE total clicks, active days, and distinct resources from
  `studentVle` and `vle`.

These feature families were selected because they correspond to information
that a study planner could plausibly use when prioritizing support. Enrollment
and demographic attributes provide baseline context and enable subgroup
audits. Assessment aggregates represent observed academic progress and
assessment completeness. Registration fields represent enrollment timing.
VLE clicks, active days, and distinct resources represent recorded online
engagement and breadth of resource interaction. They are proxy variables, not
direct measurements of ability, motivation, study duration, or causal impact.
The planner should use them to prioritize review and support, not to assign
fixed judgments to learners. Record identifiers are excluded because they do
not represent transferable learning characteristics.

Numeric values are median-imputed inside each model pipeline. Categorical
values are most-frequent-imputed and one-hot encoded. No values are imputed
from the target or from the full dataset before splitting.

## Statistical interpretation and methodological rationale

All reported counts, rates, and metrics use the enrollment as the analysis
unit. An enrollment represents one student-course-presentation combination;
it is not equivalent to a unique student. This distinction is necessary
because a student may enroll in more than one course presentation. Outcome
rates are therefore calculated with enrollment counts as denominators.

The binary target is an operational risk grouping rather than a claim that
the four original outcomes are statistically identical. `Fail` and
`Withdrawn` are grouped as the risk class because both indicate an enrollment
that did not reach a successful completion outcome for the screening task.
`Pass` and `Distinction` form the reference class. The original four labels
remain available for descriptive analysis.

The exploratory statistics are descriptive summaries of the supplied OULAD
release. Counts and proportions describe composition; means and medians
describe central tendency; standard deviations and ranges describe observed
dispersion. These summaries do not constitute inferential tests, population
estimates, or evidence of causality. In particular, a relationship between
click activity, assessment scores, and outcome cannot be interpreted as proof
that activity or scores caused the outcome.

Missingness is treated as an observed data property. A missing assessment score
is not recoded as zero because an unrecorded result does not establish a zero
performance value. Where model preprocessing requires complete numerical input,
median imputation is learned from the training partition within the pipeline.
Categorical imputation and one-hot encoding are handled by the same fitted
pipeline, preventing holdout information from influencing preprocessing.

The evaluation metrics are interpreted as follows:

- accuracy measures the proportion of all correctly classified enrollments;
- precision measures the proportion of predicted-risk enrollments that belong
  to the risk class;
- recall, or sensitivity, measures the proportion of risk enrollments detected;
- specificity measures the proportion of reference-class enrollments not
  incorrectly flagged;
- F1 is the harmonic mean of precision and recall;
- balanced accuracy is the mean of sensitivity and specificity; and
- ROC-AUC measures the probability that a randomly selected risk enrollment is
  ranked above a randomly selected reference-class enrollment, aggregated
  over decision thresholds;
- PR-AUC summarizes precision-recall performance and is especially important
  when the risk class is rare; and
- Brier score measures squared probability error, with lower values preferred.

Confusion matrices are reported because aggregate metrics alone do not show
the direction of errors. Rows represent actual classes and columns represent
predicted classes. False negatives are risk enrollments that were not flagged;
false positives are reference-class enrollments that were flagged. The
appropriate balance depends on the cost of missed support opportunities and
unnecessary interventions.

The full-course benchmark uses student-grouped train, validation, and locked
test partitions. It is a retrospective benchmark because full-course
assessment and activity aggregates may include information unavailable at an
earlier point in the course. The early-warning analysis addresses this
limitation by filtering observations at days 30, 60, and 90, excluding future
unregistration information, using an earlier presentation for validation, and
holding out a later presentation for testing. These controls reduce the
specified forms of leakage; they do not replace prospective validation.

## Model comparison

All models use the same student-grouped partitions with `random_state=42`.
Model selection uses validation PR-AUC, then validation ROC-AUC, validation
balanced accuracy, and validation F1. Final accuracy, recall, precision, F1,
PR-AUC, ROC-AUC, Brier score, expected calibration error, reliability bins,
and confusion matrices are measured on the
locked test partition. Regenerate `models/metrics/metrics.json` after this
evaluation-contract change before quoting numeric results.

### Formal rationale for the baseline model set

The four classifiers were selected because OULAD is a moderate-sized,
enrollment-level tabular dataset containing both numerical and categorical
features. The extracted matrix has approximately 32,593 enrollment rows and
24 columns, including learner attributes, course and presentation fields,
assessment-score aggregates, registration variables, and recorded VLE activity
aggregates. This structure supports classical supervised-learning baselines
without requiring the computational cost or opacity of a deep neural network.

The models were chosen to represent complementary modeling assumptions:

- **Logistic regression** is the transparent linear reference. It measures how
  much predictive performance can be obtained from additive relationships and
  provides an interpretable sanity-check baseline.
- **Random forest** represents bagged nonlinear decision trees. It can capture
  interactions between assessment performance, registration information, and
  online activity without requiring those interactions to be specified
  manually.
- **Extra trees** provides a second randomized tree ensemble. Its additional
  split randomization tests whether greater partition diversity improves
  generalization beyond random forest.
- **Histogram gradient boosting** represents sequential tree boosting. It can
  learn threshold-based and nonlinear tabular patterns efficiently and tests a
  different ensemble strategy from the two bagging methods.

This set answers four ordered baseline questions: how strong is a simple
interpretable model; do nonlinear trees help; does additional tree
randomization help; and does sequential boosting improve on bagging? Deep
learning, extensive hyperparameter search, and more specialized methods were
not used as the initial comparison because they would add complexity before a
reproducible reference point had been established and would not be justified
solely by the size or structure of this dataset.

All four models receive the same feature matrix, preprocessing, training
partition, test partition, and random seed. Consequently, the comparison is
intended to measure differences between model families rather than differences
in data preparation. The result is a baseline comparison, not evidence that
any one classifier is universally optimal. The reported calibration bins are
diagnostic rather than a calibrated-probability guarantee. Time-aware
validation, grouped validation by learner, reviewed intervention capacity,
and prospective intervention evaluation remain necessary before deployment.

### Selected baseline

The selected model is determined from validation performance at runtime. The
previous full-course ranking is not carried forward because it used the old
holdout-selection contract. The trained artifact is written to
`models/baseline.pkl`, which is ignored by Git.

The full-course baseline models were also registered in DagsHub MLflow from
run `a996aaf686ad4075a6c20a7d820e010f`. Each model is version 1:

- `smart-study-planner-oulad-baseline-logistic_regression`
- `smart-study-planner-oulad-baseline-random_forest`
- `smart-study-planner-oulad-baseline-extra_trees`
- `smart-study-planner-oulad-baseline-hist_gradient_boosting`

To repeat the registration after configuring DagsHub MLflow credentials:

```powershell
python -m pipeline.training_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/metrics.json `
  --model-output models/baseline.pkl `
  --mlflow `
  --register-models `
  --run-name oulad-full-course-baseline-registered-models
```

## Leakage-safe early-warning evaluation

The full-course comparison above is intentionally retained as a retrospective
benchmark, but it is not an early-warning result. The repository now provides
`pipeline/early_warning_pipeline.py` and
`notebooks/04_oulad_early_warning_evaluation.ipynb` for a stricter evaluation.
For each cutoff, the feature builder uses only assessment submissions and VLE
activity with a course-relative date on or before the cutoff. It uses the
registration date but excludes `date_unregistration`, because a future
withdrawal date would not be available to a planner at prediction time.

The split is time-aware: the latest presentation is held out for testing and
the preceding available presentation is used for validation. Earlier
presentations are used for training. Student overlap is removed between these
partitions where the same learner appears in more than one presentation. This
prevents later course presentations and repeated learners from contributing
training information to the evaluation. The split is applied separately at
days 30, 60, and 90, and the same four models are compared at every cutoff.

The cutoff days are formal observation checkpoints rather than arbitrary
subsets of the data. Day 30 represents an early-warning opportunity, day 60
represents a mid-course evidence point, and day 90 represents a later
observation point at which more evidence may be available while support may
still be possible. Evaluating all three points quantifies the trade-off between
intervention lead time and predictive information. The analysis does not claim
that these checkpoints are optimal for every course or intervention policy;
that decision requires prospective validation, calibration, operational
capacity, and a cost-sensitive threshold analysis.
Numeric early-warning results must be regenerated after this evaluation-contract
change. The output records validation PR-AUC, validation ROC-AUC, locked-test
metrics, Brier score, calibration diagnostics, confusion matrices, subgroup
audit results, and the
threshold selected on validation data. The model may differ by cutoff; no
algorithm is assumed to be universally superior.

These values are generated by the command below and saved in the versioned
JSON artifact `models/metrics/early_warning_metrics.json`:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/early_warning_metrics.json `
  --cutoffs-days 30 60 90
```

The early-warning results are not directly comparable to the full-course
benchmark because the observation window and presentation split differ. They
also remain retrospective discrimination measurements: the final outcome is
used as the label. Prospective validation, calibration-method review,
capacity/cost-based threshold selection, and intervention-aware evaluation are
still required before deployment. The policy utility can record a
validation-only threshold when reviewed capacity or relative error costs are
supplied; otherwise it marks the policy as `not_configured`.

### DagsHub model registration

The verified DagsHub MLflow run is
`c0a0421bdc964e06adc7113ff808cae7`. It finished successfully and registered
the selected random-forest artifact as version 1 of each cutoff-specific model:

- `smart-study-planner-oulad-early-warning-day-30`
- `smart-study-planner-oulad-early-warning-day-60`
- `smart-study-planner-oulad-early-warning-day-90`

Future runs can repeat this workflow after configuring the DagsHub MLflow
environment variables:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --metrics-output models/metrics/early_warning_metrics.json `
  --cutoffs-days 30 60 90 `
  --mlflow `
  --register-models `
  --run-name oulad-early-warning-registered-models
```

The pipeline saves each selected sklearn model in MLflow format, uploads it
under the corresponding cutoff, and creates a registry version from the
`runs:/` artifact URI.

## Interpretation limits

The full-course values are retrospective benchmark metrics, not evidence of
deployment performance. The early-warning pipeline reduces this specific
leakage by applying explicit observation cutoffs and time-aware presentation
splits, but it does not estimate an optimal study duration or schedule.

## Notebook and visualizations

`notebooks/03_oulad_baseline_comparison.ipynb` provides an interactive view
of the same reusable pipeline. It loads the local OULAD tables, runs the
cleaning and feature functions from `src/`, and compares the four baseline
models. It does not contain a separate copy of the modeling logic.

The preceding
`notebooks/02_oulad_processing_and_features.ipynb` focuses on the data layer:
raw table sizes and schemas, a raw quality audit, deterministic cleaning,
cleaning reconciliation, score quality, invariant checks, persisted-output
round-trip validation, missingness, outcome balance, enrollment-level feature
extraction, and feature distributions. Use it first when reviewing how the
modeling table was built.

The descriptive analysis is in `notebooks/01_oulad_data_exploration.ipynb`.
It covers outcome composition, course-presentation risk rates, demographic
and enrollment attributes, assessment-score distributions, and registration
timing. Its plots are descriptive and retain the distinction between
enrollments, assessment records, and activity records.

The early-warning notebook is in
`notebooks/04_oulad_early_warning_evaluation.ipynb`. It documents the
observation-availability audit, runs the four cutoff-specific models, plots
metric curves for days 30, 60, and 90, and displays separate confusion-matrix
figures for each cutoff. It calls the same feature and model functions as the
scripted pipeline rather than maintaining a second implementation.

The notebook includes these visualizations:

- **Enrollment outcomes:** counts of Distinction, Pass, Fail, and Withdrawn
  enrollments. These are enrollment counts, not unique-student counts; one
  student may have more than one enrollment.
- **Unknown values:** the share of missing values in extracted features.
  Missingness is displayed as unknown information and is not evidence that the
  student had zero activity or zero performance.
- **Baseline model comparison:** ROC-AUC, balanced accuracy, and F1 on the
  same holdout split. These metrics compare classifiers; they do not establish
  causal effects.
- **Confusion matrices:** actual labels by predicted labels for each baseline.
  The full-course notebook reports matrices before cutoff application. The
  early-warning notebook reports separate matrices for the 30-, 60-, and
  90-day cutoffs. Rows are the actual class and columns are the predicted
  class: 0 is Pass/Distinction and 1 is Fail/Withdrawn. False negatives are
  risky enrollments the model missed; false positives are lower-risk
  enrollments flagged for attention. The appropriate trade-off depends on the
  future intervention cost.
- **Mean assessment score by risk group:** descriptive group means for the
  binary target. The chart shows association in this dataset and does not show
  that assessment scores caused the final outcome.

To inspect or refresh a notebook after installing the dependencies, start
Jupyter from the project root:

```powershell
jupyter notebook notebooks/03_oulad_baseline_comparison.ipynb
```

The notebooks currently contain executed outputs generated from the local
dataset. These outputs are retained for review and must be regenerated when
the input data, dependencies, or implementation changes. They are not a
substitute for the scripted pipeline artifacts or versioned metrics files.
