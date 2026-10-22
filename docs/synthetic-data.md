# Synthetic Indian-University Dataset: Formal Methodology and Statistical Specification

## 1. Purpose and status

This document specifies the design, implementation, statistical interpretation,
and reproducibility requirements for the synthetic Indian-university dataset
used by Smart Study Planner.

The dataset is a development and testing resource. It is not a survey, an
institutional record, or evidence about real Indian students. Every row is
generated from explicit simulation assumptions and a recorded pseudo-random
seed. Results obtained from this data must therefore be described as
simulation results and must not be reported as real-world educational
performance.

The project maintains two separate analytical tracks:

1. **OULAD risk track:** real, de-identified historical learning-analytics
   data used for leakage-aware academic-risk modelling.
2. **Synthetic planner track:** simulated relational data used to develop
   study scheduling, recommendation, wellbeing-aware planning, and system
   integration features that are not available in OULAD.

The two tracks must not be concatenated into a single training table. OULAD
supports empirical benchmarking; the synthetic track supports controlled
software and planner experimentation.

## 2. Current reproducible configuration

The project default is defined in `configs/simulation.yaml`:

| Parameter | Current value | Reason |
|---|---:|---|
| Students | 1,000 | Large enough to cover repeated profiles, courses, terms, and student-disjoint evaluation while remaining practical for local development. |
| Academic terms | 3 | Covers foundational, intermediate, and advanced B.Tech CSE coursework. |
| Weeks per term | 16 | Represents a conventional teaching period before examination completion. |
| Seed | 42 | Makes the generated records reproducible. |
| Start date | 2025-07-01 | Provides a deterministic calendar anchor. |

Reproduce the configured data from the repository root:

```powershell
python -m src.simulation.simulator --config configs/simulation.yaml --overwrite
```

Reproduce it through DVC:

```powershell
dvc repro simulate
```

The configured output directory is `data/raw/synthetic/`, kept separate from
the real OULAD directory `data/raw/oulad/`. `--overwrite` is intentionally required when the output directory already
contains generated CSV files. This prevents accidental replacement of a
dataset. The generated directory is ignored by Git and represented by the
`simulate` stage in `dvc.lock`.

## 3. Generation architecture

The generator creates parent entities before dependent entities. This mirrors
a relational university information system and allows foreign-key integrity
checks.

```text
configuration and seed
        |
        +--> university, campus, department, program
        +--> academic terms
        +--> courses, topics, course-topic bridges
        +--> students and latent simulation state
        +--> offerings and enrollments
        +--> attendance, assessments, attempts, outcomes
        +--> availability, sleep, wellbeing, sessions, breaks
        +--> recommendations, feedback, resources, progress
        +--> manifest and CSV files
```

The hidden state returned by `_students` is not an observed measurement. It is
a simulation mechanism used to create correlated records. For example, a
student's simulated reliability influences attendance, assessment submission,
session completion, recommendation acceptance, and resource completion. This
creates coherent test cases, but it does not prove that those variables cause
one another in real life.

## 4. Function reference

The implementation is in
[`src/simulation/simulator.py`](../src/simulation/simulator.py). The following
reference documents every function in that module and the reason it exists.

The executed analysis notebooks are:

- [`06_synthetic_data_exploration.ipynb`](../notebooks/06_synthetic_data_exploration.ipynb)
  for table inventory, schema, descriptive statistics, and visual quality
  checks;
- [`07_synthetic_processing_and_features.ipynb`](../notebooks/07_synthetic_processing_and_features.ipynb)
  for cutoff-aware aggregation and feature rationale; and
- [`08_synthetic_baseline_testing.ipynb`](../notebooks/08_synthetic_baseline_testing.ipynb)
  for student-disjoint baseline comparison and confusion matrices.

The formal baseline-model report is in
[`docs/synthetic-baseline.md`](synthetic-baseline.md). It records the actual
predictor contract, cleaning and split discipline, reasons for the four
baseline algorithms, metric definitions, model-selection rule, and the
operational interpretation of false positives and false negatives.

| Function or class | Responsibility | Methodological reason |
|---|---|---|
| `SimulationConfig` | Stores output path, seed, student count, term count, term length, start date, and overwrite policy. | Makes the experiment configuration explicit, serializable, and reproducible instead of scattering constants through the generator. |
| `_clip(value, low, high)` | Bounds a numeric value within an admissible interval using `numpy.clip`. | Prevents impossible values such as negative hours, scores above 100, or probabilities outside `[0, 1]`. |
| `_date(value)` | Converts a timestamp to `YYYY-MM-DD`. | Gives all date fields one stable, portable CSV representation. |
| `_datetime(value)` | Converts a timestamp to second-resolution ISO-like text. | Preserves event ordering while avoiding locale-dependent datetime formats. |
| `_round(value, digits)` | Rounds generated floating-point values. | Keeps exported values readable and prevents meaningless machine precision from appearing as measured accuracy. |
| `_grade(score)` | Maps a 0–100 score to the documented synthetic letter grades. | Provides a consistent categorical representation for assessment and outcome analysis. |
| `_term_rows(config)` | Creates academic terms from the configured start date and weeks per term. | Gives every academic event a deterministic temporal context. The 21-day inter-term interval is a simulation assumption for registration, results, and breaks. |
| `_course_rows()` | Creates course rows, four ordered topics per course, and the course-topic bridge. | Represents course decomposition and topic sequencing needed by a study planner. |
| `_students(rng, count)` | Creates student-facing rows and latent behavioural state for the configured population. | Produces controlled variation in prior performance, attendance, reliability, sleep, and availability while keeping the public schema relational. |
| `generate_dataset(config)` | Validates configuration, builds all tables, writes CSV files, and writes `manifest.json`. | Serves as the single orchestration boundary for reproducible dataset creation and provenance recording. |
| `_load_config(path)` | Reads a YAML mapping and rejects non-mapping content. | Separates experiment configuration from code and makes DVC able to detect configuration changes. |
| `main()` | Parses command-line arguments, applies CLI overrides, invokes generation, and prints row counts. | Provides a repeatable command-line interface for local runs and the DVC pipeline. |

### 4.1 Validation behaviour

`generate_dataset` applies the following constraints:

- at least four students are required so all four declared student profiles
  appear at least once;
- one to three terms are supported because the supplied course catalogue has
  three term assignments;
- a term must contain at least eight weeks;
- existing CSV output is not replaced unless `overwrite=True` is supplied.

These are implementation constraints, not claims about the minimum size or
duration of a real university dataset.

## 5. Scenario assumptions and variation

The current profiles are:

| Profile | Intended simulated condition | Main variation |
|---|---|---|
| `high_support` | Consistent access and study behaviour | Higher prior performance, attendance, reliability, sleep, and availability. |
| `balanced` | Moderate academic and time conditions | Intermediate values across the main behavioural dimensions. |
| `constrained` | Restricted time and competing commitments | Lower availability, part-time employment, weaker attendance, and irregular study. |
| `backlog_risk` | Higher academic-support need | Lower prior performance, attendance, reliability, sleep, and availability; some term-one backlog enrolments. |

Profiles are assigned cyclically so the 1,000-student default contains equal
profile representation. Gaussian variation is then added to the latent
values, followed by domain clipping. This is a deliberate coverage strategy;
it is not an estimate of the prevalence of these conditions in India.

The current course catalogue covers programming, mathematics, digital logic,
communication, data structures, object-oriented programming, databases,
computer organization, operating systems, networks, software engineering,
and artificial intelligence. Course type, difficulty, credits, assessment
scheme, and estimated effort are included because a planner must prioritize
work using both academic importance and expected effort.

## 6. Relational schema and field rationale

The generated files are CSV representations of the following entities. The
first identifier in each description is the primary key unless stated
otherwise.

| Table | Grain and purpose | Important fields and reason |
|---|---|---|
| `universities` | One row per simulated institution. | Institution identity and state provide organizational context without claiming a real institution. |
| `campuses` | One row per campus. | Supports campus-level scheduling and location context. |
| `departments` | One row per department. | Connects courses and programmes to an academic unit. |
| `programs` | One row per programme. | Stores degree level, duration, regulation scheme, and grading scale so GPA values are interpretable. |
| `students` | One row per student. | Stores stable planning context such as residence, employment, study mode, and consent flag. Protected category is retained only for fairness analysis and must not drive recommendations. |
| `academic_terms` | One row per term. | Defines the temporal boundaries used by all subsequent events. |
| `courses` | One row per catalogue course. | Stores credits, difficulty, course type, assessment scheme, and estimated effort. These determine workload and prioritization. |
| `course_offerings` | One row per course presentation in a term. | Links a course to a term, department, section, faculty placeholder, and attendance rule. |
| `enrollments` | One row per student-offering relationship. | This is the main academic unit for outcomes, attendance, assessment, and planner recommendations. |
| `topics` | One row per course topic. | Provides actionable units smaller than a course for study planning. |
| `course_topics` | One row per course-topic relationship. | Preserves topic order, weight, and deadline metadata. |
| `academic_performance` | One row per student-term. | Stores SGPA, cumulative GPA, attempted/earned/failed credits, and backlog count. It is a longitudinal academic summary and must be time-aligned before use. |
| `class_timetable` | One row per offering schedule. | Connects classes to weekdays, times, rooms, and availability constraints. |
| `attendance_records` | One row per enrollment-class occurrence. | Attendance status and the running percentage support workload and eligibility planning. |
| `assessments` | One row per offering-assessment. | Defines assessment type, date, maximum marks, and weightage. |
| `assessment_attempts` | One row per enrollment-assessment attempt. | Stores observed simulated marks and submission timing. It is useful for progress monitoring but may leak future information if used after its date. |
| `exam_schedule` | One row per scheduled assessment exam. | Makes exam duration and timing explicit for schedule construction. |
| `learning_resources` | One row per topic-resource. | Represents lectures, readings, quizzes, and previous-year papers available to a planner. |
| `resource_interactions` | One row per student-resource interaction. | Measures opening, viewing, completion, and rating behaviour. It is an interaction trace, not a direct measure of learning. |
| `student_topic_state` | One row per enrollment-topic-cutoff snapshot. | Stores mastery, confidence, fatigue, and remaining effort at early observation dates. |
| `availability` | One row per student-day. | Captures available time and competing class, commute, and work hours. |
| `student_preferences` | One row per student. | Stores preferred study period, session length, break length, notification preference, and accessibility needs. |
| `student_goals` | One row per student goal. | Defines the desired GPA or CGPA target and priority used by the planner. |
| `student_goal_progress` | One row per student-term. | Tracks progress and gap relative to the goal. |
| `calendar_constraints` | One row per student-term constraint. | Represents family, placement, or other declared time conflicts. |
| `study_sessions` | One row per planned or attempted study session. | Connects a student, enrollment, and topic to duration, completion, screen use, distraction, and mastery. |
| `break_records` | One row per recorded break. | Supports sustainable scheduling and break-aware recommendations. |
| `sleep_records` | One row per student-day. | Provides consent-based sleep context for planning; it is not a medical record. |
| `daily_wellbeing` | One row per student-day. | Aggregates screen exposure, breaks, sleep, fatigue, concentration, and stress for planning context. |
| `planner_recommendations` | One row per recommendation-session. | Stores recommended duration, break, priority, reason, acceptance, and completion. |
| `recommendation_feedback` | One row per submitted recommendation response. | Measures perceived usefulness and difficulty for future evaluation. |
| `faculty_support` | One row per offering support opportunity. | Represents office hours/tutorial access and response/satisfaction context. |
| `academic_events` | One row per term event. | Captures holidays, festivals, and examinations that affect scheduling. |
| `outcomes` | One row per enrollment. | Stores final grade, pass/withdrawal status, and retake requirement. These are end-of-course labels and must not be used as early features before they occur. |

### 6.1 Important derived features

The following features are appropriate for planner or monitoring experiments
when their timestamps are respected:

| Feature | Definition or construction | Reason |
|---|---|---|
| `cgpa_trend` | Change in cumulative GPA between available terms. | Detects direction of academic progress rather than relying on one level. |
| `earned_credit_ratio` | `earned_credits / attempted_credits`. | Summarizes progression while accounting for course load. |
| `attendance_gap_to_required` | Observed attendance percentage minus the offering threshold. | Directly indicates proximity to an institutional attendance rule. |
| `days_to_next_deadline` | Next assessment/deadline date minus observation date. | Converts the calendar into actionable urgency. |
| `remaining_workload_hours` | Sum of estimated effort not yet completed. | Supports prioritization and realistic scheduling. |
| `focus_ratio` | `active_study_minutes / actual_duration_minutes`. | Distinguishes time spent in a session from active study time. |
| `break_ratio` | `actual_break_minutes / actual_duration_minutes`. | Measures whether a session has planned recovery time. |
| `screen_load` | `screen_time_minutes / active_study_minutes`. | Describes screen exposure relative to active work; it is not a measure of distraction by itself. |
| `sleep_consistency_score` | Variation of daily sleep duration over a chosen window. | Identifies unstable schedules without diagnosing sleep disorders. |
| `study_consistency_score` | Regularity of completed sessions over a chosen window. | Supports habit-aware recommendations. |
| `session_completion_rate` | Completed sessions divided by planned sessions. | Measures adherence to the planner schedule. |
| `schedule_deviation` | `actual_duration_minutes - planned_duration_minutes`. | Measures whether plans systematically over- or under-estimate time. |

## 7. Required statistical profile

Statistics are used to describe the generated data, identify implementation
errors, compare controlled scenarios, and support model evaluation. They do
not turn synthetic observations into population evidence.

### 7.1 Statistics required for every table

| Statistic | Definition | Why it is required |
|---|---|---|
| Row count `n` | Number of records in the table. | Confirms the generated scale and detects missing or duplicated outputs. |
| Column count and schema | Names and data types of fields. | Detects schema drift and ensures downstream code receives the expected contract. |
| Null count and null percentage | Missing values and `missing / n × 100`. | Distinguishes intentional unavailable events from generation defects. |
| Unique count | Number of distinct values in identifier and categorical fields. | Checks identifier uniqueness and reveals whether a category has adequate representation. |
| Duplicate-key count | Number of repeated values for a declared primary key. | A relational table must not contain duplicate primary keys. |
| Frequency and percentage | `count(category) / n × 100`. | Describes categorical balance, such as outcome, residence, profile, and completion status. |

### 7.2 Continuous-variable statistics

For numeric fields, report `n`, missing percentage, mean, median, standard
deviation, minimum, first quartile, third quartile, maximum, and IQR.

| Statistic | Definition | Interpretation and reason |
|---|---|---|
| Mean | `Σxᵢ / n`. | Measures the arithmetic average and is useful when extreme values are not dominant. Use it for aggregate workload, marks, attendance, and time totals. |
| Median | The 50th percentile after sorting. | Represents a typical record and is more robust than the mean when durations, commute, or screen time are skewed. |
| Standard deviation | `sqrt(Σ(xᵢ − mean)² / (n − 1))` for a sample-style descriptive estimate. | Measures dispersion around the mean and checks whether the generator produces meaningful variation rather than identical rows. |
| Minimum and maximum | Smallest and largest observed values. | Detects violations of declared bounds, such as negative hours or scores above 100. |
| Quartiles `Q1`, `Q3` | 25th and 75th percentiles. | Describe the central half of the distribution without assuming normality. |
| IQR | `Q3 − Q1`. | Measures robust spread and helps identify unusually extreme values. |
| Variance | Standard deviation squared. | Useful for comparing dispersion on the original measurement scale only when units are comparable. |
| Skewness | Direction and degree of asymmetry. | Helps decide whether median/IQR should be emphasized over mean/standard deviation. |

Mean and median must be reported together. For example, if mean study time is
substantially higher than median study time, a smaller number of long sessions
may be pulling the average upward. That difference matters to a planner: a
mean-based schedule can overestimate the time available to a typical student.

### 7.3 Binary and rate statistics

For a Boolean or two-class field, report the count and percentage of each
class. For example:

- pass rate = `passed / total outcomes × 100`;
- withdrawal rate = `withdrawn / total outcomes × 100`;
- session completion rate = `completed sessions / planned sessions × 100`;
- recommendation acceptance rate = `accepted recommendations / recommendations × 100`;
- late submission rate = `late submissions / assessment attempts × 100`.

The denominator must always be shown. A rate without its denominator is not
auditable, especially when different tables have different grains.

### 7.4 Grouped statistics

Report the same descriptive statistics by meaningful, non-leaking groups:

- student profile or scenario;
- academic term;
- course and course type;
- difficulty and credit band;
- residence type and employment status;
- observation cutoff;
- recommendation reason and priority.

Grouped comparisons explain whether the generator actually produces the
intended variations. They must not be interpreted as evidence that a real
demographic group is academically better or worse. Protected attributes are
for fairness auditing only and must not be used to personalize a
recommendation.

### 7.5 Relationship statistics

Use Pearson correlation for approximately linear relationships between
continuous variables and Spearman correlation for monotonic relationships or
ordinal variables. Examples include availability versus completed study
minutes, sleep versus fatigue, and attendance versus marks.

These statistics are exploratory association measures. They do not establish
causality because the generator itself creates several variables from shared
latent assumptions. For categorical pairs, use a contingency table and
conditional percentages rather than assigning arbitrary numeric codes.

### 7.6 Model statistics

For binary academic-risk experiments, report the confusion matrix and the
following metrics:

| Metric | Formula or meaning | Reason |
|---|---|---|
| True positive (TP) | Risk correctly identified. | Represents a learner who may receive timely support. |
| False positive (FP) | Non-risk learner flagged as risk. | Measures unnecessary support or attention. |
| True negative (TN) | Non-risk learner correctly not flagged. | Measures appropriate non-intervention. |
| False negative (FN) | Risk learner missed. | Critical operational error because support may not be offered. |
| Accuracy | `(TP + TN) / (TP + TN + FP + FN)`. | Overall correctness, but can be misleading when classes are imbalanced. |
| Precision | `TP / (TP + FP)`. | Reliability of a risk alert. |
| Recall/sensitivity | `TP / (TP + FN)`. | Coverage of learners who need support. |
| Specificity | `TN / (TN + FP)`. | Ability to avoid unnecessary alerts. |
| F1 | Harmonic mean of precision and recall. | Balances missed risk and alert precision. |
| Balanced accuracy | `(sensitivity + specificity) / 2`. | Gives equal importance to both classes. |
| ROC-AUC | Threshold-independent ranking ability across ROC thresholds. | Compares how well models order risk before choosing an intervention threshold. |
| PR-AUC | Area under the precision-recall curve. | Particularly informative when the risk class is uncommon. |
| Brier score | Mean squared error of predicted probabilities. | Evaluates probability quality, which is important when priority depends on risk level. |

Accuracy must never be reported alone. Confusion matrices are required for
the full-course benchmark and for the 30-, 60-, and 90-day cutoff evaluations.
The model-selection rule must be stated before comparison; a suitable default
for this project is ROC-AUC first, balanced accuracy second, and F1 third.

## 8. Leakage and temporal validity

The planner and risk model must use only information available at the decision
time. A feature is valid for an observation date only when its source event is
on or before that date.

The following are future information when they occur after a cutoff and must
not be used as early-warning predictors:

- final grade and final result;
- future assessment marks;
- future attendance;
- withdrawal date;
- post-cutoff study sessions, resource interactions, or feedback;
- future planner completion.

The cutoffs are interpreted as staged decision points:

- **30 days:** earliest support opportunity, with the least evidence;
- **60 days:** mid-course evidence with more observed behaviour;
- **90 days:** later but still potentially actionable evidence;
- **full course:** retrospective benchmark only, not an early intervention
  claim.

Cutoff comparison measures the trade-off between intervention timeliness and
information quantity. It does not prove that 30, 60, or 90 days is optimal.
Production selection requires prospective validation, calibration, intervention
capacity, and an explicit cost for false negatives and false positives.

## 9. Current generated snapshot

The current configured output contains 36 CSV tables and the following key
row counts. Counts are generated from the local synthetic output and are not
population statistics.

| Table or quantity | Count |
|---|---:|
| Students | 1,000 |
| Academic terms | 3 |
| Course offerings | 12 |
| Enrollments | 12,000 |
| Attendance records | 192,000 |
| Assessment attempts | 36,000 |
| Availability records | 336,000 |
| Daily wellbeing records | 336,000 |
| Sleep records | 336,000 |
| Study sessions | 96,000 |
| Planner recommendations | 96,000 |
| Topic-state snapshots | 144,000 |
| Total CSV data rows | 1,780,456 |

Selected descriptive values from the current seeded snapshot are included to
demonstrate the required reporting format:

| Table and variable | Mean | Median | Standard deviation | IQR (`Q1–Q3`) | Range |
|---|---:|---:|---:|---:|---:|
| `academic_performance.semester_gpa` | 6.70 | 6.59 | 1.42 | 5.53–7.86 | 4.00–10.00 |
| `attendance_records.attendance_percentage` | 80.12 | 84.62 | 20.82 | 66.67–100.00 | 0.00–100.00 |
| `assessment_attempts.marks_obtained` | 87.05 | 89.41 | 12.62 | 77.19–100.00 | 39.15–100.00 |
| `availability.available_hours` | 2.50 | 2.42 | 1.09 | 1.68–3.32 | 0.25–6.52 |
| `study_sessions.actual_duration_minutes` | 49.98 | 51.00 | 25.48 | 37.00–67.00 | 0.00–103.00 |
| `sleep_records.total_sleep_hours` | 6.53 | 6.53 | 1.04 | 5.80–7.27 | 3.50–9.50 |
| `daily_wellbeing.total_screen_minutes` | 229.61 | 228.00 | 75.01 | 177.00–280.00 | 12.00–612.00 |
| `daily_wellbeing.fatigue_score` | 0.47 | 0.00 | 0.69 | 0.00–0.80 | 0.00–4.68 |

These values are a quality-control snapshot of seed 42. They are not target
benchmarks and must be regenerated whenever the configuration, code, or seed
changes.

## 10. Interpretation rules

1. Report counts with their table grain. An enrollment is not a unique student.
2. Report means together with medians and spread because time and activity
   variables can be skewed.
3. Preserve missing values as unknown unless a documented data-generating
   reason supports another treatment. A missing mark is not a zero mark.
4. Treat VLE/resource interactions as recorded activity, not study duration or
   learning achievement.
5. Treat sleep, screen time, fatigue, concentration, and stress as
   consent-based planning context, not medical diagnosis.
6. Do not infer causation from correlations or from the latent simulation
   mechanism.
7. Compare models with confusion matrices and class-aware metrics, not
   accuracy alone.
8. Never report synthetic descriptive statistics or model scores as evidence
   about real students.

## 11. Verification checklist

Before accepting a generated version, run:

```powershell
python -m pytest -q
ruff check src pipeline tests
dvc repro simulate
dvc status simulate
```

The output should be checked for:

- expected table count and manifest configuration;
- unique primary keys;
- valid foreign keys between students, offerings, enrollments, topics, and
  child records;
- numeric values inside their declared domains;
- documented missingness only;
- representation of all four scenario profiles;
- reproducibility when the same seed and configuration are used;
- no leakage of post-cutoff fields into early-warning features.

## 12. Limitations and future extensions

The current generator models one synthetic B.Tech CSE programme, one campus,
one section per offering, and a fixed set of behavioural profiles. It does not
represent the full diversity of Indian institutions, curricula, languages,
assessment policies, socioeconomic conditions, disability experiences, or
student support systems. The distributions are hand-specified and several
variables share latent drivers by design.

Future work should add configuration-driven institutions, multiple sections,
more course and assessment variants, explicit missing-data mechanisms,
calibration against authorised aggregate institutional statistics, and
prospective validation with consented, de-identified data. Any such extension
must preserve provenance, privacy, temporal validity, and the distinction
between simulated and observed data.

### 12.1 Improvements implemented in the current generator

The generator now addresses several development gaps without presenting the
simulation as real institutional evidence:

- `curriculum_prerequisites.csv` makes course dependencies explicit. The
  feature pipeline derives prerequisite count and unmet-prerequisite count
  using only prerequisite outcomes from earlier terms.
- `academic_performance` is joined as lagged history. The feature pipeline
  exposes prior-term GPA, prior cumulative GPA, prior failed credits, prior
  backlog count, and prior completed terms only when those records precede the
  current offering.
- Student context includes prior education stream, first-generation status,
  internet access type, financial-aid status, and preferred language. These
  fields support documented subgroup analysis; sensitive and consent-related
  fields are excluded from the default baseline predictor matrix.
- `early_warning_targets.csv` provides separate simulated labels for final
  non-pass, withdrawal, attendance-requirement breach, late submission,
  low-assessment performance, and study-plan abandonment. These labels support
  future task-specific models and are not causal intervention outcomes.
- The configurable `missingness_rate` applies deterministic, seed-controlled
  missingness to observational fields while preserving identifiers, dates, and
  relational keys. Missingness is intentionally visible so preprocessing can
  be tested under incomplete-data conditions.

These changes improve software and schema realism. They do not resolve the
fundamental limitations of synthetic provenance, institutional diversity, or
prospective validation. Those require authorised aggregate statistics and
consented, de-identified observations and must not be fabricated.
