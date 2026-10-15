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
  over decision thresholds.

Confusion matrices are reported because aggregate metrics alone do not show
the direction of errors. Rows represent actual classes and columns represent
predicted classes. False negatives are risk enrollments that were not flagged;
false positives are reference-class enrollments that were flagged. The
appropriate balance depends on the cost of missed support opportunities and
unnecessary interventions.

The full-course benchmark uses a stratified 75/25 holdout so that both
partitions retain approximately the observed class proportions. It is a
retrospective benchmark because full-course assessment and activity aggregates
may include information unavailable at an earlier point in the course. The
early-warning analysis addresses this limitation by filtering observations at
days 30, 60, and 90, excluding future unregistration information, and holding
out the latest course presentation. These controls reduce the specified forms
of temporal leakage; they do not replace prospective validation.

## Model comparison

All models used the same 75/25 stratified holdout split with
`random_state=42`. Model selection prioritizes ROC-AUC, then balanced accuracy,
then F1. The metrics below were generated by the actual OULAD run and are also
saved in `models/metrics/metrics.json`.

| Model | Accuracy | Balanced accuracy | Precision | Recall | F1 | ROC-AUC |
|---|---:|---:|---:|---:|---:|---:|
| Logistic regression | 0.857160 | 0.858075 | 0.882310 | 0.841702 | 0.861527 | 0.936149 |
| Random forest | 0.930421 | 0.931722 | 0.957608 | 0.908415 | 0.932363 | 0.981407 |
| Extra trees | 0.930175 | 0.931641 | 0.960069 | 0.905393 | 0.931930 | 0.980751 |
| Histogram gradient boosting | 0.933121 | 0.934582 | 0.962799 | 0.908415 | 0.934816 | 0.983018 |

### Selected baseline

`hist_gradient_boosting` is selected because it has the highest ROC-AUC,
balanced accuracy, accuracy, and F1 in this fixed comparison. The trained
artifact is written to `models/baseline.pkl`, which is ignored by Git.

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

The split is time-aware: `2014J` is the test presentation and `2013B`, `2013J`,
and `2014B` are the training presentations. This prevents later course
presentations from contributing training information to an earlier evaluation.
The split is applied separately at days 30, 60, and 90, and the same four
models are compared at every cutoff.

The cutoff days are formal observation checkpoints rather than arbitrary
subsets of the data. Day 30 represents an early-warning opportunity, day 60
represents a mid-course evidence point, and day 90 represents a later
observation point at which more evidence may be available while support may
still be possible. Evaluating all three points quantifies the trade-off between
intervention lead time and predictive information. The analysis does not claim
that these checkpoints are optimal for every course or intervention policy;
that decision requires prospective validation, calibration, operational
capacity, and a cost-sensitive threshold analysis.
The measured results from the supplied OULAD release are:

| Cutoff | Selected model | Accuracy | Balanced accuracy | F1 | ROC-AUC |
|---:|---|---:|---:|---:|---:|
| 30 days | Random forest | 0.732682 | 0.732320 | 0.741542 | 0.815245 |
| 60 days | Random forest | 0.767318 | 0.765984 | 0.781921 | 0.855580 |
| 90 days | Random forest | 0.782948 | 0.781607 | 0.796706 | 0.877778 |

The complete early-warning comparison is shown below. These values use the
same latest-presentation test set at each cutoff and are included to make the
selection of random forest transparent.

| Cutoff | Model | Accuracy | Balanced accuracy | F1 | ROC-AUC |
|---:|---|---:|---:|---:|---:|
| 30 | Logistic regression | 0.725133 | 0.725412 | 0.728723 | 0.772451 |
| 30 | Random forest | 0.732682 | 0.732320 | 0.741542 | **0.815245** |
| 30 | Extra trees | 0.723091 | 0.721643 | 0.741030 | 0.803825 |
| 30 | Histogram gradient boosting | **0.741030** | **0.741162** | **0.745727** | 0.806777 |
| 60 | Logistic regression | 0.744938 | 0.742790 | 0.766580 | 0.814485 |
| 60 | Random forest | **0.767318** | **0.765984** | **0.781921** | **0.855580** |
| 60 | Extra trees | 0.761368 | 0.759479 | 0.780025 | 0.852880 |
| 60 | Histogram gradient boosting | 0.759858 | 0.758287 | 0.776492 | 0.846532 |
| 90 | Logistic regression | 0.730462 | 0.727838 | 0.756674 | 0.809820 |
| 90 | Random forest | **0.782948** | **0.781607** | 0.796706 | **0.877778** |
| 90 | Extra trees | 0.779130 | 0.776701 | **0.799742** | 0.874997 |
| 90 | Histogram gradient boosting | 0.763144 | 0.760836 | 0.784380 | 0.863592 |

### Why random forest was selected for early warning

The selection rule is lexicographic: ROC-AUC is the primary criterion,
balanced accuracy is the first tie-breaker, and F1 is the second tie-breaker.
This rule reflects the planner's intended use as a risk-screening system. A
planner may change the support threshold according to intervention capacity,
so ranking quality across thresholds is more informative than accuracy at one
default threshold.

- **Day 30:** Random forest has the highest ROC-AUC at 0.815245, ahead of
  histogram gradient boosting at 0.806777, extra trees at 0.803825, and
  logistic regression at 0.772451. Histogram gradient boosting has higher
  accuracy, balanced accuracy, and F1 at this cutoff, while random forest has
  higher recall and ROC-AUC. The selection therefore follows the declared
  primary criterion rather than selecting by accuracy alone.
- **Day 60:** Random forest has the highest ROC-AUC, balanced accuracy, F1,
  and accuracy. Its ROC-AUC of 0.855580 is higher than extra trees at 0.852880,
  histogram gradient boosting at 0.846532, and logistic regression at
  0.814485. This is the clearest cutoff-specific comparison in favor of random
  forest.
- **Day 90:** Random forest again has the highest ROC-AUC at 0.877778 and the
  highest accuracy and balanced accuracy. Extra trees has a slightly higher F1
  and recall, but random forest has higher precision and the primary ROC-AUC.
  This indicates a different operational trade-off: extra trees identifies
  more risk enrollments at the default threshold, while random forest provides
  stronger overall ranking and fewer predicted-risk false positives at that
  threshold.

Random forest is therefore the selected early-warning model at all three
cutoffs because it provides the strongest threshold-independent ranking under
the pre-declared selection rule. This does not establish that random forest is
universally superior. The final deployment choice would require confidence
intervals or repeated validation, probability calibration, a chosen support
capacity, fairness analysis, and prospective evaluation of interventions. The
full-course benchmark remains separate: histogram gradient boosting is
selected there because it performs best under the retrospective full-course
comparison.

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
used as the label. Prospective validation, calibration, threshold selection,
and intervention-aware evaluation are still required before deployment.

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
