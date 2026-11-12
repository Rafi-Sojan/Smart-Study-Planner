# Durable project decisions

These records summarise decisions that should not change incidentally during an
implementation task. Amend this file and the corresponding formal documentation
when a decision is deliberately revised.

## D-001 — Separate evidence roles

**Decision:** OULAD remains the principal retrospective academic-risk benchmark,
KU Leuven remains external comparison evidence, and the synthetic
Indian-university data remains development-only.

**Consequence:** Synthetic results cannot establish real-student validity,
fairness, calibration, intervention effectiveness, or deployment readiness.

## D-002 — Enforce observation cutoffs before aggregation

**Decision:** Early-warning features are constructed only from evidence
available by day 30, 60, or 90. Outcomes, withdrawal dates, final-course fields,
and future activity are excluded.

**Consequence:** Leakage control takes precedence over a higher retrospective
score. Full-course results are labelled as retrospective benchmarks.

## D-003 — Use one canonical generated-artifact tree

**Decision:** Generated estimators, metrics, and validation evidence live under
`artifacts/models/`, `artifacts/metrics/`, and `artifacts/validation/`.

**Consequence:** DVC owns generated contents and lineage. Source-code model
implementations stay in `src/models/`; MLflow does not replace DVC lineage.

## D-004 — Keep engineered features away from students

**Decision:** The student interface requests understandable goals, tasks,
availability, preferences, academic context, and wellbeing context. The backend
loads institutional evidence and derives fitted features.

**Consequence:** Raw feature entry, model hashes, registry URIs, and diagnostics
are restricted to explicit operator or administrator surfaces.

## D-005 — Require bounded wellbeing context

**Decision:** Sleep hours, stress, fatigue, and concentration are required in the
standalone intake.

**Consequence:** These fields remain self-reported, non-clinical planning
context. They require purpose limitation, privacy, access, and retention
controls and must not be presented as diagnoses.

## D-006 — Compare four baseline model families

**Decision:** Baseline evaluation compares logistic regression, random forest,
extra trees, and histogram gradient boosting under the same split and metric
contract.

**Consequence:** Model selection is evidence-based across linear, bagged-tree,
randomised-tree, and boosted-tree behaviours. Changing the set requires updated
rationale, tests, metrics, notebooks, and documentation.

## D-007 — Separate registration from approval

**Decision:** MLflow registration records a candidate; it does not approve or
promote the model.

**Consequence:** Production requires an immutable numeric registry version plus
quality, fairness, feature-contract, integrity, and human-review evidence.

## D-008 — Preserve blocked quality assessments

**Decision:** `dvc repro model_quality` produces deterministic reports for all
configured tracks. A valid assessment may end in `blocked`.

**Consequence:** CI retains the report as evidence. Only a true promotion
boundary uses strict non-zero failure, and policies must not be weakened to
manufacture a pass.

## D-009 — Keep external side effects explicit

**Decision:** Local pipeline execution does not contact DagsHub unless tracking
or registration is explicitly requested. Git commits, pushes, DVC pushes,
registrations, builds, and deployments are reported only after they complete.

**Consequence:** A local implementation result is not represented as an external
release or deployed service.

## D-010 — Keep the Render path demonstration-only

**Decision:** Render uses one authenticated web service in which Nginx serves
React and proxies a loopback-only FastAPI process. The Blueprint sets
`APP_ENV=development` and loads a registered research candidate from MLflow.

**Consequence:** The Render path preserves same-origin browser security without
silently creating a paid private service. It does not bypass or replace the
production model gates, Kubernetes topology, prospective evidence, monitoring,
or institutional approval requirements.
