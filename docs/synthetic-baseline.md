# Synthetic baseline modelling: formal report

## 1. Scope and interpretation

This report documents the reproducible baseline experiment for the synthetic
Indian-university planner data. The task is enrollment-level risk screening:
`risk_label = 1` denotes a simulated failed or withdrawn enrollment and
`risk_label = 0` denotes a simulated passed enrollment.

The experiment is a development benchmark for the Smart Study Planner. It is not
evidence about real students, Indian universities, intervention effectiveness,
or causal relationships. The simulator uses controlled latent profiles, so
strong scores may reflect the design of the simulation. The OULAD and synthetic
tracks remain separate and their results must not be combined or compared as if
they represented the same population.

The executed implementation is in:

- [`07_synthetic_processing_and_features.ipynb`](../notebooks/07_synthetic_processing_and_features.ipynb), which creates cutoff-aware feature tables;
- [`08_synthetic_baseline_testing.ipynb`](../notebooks/08_synthetic_baseline_testing.ipynb), which trains, compares, and evaluates the four baselines; and
- [`src/features/synthetic_features.py`](../src/features/synthetic_features.py), which is the reusable processing contract.

## 2. Unit of analysis and temporal design

The unit of analysis is one student-course-offering enrollment. A student can
therefore contribute multiple rows across terms and courses. Counts, class
rates, and model metrics are interpreted at this enrollment grain unless
explicitly stated otherwise.

The same enrollment is represented at three possible decision dates:

| Cutoff | Formal purpose | Planner interpretation |
|---:|---|---|
| 30 days | Earliest tested observation window | Maximizes time for support, but has the least observed evidence. |
| 60 days | Mid-course sensitivity scenario | Provides more behavioural and academic evidence while retaining intervention time. |
| 90 days | Later sensitivity scenario | May improve discrimination, but leaves less time for meaningful intervention. |

These are evaluation checkpoints, not claims that 30, 60, or 90 days is a
universally correct policy. The comparison measures the trade-off between
information quantity and intervention lead time. Final outcomes are used only
as labels; events after a cutoff are not aggregated into its predictors.

## 3. Feature extraction and selection contract

The processing function joins the normalized relational tables at enrollment
grain, filters dated event tables to the chosen cutoff, and aggregates event
records. It preserves missingness when no event has yet been observed. A
missing assessment is not treated as a zero mark.

Features are retained using three predeclared criteria:

1. the information is available by the decision date;
2. the field represents academic progress, workload, engagement, time, or
   wellbeing context relevant to planning; and
3. the field is not an identifier, final outcome, or post-cutoff observation.

This is a design-time feature contract. Features are not selected solely
because they correlate with the target in this generated sample.

### 3.1 Actual predictor fields

The generated feature table currently contains 64 columns. The baseline matrix
contains 55 predictor fields after exclusion of identifiers, labels, sensitive
audit-only fields, cutoff metadata, and final-outcome fields:

**Enrollment and course context**

`attempt_number`, `is_backlog`, `enrollment_status`,
`enrollment_date`, `term_id`, `section`, `attendance_requirement_percent`,
`term_number`, `course_type`, `credits`, `difficulty`, `estimated_effort_hours`,
`residence_type`, `employment_status`, and `study_mode`.

**Student history and curriculum context**

`prior_education_stream`, `first_generation_student`,
`internet_access_type`, `financial_aid_status`, `prior_semester_gpa`,
`prior_cumulative_gpa`, `prior_failed_credits`, `prior_backlog_count`,
`prior_terms_completed`, `prerequisite_count`, and
`unmet_prerequisite_count`.

**Attendance and assessment progress**

`attendance_classes_observed`, `attendance_absences`,
`attendance_pct_at_cutoff`, `attendance_pct_mean`,
`assessment_attempt_count`, `assessment_mean_score`,
`assessment_late_rate`, and `assessment_submitted_rate`.

**Study behaviour and topic state**

`planned_sessions`, `completed_sessions`, `active_study_minutes`,
`study_screen_minutes`, `distraction_minutes`, `actual_break_minutes`,
`session_completion_rate`, `mean_mastery_score`,
`mean_confidence_score`, `mean_topic_fatigue`, and
`remaining_effort_hours`.

**Wellbeing and availability context**

`mean_total_screen_minutes`, `mean_total_break_minutes`,
`mean_sleep_hours`, `mean_sleep_deficit_hours`, `mean_fatigue_score`,
`mean_concentration_score`, `mean_stress_score`,
`mean_available_hours`, `mean_commute_hours`, and
`mean_part_time_work_hours`.

The feature contract also includes lagged academic history and curriculum
context: `prior_semester_gpa`, `prior_cumulative_gpa`, `prior_failed_credits`,
`prior_backlog_count`, `prior_terms_completed`, `prerequisite_count`, and
`unmet_prerequisite_count`. A term-one enrollment has no prior academic history
by definition. Current-term and future performance records remain excluded.

The exact feature inventory is also printed by Notebook 07 for each cutoff,
including the pandas data type. Categorical fields are not assigned arbitrary
numeric codes; they are imputed and one-hot encoded inside the model pipeline.

### 3.2 Explicit exclusions and leakage controls

The following fields are not predictors:

- record identifiers: `enrollment_id`, `student_id`, `offering_id`,
  `course_id`, `faculty_id`, `department_id`, and `program_id` when
  present as identifiers;
- labels and final outcomes: `risk_label`, `passed`, `withdrawn`,
  `requires_retake`, final grade, and result status;
- sensitive or consent-related audit fields: `category`, `preferred_language`,
  and `consent_status`;
- temporal metadata: `observation_cutoff_days`, `cutoff_date`, and
  `start_date`;
- any future event or outcome occurring after the stated cutoff.

Some course and organizational fields, such as `course_id` or
`department_id`, can be useful for descriptive grouping, but they are excluded
from the model matrix when treated as identifiers. This avoids allowing a
memorized record key to stand in for a generalizable learning signal. The
processing notebook documents the table-level contract, while the baseline
notebook applies the final drop set before fitting.

## 4. Cleaning, transformation, and split discipline

The processing stage performs relational joins, date filtering, aggregation,
and domain-preserving calculations. It does not fabricate observations for
missing event records. The modelling stage then applies:

- median imputation for numeric predictors;
- most-frequent imputation for categorical predictors;
- standard scaling for numeric predictors used by logistic regression;
- one-hot encoding for categorical predictors with unknown-category handling;
- the complete transformation inside a scikit-learn `Pipeline` and
  `ColumnTransformer`.

All learned preprocessing parameters are fitted on training students only.
The split is student-disjoint: students, rather than individual enrollment
rows, are assigned to training, validation, or locked-test partitions. This
prevents a student's behaviour from appearing in multiple partitions and
producing an optimistic estimate of generalization to unseen students. The
split uses random state 42 and stratifies students by whether they have at
least one risky enrollment.

## 5. Baseline algorithms and reasons for inclusion

Four deliberately different baselines are compared at every cutoff.

| Model | Why it is included | Limitation addressed by comparison |
|---|---|---|
| Logistic regression | Transparent linear reference with probability output and a strong reproducible baseline. | May miss interactions such as the joint effect of low attendance and low availability. |
| Random forest | Captures nonlinear relationships and interactions, is comparatively robust to mixed planner variables, and provides a useful ensemble reference. | Can be less transparent and its probabilities may require calibration. |
| Extra trees | Adds a more randomized tree ensemble with different split behaviour. | Tests whether randomization improves the bias-variance trade-off over conventional forests. |
| Histogram gradient boosting | Provides a strong nonlinear boosting baseline capable of learning structured effects efficiently. | Can fit controlled simulation patterns strongly and requires careful validation. |

The purpose is not to claim that one algorithm is universally best. The four
models establish transparent, nonlinear, randomized-ensemble, and boosting
reference points before more advanced tuning is attempted.

## 6. Evaluation statistics

Notebook 08 reports accuracy, precision, recall, F1, balanced accuracy,
ROC-AUC, PR-AUC, Brier score, model ranking, confusion matrices, validation
threshold diagnostics, and
descriptive subgroup metrics for category, residence, employment, and study
mode. Protected attributes are used for auditing only and are not included in
the default predictor matrix.

| Statistic | Definition | Why it matters for a planner |
|---|---|---|
| Accuracy | `(TP + TN) / N` | Overall correctness, but insufficient when class frequencies differ. |
| Precision | `TP / (TP + FP)` | Reliability of a risk alert and likely support workload. |
| Recall/sensitivity | `TP / (TP + FN)` | Coverage of risky enrollments; missed risk can remove an opportunity for support. |
| Specificity | `TN / (TN + FP)` | Ability to avoid unnecessary alerts. |
| F1 | Harmonic mean of precision and recall | Summarizes the precision-recall trade-off at the selected threshold. |
| Balanced accuracy | `(sensitivity + specificity) / 2` | Gives both classes equal importance. |
| ROC-AUC | Threshold-independent ranking measure | Evaluates whether risky enrollments tend to receive higher scores before choosing an alert threshold. |
| PR-AUC | Area under the precision-recall curve | More informative than accuracy when the risky class is rare. |
| Brier score | Mean squared probability error | Assesses probability calibration; lower is better. |

Mean, median, standard deviation, quartiles, IQR, and missing percentages are
used in the processing and exploration notebooks to describe generated
features. Mean and median are reported together because time, screen, commute,
availability, and session variables may be skewed. A mean materially above a
median indicates that a smaller group of high values is pulling the average
upward; a planner should not automatically schedule the mean as if it were the
experience of a typical student.

## 7. Model selection rule and formal comparison

The selection rule is declared before interpreting the results:

1. highest validation PR-AUC;
2. if tied, highest validation ROC-AUC;
3. if tied, highest validation balanced accuracy;
4. if still tied, highest validation F1.

PR-AUC is primary because the simulated risky class is rare and the planner
needs to understand precision-recall behaviour. ROC-AUC remains useful for
ranking, balanced accuracy gives both classes equal importance, and F1
summarizes alert precision and risk recall. Accuracy is reported but is not the
selection criterion.

The ranking audit table in Notebook 08 displays every model's rank separately
for days 30, 60, and 90. Therefore the selected algorithm may differ by cutoff.
The decision should be reported with the measured table and not reduced to a
claim that random forest, or any other model, is always superior.

In the current executed seed-42 snapshot, 152 of 12,000 enrollment rows are
risky, and the locked test partition contains 3,000 rows. At the default 0.5
threshold, the candidates predict almost all rows as low risk, so locked-test
recall and F1 are zero while ROC-AUC and PR-AUC still show ranking signal.
This measured contrast is a central result, not an error to conceal: it shows
why a high ROC-AUC or accuracy cannot by itself justify an alert policy.
The current benchmark therefore selects a ranking baseline, but it does not
claim that its default threshold is ready for planner intervention. A threshold
is selected from validation data for diagnostic reporting and then evaluated on
the locked test partition. Intervention capacity and support costs have not
yet been supplied, so this is not a production threshold.

For the current executed seed-42 comparison, the validation rule selects extra
trees at 30 days (validation PR-AUC 0.1091), logistic regression at 60 days
(0.1212), and extra trees at 90 days (0.1497). These values are from the
regenerated synthetic pipeline and must be regenerated if the dataset, seed, or
feature contract changes. The selection is a synthetic development comparison,
not a production model recommendation.

## 8. Confusion matrices and operational interpretation

Each selected model produces a 2 × 2 confusion matrix with actual class on the
vertical axis and predicted class on the horizontal axis:

| | Predicted low risk | Predicted risk |
|---|---:|---:|
| Actual low risk | TN | FP |
| Actual risk | FN | TP |

The notebooks show matrices for the 30-, 60-, and 90-day selected models and
also print an audit table containing TN, FP, FN, TP, sensitivity, specificity,
false-positive rate, and false-negative rate. The accompanying FP/FN graph
shows operational error counts by cutoff.

False negatives are especially important when the model is used to prioritize
support because a learner who needs help is not flagged. False positives are
also material because limited advising capacity may be allocated unnecessarily.
The acceptable balance depends on available intervention resources and the
relative cost of missing risk versus contacting a learner who would have
passed. A production deployment must therefore choose a threshold using
validated intervention costs rather than using the default 0.5 threshold
without review. Further analysis should include precision-recall curves,
threshold sweeps, class-weight or resampling sensitivity, calibration-method
comparison, and an intervention-capacity analysis using reviewed capacity or
error costs. The reusable policy utility supports this analysis without
selecting a policy from the locked test set.

## 9. What the results can and cannot establish

The executed notebook outputs are the authoritative measured results for the
current seed and configuration. They should be read with the displayed sample
sizes, model ranking, and confusion matrices. Re-running the generator,
changing the seed, changing the simulator, or changing the feature contract
can change the results.

The benchmark can establish that the code runs reproducibly on the synthetic
schema and that the candidate models can be compared under a student-disjoint,
cutoff-aware protocol. It cannot establish real-world accuracy, fairness,
calibration, intervention benefit, causal effects, or suitability for an
Indian university. Those claims require consented, de-identified institutional
data, prospective validation, calibration, subgroup analysis, threshold
review, and drift monitoring.

The generated `early_warning_targets.csv` separates several operational labels
that can be modelled in later work. The present baseline continues to use final
non-pass as its primary risk target so that comparisons remain directly
comparable with the earlier experiments. A task-specific evaluation must define
its prediction horizon and intervention utility before selecting a model.

