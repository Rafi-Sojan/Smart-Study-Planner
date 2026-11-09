# Student input and feature-derivation specification

## 1. Purpose

The student interface must request only information that a learner can
understand and reasonably provide. Engineered OULAD and synthetic-model columns
are implementation details and are not student form fields. This separation
reduces entry burden, prevents accidental identifier collection, and avoids
asking a learner to reproduce university records manually.

The standalone application is a demonstration without an LMS connection. Its
academic snapshot is therefore self-reported and provisional. It is not a
substitute for observed institutional activity, and it does not establish that
an OULAD early-warning model is valid for the current institution.

## 2. Responsibility boundary

| Actor | Information or operation |
|---|---|
| Student | Goal, subjects, tasks, deadlines, available study windows, preferred session and break lengths, optional academic estimates, and required bounded wellbeing ratings |
| University/LMS | Enrolment, verified attendance, assessment history, prior results, registration context, and digital engagement activity |
| FastAPI backend | Contract-ordered feature construction, compatible aggregation, missing-value preservation, model invocation, evidence summary, task ranking, and scheduling |
| Risk model | Support-risk score used internally by the planner |
| Planner | Reviewable schedule, task rationale, capacity shortfall, recommendations, and support-review indicator |

The normal student request does not accept `model_id`, raw model columns,
thresholds, registry URIs, hashes, or artifact paths. It always uses the
deployment's reviewed default model. Those controls remain in the explicit
administrator testing interface.

## 3. Standalone demonstration intake

Required student fields are:

- primary planning goal;
- one or more subject names;
- course style;
- current semester or term;
- typical sleep hours;
- bounded stress, fatigue, and concentration ratings;
- at least one task with title, subject, deadline, estimated effort,
  difficulty, and importance;
- at least one timezone-aware availability window; and
- preferred session and break lengths.

The following bounded fields are optional because they are self-reported
stand-ins until an institution supplies verified records:

- previous CGPA;
- recent assessment average;
- attendance estimate;
- assignment-submission rate;
- independent study hours per week;
- current credit load;
- confidence rating.

The four wellbeing values are mandatory for this standalone planner workflow
because it produces wellbeing-aware scheduling recommendations. They remain
self-reported planning context, not clinical measurements or diagnostic data.
An institutional deployment must establish an appropriate lawful basis,
explain the purpose and retention period, restrict access, and review whether
an alternative or opt-out is required by local governance.

Names, registration numbers, email addresses, credentials, diagnoses, and
free-text wellbeing information are neither required nor accepted by this
schema.

## 4. Derivation rules

`src/api/student_features.py` starts with the fitted model's exact ordered
contract and assigns `null` to every unavailable feature. It then maps only
meaning-compatible values:

| Understandable source | Compatible fitted features |
|---|---|
| Course style | `course_type` |
| Current term | `term_number` |
| Current credit load | `credits`, `studied_credits` |
| Previous CGPA | `prior_semester_gpa`, `prior_cumulative_gpa` |
| Recent average | `assessment_mean_score`, `assessment_score_mean` |
| Attendance estimate | `attendance_pct_at_cutoff`, `attendance_pct_mean` |
| Submission-rate estimate | `assessment_submitted_rate`, converted from percent to proportion |
| Weekly study estimate | `active_study_minutes`, scaled to the configured observation window and explicitly treated as a proxy |
| Confidence rating | `mean_confidence_score`, normalized from 1–5 to 0–1 |
| Task workload | `remaining_effort_hours` and a coarse task-difficulty category |
| Availability windows | `mean_available_hours` |
| Sleep | `mean_sleep_hours` and non-negative deficit relative to eight hours |
| Stress, fatigue, concentration | Corresponding bounded mean fields where present in the fitted contract |

The adapter deliberately does **not** synthesize LMS clicks, active days,
resource counts, registration dates, verified assessment counts, late
submissions, attendance event counts, prior attempts, backlogs, prerequisites,
identifiers, outcomes, or post-outcome fields. Missing compatible values remain
`null`; the fitted preprocessing pipeline controls imputation.

## 5. Evidence communication

The student response omits the numerical probability, threshold, model name,
version, feature names, and contract digest. It returns an understandable
support level and an evidence summary containing:

- whether institutional data is connected;
- whether current evidence is limited or partial;
- the high-level sources used; and
- a formal warning that the self-reported demonstration signal is provisional.

The evidence label is not a calibration or validity measure. Coverage means
only that more fitted inputs were constructible; it does not show that the
inputs are accurate or that transfer to the local student population is valid.

## 6. Institutional integration requirements

Replacing the demonstration adapter requires a reviewed LMS/SIS connector with
field-level provenance, units, cutoff logic, freshness rules, missingness
handling, consent or lawful-basis review, retention limits, access controls,
reconciliation, and failure behavior. Institutional fields must be transformed
using the same definitions used during training. Until prospective local
validation and intervention governance are complete, every output remains
research decision support requiring human review.
