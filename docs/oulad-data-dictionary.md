# OULAD raw-data dictionary and feature map

## Scope and provenance

This document describes the seven standard CSV tables used by the Open
University Learning Analytics Dataset (OULAD), the row unit of each table, the
raw column meanings, and the derived features used by this repository. The
observed row counts below come from the existing executed processing notebook
and the supplied `oulad-dataset.zip`. They are properties of that local release
and should be regenerated if a different archive is supplied.

OULAD contains anonymised information about courses, students, assessments,
registration, and Virtual Learning Environment (VLE) activity. The official
dataset description is available in the [OULAD Scientific Data
paper](https://doi.org/10.1038/sdata.2017.171) and the [OU Analyse dataset
page](https://research.stem.open.ac.uk/ouanalyse/dataset/).

## Raw table inventory

| CSV table | Row unit | Observed rows | Raw columns | Repository role |
|---|---|---:|---:|---|
| `studentInfo.csv` | One student registered on one module presentation | 32,593 | 12 | Required enrollment population and final outcome |
| `studentRegistration.csv` | One registration record for one student-module-presentation combination | 32,593 | 5 | Registration timing and withdrawal timing |
| `assessments.csv` | One assessment definition offered in one module presentation | 206 | 6 | Assessment catalog and join map |
| `studentAssessment.csv` | One recorded student result for one assessment | 173,912 | 5 | Assessment submissions and scores |
| `courses.csv` | One module presentation | 22 | 3 | Course/presentation duration metadata |
| `vle.csv` | One VLE learning-material item in one module presentation | 6,364 | 6 | Resource catalog and activity join map |
| `studentVle.csv` | One student's daily interaction with one VLE item | 10,655,280 | 6 | Daily online activity and click counts |

The tables have different row units. A raw row count is therefore not a
student count unless the table and population are explicitly stated. The model
unit is created later: one row per student-module-presentation enrollment.

## Identifier relationships

The relationships used by the project are:

- `studentInfo` joins to `studentRegistration` and `studentVle` using
  `id_student` together with `code_module` and `code_presentation` where
  needed.
- `courses` identifies a module presentation using
  `code_module` and `code_presentation`.
- `assessments` joins to `studentAssessment` using `id_assessment`.
- `vle` joins to `studentVle` using `id_site`.
- `code_module` identifies the module, while `code_presentation` identifies a
  particular offering of that module.

## `studentInfo.csv`

This is the enrollment-level demographic and final-outcome table. Its row unit
is one student enrolled in one module presentation.

| Column | Meaning | Modeling interpretation |
|---|---|---|
| `code_module` | Identifier of the module/course | Categorical enrollment context and join key |
| `code_presentation` | Identifier of the module presentation/term | Categorical presentation context, join key, and time-split key |
| `id_student` | Anonymised student identifier | Join key and audit identifier; excluded from model inputs |
| `gender` | Recorded student gender category | Categorical demographic context; not a causal explanation |
| `region` | Geographic region category | Categorical demographic context |
| `highest_education` | Highest education level reported at entry | Categorical entry-background feature |
| `imd_band` | Band of the Index of Multiple Deprivation for the student's area | Anonymised socioeconomic-context category; missingness is retained |
| `age_band` | Age category rather than exact age | Categorical age-context feature |
| `num_of_prev_attempts` | Number of previous attempts at the module | Numeric prior-experience feature |
| `studied_credits` | Total credits being studied in the current period | Numeric workload/context feature |
| `disability` | Declared disability indicator | Categorical learner-context field; requires careful fairness interpretation |
| `final_result` | Final module outcome: `Pass`, `Distinction`, `Fail`, or `Withdrawn` | Supervised-learning source label; excluded from model inputs |

The repository derives `target_risk` from `final_result`: `Fail` and
`Withdrawn` become `1`, while `Pass` and `Distinction` become `0`. This is a
risk-screening grouping, not a claim that failure and withdrawal have the same
cause or intervention requirement.

## `studentRegistration.csv`

This table records when a student registered for and, when applicable,
unregistered from a module presentation. Dates are measured in days relative
to the presentation start; negative values indicate activity before the
official start.

| Column | Meaning | Modeling interpretation |
|---|---|---|
| `code_module` | Module identifier | Join key |
| `code_presentation` | Presentation identifier | Join key and time context |
| `id_student` | Anonymised student identifier | Join key |
| `date_registration` | Relative day of registration | Enrollment-timing feature |
| `date_unregistration` | Relative day of unregistration; empty for students who completed | Retrospective field; excluded from cutoff-based early-warning features because it can reveal withdrawal |

The full-course baseline may include the registration fields as retrospective
features. The early-warning feature builder deliberately uses only
`date_registration` and excludes future `date_unregistration`.

## `assessments.csv`

This is the assessment catalog. Each row defines an assessment offered by a
module presentation.

| Column | Meaning | Modeling/processing interpretation |
|---|---|---|
| `code_module` | Module identifier to which the assessment belongs | Join key |
| `code_presentation` | Presentation identifier to which the assessment belongs | Join key |
| `id_assessment` | Assessment identifier | Primary join key to `studentAssessment` |
| `assessment_type` | Assessment type: commonly `TMA`, `CMA`, or `Exam` | Assessment-structure category |
| `date` | Planned/final submission day relative to presentation start | Used to understand assessment timing and filter observations at a cutoff |
| `weight` | Assessment contribution weight in percent | Assessment-structure metadata; not used as a raw learner score |

## `studentAssessment.csv`

This table contains recorded student assessment results. A missing score means
that the release contains no score for that record; it is not converted to
zero.

| Column | Meaning | Modeling/processing interpretation |
|---|---|---|
| `id_assessment` | Assessment identifier | Join key to the assessment catalog |
| `id_student` | Anonymised student identifier | Join key |
| `date_submitted` | Day of submission relative to presentation start | Used for cutoff filtering; future submissions are excluded in early-warning mode |
| `is_banked` | Indicator that a result was carried over/banked from an earlier presentation | Assessment-record context; retained during cleaning |
| `score` | Student score on a 0–100 scale | Aggregated into score count, mean, standard deviation, minimum, maximum, and missing-score count |

## `courses.csv`

This table contains one row per module presentation.

| Column | Meaning | Modeling/processing interpretation |
|---|---|---|
| `code_module` | Module identifier | Presentation join key |
| `code_presentation` | Presentation identifier | Presentation join key |
| `module_presentation_length` | Length of the presentation in days | Course-duration metadata; useful for temporal interpretation |

This table is loaded and audited by the repository but is not currently a
direct input to the baseline feature matrix.

## `vle.csv`

This is the catalog of learning-material items available in the VLE.

| Column | Meaning | Modeling/processing interpretation |
|---|---|---|
| `id_site` | Identifier of the VLE material/resource | Primary join key to `studentVle` |
| `code_module` | Module identifier | Join key |
| `code_presentation` | Presentation identifier | Join key |
| `activity_type` | Type/role of the VLE material, such as a page, file, or other activity | Resource-category metadata |
| `week_from` | Planned first week of availability/use | Resource timing metadata; may be missing |
| `week_to` | Planned final week of availability/use | Resource timing metadata; may be missing |

## `studentVle.csv`

This is a daily summary of student interactions with VLE materials.

| Column | Meaning | Modeling/processing interpretation |
|---|---|---|
| `code_module` | Module identifier | Join key |
| `code_presentation` | Presentation identifier | Join key |
| `id_student` | Anonymised student identifier | Join key |
| `id_site` | VLE material identifier | Join key to `vle` |
| `date` | Relative day of interaction | Used for cutoff filtering and active-day counts |
| `sum_click` | Number of recorded interactions with the material on that day | Aggregated as total clicks; not interpreted as study hours or attention duration |

## Derived enrollment-level feature matrix

The feature builder aggregates the raw event tables to one row per
student-module-presentation enrollment. The following fields are currently
constructed:

| Derived feature | Source | Definition |
|---|---|---|
| `target_risk` | `studentInfo.final_result` | `1` for `Fail`/`Withdrawn`; `0` for `Pass`/`Distinction` |
| Demographic and enrollment categories | `studentInfo` | Gender, region, education, deprivation band, age band, disability, module, presentation |
| `num_of_prev_attempts` | `studentInfo` | Number of previous module attempts |
| `studied_credits` | `studentInfo` | Current studied-credit total |
| `assessment_count` | `studentAssessment` + `assessments` | Number of distinct assessments represented for the enrollment |
| `assessment_score_mean` | `studentAssessment.score` | Mean observed score |
| `assessment_score_std` | `studentAssessment.score` | Standard deviation of observed scores |
| `assessment_score_min` | `studentAssessment.score` | Minimum observed score |
| `assessment_score_max` | `studentAssessment.score` | Maximum observed score |
| `assessment_score_missing` | `studentAssessment.score` | Number of missing score values |
| `date_registration` | `studentRegistration` | Mean/available registration date for the enrollment |
| `date_unregistration` | `studentRegistration` | Retrospective field available only in the full-course feature path; not available at an early cutoff |
| `vle_clicks` | `studentVle` | Sum of `sum_click` across observed activity |
| `vle_active_days` | `studentVle` | Number of distinct interaction days |
| `vle_resources` | `studentVle` + `vle` | Number of distinct VLE resources accessed |

The identifier fields `id_student` and `id_presentation` are retained for
inspection or splitting but removed from model inputs. `final_result` is
retained for label construction and audit only. Assessment submissions and VLE
rows are filtered by `date_submitted` or `date` when a 30-, 60-, or 90-day
cutoff is requested.

## Cleaning rules affecting the raw columns

The cleaner uses conservative validation:

- required columns and files are checked explicitly;
- numeric identifier, date, weight, registration, and activity fields are
  coerced where appropriate;
- scores outside 0–100 are converted to missing;
- missing scores remain missing and are not changed to zero;
- invalid or missing final outcomes are excluded from supervised training;
- duplicate assessment definitions are reduced by `id_assessment`; and
- VLE click counts remain activity counts rather than being converted to study
  duration.

The raw-to-clean row counts for the supplied release are unchanged in the
existing run: 32,593 `studentInfo` rows, 173,912 `studentAssessment` rows,
206 `assessments` rows, 32,593 `studentRegistration` rows, 22 `courses` rows,
6,364 `vle` rows, and 10,655,280 `studentVle` rows.

## Interpretation and limitations

The raw fields describe observed records, not complete psychological,
educational, or scheduling states. Demographics are context variables, VLE
clicks measure logged activity, and assessment scores are observed performance
signals. None alone establishes ability, motivation, study duration, or the
causal effect of an intervention. In particular, `date_unregistration` and
complete-course aggregates are unsuitable for an early-warning claim unless
their availability at the prediction time is guaranteed.
