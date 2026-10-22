# OULAD and Synthetic Smart Study Planner Data

## Purpose

This directory documents the synthetic Indian-university data model that complements the project's real OULAD experiments. The generated CSV records are stored under `data/raw/synthetic/`; the two sources serve different purposes:

- **OULAD** provides a real-world benchmark for predicting academic risk.
- **Synthetic Indian-university data** provides planner-specific variables that OULAD does not contain, including CGPA, attendance, course topics, study availability, sleep, screen time, breaks, and planner interactions.

The sources must not be concatenated into one training table. OULAD is used for leakage-aware risk modelling, while the synthetic data is used to develop and test study-planning and recommendation workflows.

This README documents the intended schema and generation requirements. It does not claim that synthetic records are real student observations.

The formal methodology, generator-function reference, statistical definitions,
quality-control snapshot, and rationale for each processing step are documented
in [docs/synthetic-data.md](../../docs/synthetic-data.md).

## Reproduce the dataset

From the repository root, activate the project environment and run:

```powershell
python -m src.simulation.simulator --config configs/simulation.yaml --overwrite
```

The generator writes one CSV per relational table and a `manifest.json` file
under `data/raw/synthetic/`, containing the seed, configuration, row counts,
and limitations. Generated records are ignored by Git. The equivalent DVC stage is declared as
`simulate` in the repository's `dvc.yaml`; `--overwrite` is included in that
stage so a deliberate DVC reproduction can replace the exact generated output
directory.

The repository default is 1,000 students, three academic terms, and 16 weeks
per term. The manifest is the authoritative record of the configuration and
row counts for a particular generated run. `data/raw/oulad/` remains reserved
for the real OULAD archive and must not contain synthetic files.

## Intended use

The synthetic dataset is designed for a configurable B.Tech Computer Science pilot covering multiple semesters and realistic Indian-university conditions, including:

- semester-based academic calendars;
- CBCS, NEP-style, or institution-specific credit structures;
- theory, laboratory, project, elective, and seminar courses;
- internal assessments, assignments, practicals, viva examinations, and end-semester examinations;
- configurable attendance requirements;
- backlogs, supplementary examinations, and repeated course attempts;
- university holidays, festivals, examinations, and other academic events;
- student availability, commute time, sleep, screen time, breaks, and study behaviour.

Institution-specific rules must be configuration values. For example, an attendance threshold must not be assumed to be 75% for every university.

## Dataset separation

### OULAD risk track

OULAD is used to estimate the probability of `Fail` or `Withdrawn` using information available before a defined cutoff. The binary target is:

```text
risk_label = 1: Fail or Withdrawn
risk_label = 0: Pass or Distinction
```

The current project evaluates full-course, 30-day, 60-day, and 90-day observation windows. OULAD module and presentation codes must remain unchanged; they must not be renamed as Indian courses without a documented mapping.

### Synthetic planner track

The synthetic track models a student, course, topic, daily state, study session, recommendation, and eventual academic outcome. It is intended to support scheduling and recommendation experiments, not to manufacture evidence of real-world student performance.

## Proposed course catalogue

The initial synthetic pilot uses a B.Tech Computer Science programme with representative course types:

| Course | Type | Credits |
|---|---|---:|
| Engineering Mathematics I | Theory | 4 |
| Programming Fundamentals | Theory and laboratory | 4 |
| Digital Logic Design | Theory and laboratory | 4 |
| Communication Skills | Theory | 2 |
| Data Structures and Algorithms | Theory and laboratory | 4 |
| Object-Oriented Programming | Theory and laboratory | 4 |
| Database Management Systems | Theory and laboratory | 4 |
| Computer Organization | Theory | 3 |
| Operating Systems | Theory | 4 |
| Computer Networks | Theory and laboratory | 4 |
| Software Engineering | Theory | 3 |
| Artificial Intelligence Fundamentals | Elective or theory | 3 |

These course definitions are synthetic design assumptions. They are not claims about a particular Indian university curriculum.

## Attribute specification

### `UNIVERSITIES`

```text
university_id
university_name
state
accreditation_category
```

### `CAMPUSES`

```text
campus_id
university_id
campus_name
city
```

### `DEPARTMENTS`

```text
department_id
campus_id
department_name
```

### `PROGRAMS`

```text
program_id
department_id
program_name
degree_level
regulation_scheme
duration_years
grading_scale
```

### `STUDENTS`

```text
student_id
program_id
admission_year
category
study_mode
residence_type
employment_status
consent_status
```

`category` is optional protected information. It must not be used to generate study recommendations. If retained, it should be access-controlled and used only for fairness analysis.

### `ACADEMIC_TERMS`

```text
term_id
university_id
academic_year
semester_name
start_date
end_date
exam_session
```

### `COURSES`

```text
course_id
program_id
course_code
course_name
course_type
credits
difficulty
assessment_scheme
estimated_effort_hours
```

### `COURSE_OFFERINGS`

```text
offering_id
course_id
term_id
department_id
section
faculty_id
attendance_requirement_percent
```

### `ENROLLMENTS`

```text
enrollment_id
student_id
offering_id
attempt_number
is_backlog
enrollment_status
enrollment_date
```

### `TOPICS`

```text
topic_id
topic_name
difficulty
estimated_effort_hours
prerequisite_topic_id
```

### `COURSE_TOPICS`

```text
course_topic_id
course_id
topic_id
sequence_order
assessment_weight
recommended_deadline
```

### `ACADEMIC_PERFORMANCE`

```text
performance_id
student_id
term_id
semester_gpa
cumulative_gpa
grading_scale
attempted_credits
earned_credits
failed_credits
backlog_count
result_date
```

CGPA and SGPA must be interpreted with their associated grading scale. Final or future performance must not be used as an early-warning feature.

### `CLASS_TIMETABLE`

```text
timetable_id
offering_id
weekday
start_time
end_time
room
```

### `ATTENDANCE_RECORDS`

```text
attendance_id
enrollment_id
class_date
attendance_status
attendance_percentage
attendance_gap_to_required
```

### `ASSESSMENTS`

```text
assessment_id
offering_id
assessment_type
assessment_date
maximum_marks
weightage
```

### `ASSESSMENT_ATTEMPTS`

```text
attempt_id
assessment_id
enrollment_id
marks_obtained
grade
is_supplementary
submission_status
late_submission
```

### `STUDENT_TOPIC_STATE`

```text
state_id
enrollment_id
topic_id
observation_date
mastery_score
confidence_score
fatigue_score
remaining_effort_hours
```

### `AVAILABILITY`

```text
availability_id
student_id
availability_date
available_hours
class_hours
commute_hours
part_time_work_hours
availability_reason
```

### `STUDENT_PREFERENCES`

```text
preference_id
student_id
preferred_study_period
preferred_session_minutes
preferred_break_minutes
notification_preference
accessibility_needs
```

### `STUDY_SESSIONS`

```text
session_id
student_id
enrollment_id
topic_id
planned_start
actual_start
planned_duration_minutes
actual_duration_minutes
active_study_minutes
screen_time_minutes
distraction_minutes
planned_break_minutes
actual_break_minutes
break_count
session_mode
device_type
completion_status
post_session_mastery
```

### `BREAK_RECORDS`

```text
break_id
session_id
break_start
break_end
duration_minutes
break_type
planned
restorative_rating
```

### `SLEEP_RECORDS`

```text
sleep_id
student_id
sleep_date
sleep_start
wake_time
total_sleep_hours
sleep_quality_score
nap_minutes
sleep_interruptions
sleep_source
```

### `DAILY_WELLBEING`

```text
wellbeing_id
student_id
observation_date
academic_screen_minutes
recreational_screen_minutes
total_screen_minutes
total_break_minutes
sleep_hours
sleep_deficit_hours
fatigue_score
concentration_score
stress_score
```

Sleep, screen-time, fatigue, concentration, and stress fields are optional, consent-based, and intended for planning support rather than medical diagnosis.

### `PLANNER_RECOMMENDATIONS`

```text
recommendation_id
enrollment_id
topic_id
recommendation_date
recommended_duration_minutes
recommended_break_minutes
priority
recommendation_reason
accepted
completed
```

### `ACADEMIC_EVENTS`

```text
event_id
university_id
event_date
event_type
event_name
affects_classes
```

### `OUTCOMES`

```text
outcome_id
student_id
offering_id
final_grade
result_status
passed
withdrawn
requires_retake
```

### Risk and provenance metadata

These fields should be attached to feature snapshots or stored in a separate metadata table:

```text
oulad_risk_score
risk_band
observation_date
cutoff_days
data_source
scenario_id
random_seed
feature_collection_method
missingness_flag
```

## Useful derived features

```text
cgpa_trend
semester_gpa_trend
earned_credit_ratio
activity_trend
days_since_last_activity
assignment_submission_rate
attendance_gap_to_required
days_to_next_deadline
remaining_workload_hours
focus_ratio
break_ratio
screen_load
sleep_consistency_score
study_consistency_score
session_completion_rate
schedule_deviation
```

Example definitions:

```text
focus_ratio = active_study_minutes / actual_duration_minutes
break_ratio = actual_break_minutes / actual_duration_minutes
screen_load = screen_time_minutes / active_study_minutes
schedule_deviation = actual_duration_minutes - planned_duration_minutes
```

## Scenario coverage

The generator should cover controlled variants rather than arbitrary combinations.

### Course variants

- theory;
- programming;
- laboratory;
- mathematics;
- project;
- elective;
- seminar;
- backlog or supplementary course;
- high-credit and low-credit courses.

### Student variants

- high, medium, and low prior CGPA;
- strong, moderate, and weak attendance;
- regular and irregular study behaviour;
- hosteller and day scholar;
- short and long commute;
- part-time employment;
- different weekly availability;
- repeated or backlog courses.

### Behaviour variants

- regular and reduced sleep;
- low, moderate, and high screen time;
- planned and unplanned breaks;
- completed, partial, and missed study sessions;
- accepted, ignored, and partially followed recommendations.

Every generated record should include `scenario_id` and `random_seed` so that a scenario can be reproduced.

## Leakage and evaluation rules

For a cutoff-based prediction task, each feature snapshot must contain only information available on or before its `observation_date` or `cutoff_days`.

The following must not be used as early-warning features when they occur after the cutoff:

```text
final_result
final_grade
future_assessment_score
future_attendance
withdrawal_date
post-cutoff study activity
future planner completion
```

Training and test partitions should be chronological or student-disjoint, depending on the experiment. The split strategy must be documented with every experiment.

## Privacy and governance

- Do not scrape identifiable student records.
- Use authorized, de-identified institutional data for future real-data extensions.
- Store aggregate screen-time values rather than application names, screenshots, keystrokes, or browsing histories.
- Collect sleep and wellbeing data only with explicit consent.
- Restrict protected demographic attributes to fairness auditing.
- Mark every record with its data source.
- Never report synthetic results as real student performance.

## Relationship to project components

```text
OULAD data
  -> cleaning and feature extraction
  -> leakage-aware risk models
  -> MLflow experiment tracking

Synthetic Indian-university data
  -> configurable scenario generation
  -> planner and recommendation features
  -> scheduling and interaction experiments
```

The synthetic dataset should eventually be replaced or supplemented by consented application telemetry and institutional records. Until then, it is a reproducible development and demonstration resource, not evidence of production effectiveness.
