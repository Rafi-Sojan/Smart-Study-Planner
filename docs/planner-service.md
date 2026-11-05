# Study-planner service specification

## Scope

`POST /v1/study-plan` combines the loaded risk model with deterministic task
prioritization and capacity-constrained scheduling. It returns a proposed plan
for learner or adviser review. It must not be used to impose academic,
disciplinary, admissions, attendance, or financial-aid decisions.

The endpoint accepts the exact model feature contract, one or more tasks, and
timezone-aware availability windows. Task identifiers must be unique;
availability windows must not overlap; and completed work cannot exceed the
estimated work. The same API-key and model-readiness controls used by the risk
endpoint apply to the planner endpoint.

## Priority calculation

For each incomplete task, `src/planner/prioritizer.py` computes a score in the
range zero to one:

```text
0.35 × deadline urgency
+ 0.25 × task importance
+ 0.15 × task difficulty
+ 0.15 × workload pressure
+ 0.10 × course-risk score
```

Urgency increases as a deadline approaches and reaches one when overdue.
Workload pressure compares remaining minutes with a transparent planning
capacity of 120 minutes per available calendar day. Importance and difficulty
are bounded one-to-five inputs. Risk is deliberately limited to ten percent of
the priority score so that a model output cannot erase deadlines or dominate
the learner's declared task context. Ties are resolved by deadline and task ID,
making the result reproducible. Any "elevated risk" rationale or supportive
review recommendation uses the approved operating threshold loaded with the
model, rather than an independent hard-coded decision boundary.

## Scheduling

`src/planner/scheduler.py` allocates ranked work into chronological,
non-overlapping availability windows. Sessions use a configurable duration of
15–120 minutes and an explicit zero-to-30-minute break. Tasks rotate between
sessions so one large task does not silently consume every window. The service
returns every unallocated minute by task; it never implies that infeasible work
has been completed.

Recommendations explain the first priority, capacity shortfalls, breaks, and
when a supportive tutor or adviser review may be appropriate. The response
always sets `human_review_required=true`.

## Safety and limitations

The scheduler does not infer sleep requirements, disability accommodations,
transport, caring duties, employment constraints, or clinical wellbeing. Such
constraints require explicit, consented product design and human review. The
risk score is a screening signal rather than a diagnosis or causal estimate.
Planner usefulness and harm must be evaluated prospectively with learners and
support staff before any live release.
