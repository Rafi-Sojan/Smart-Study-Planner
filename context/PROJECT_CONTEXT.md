# Smart Study Planner project context

## Purpose

Smart Study Planner is an educational analytics demonstrator that combines
leakage-aware academic-risk estimation with a human-reviewable study-planning
service. It is a research and engineering candidate, not an approved automated
student decision system.

## Evidence tracks

| Track | Intended role | Evidence boundary |
|---|---|---|
| OULAD | Principal academic-risk benchmark and 30/60/90-day early-warning evaluation | Retrospective association only; not prospective or causal evidence |
| KU Leuven | Authorised external comparison and transfer stress-test evidence | Separate real-world dataset with a narrower shared feature contract |
| Synthetic Indian-university data | Planner, feature-contract, pipeline, and interface development | Simulated data only; never real-student validation or deployment evidence |
| EdNet | Complementary activity and content exploration | TOEIC-specific; not a replacement for the academic-risk target |

Outcome labels, final-course information, withdrawal dates, and post-cutoff
activity are forbidden from early-warning inputs. A feature available at day 60
or day 90 is not automatically valid at day 30.

## System flow

1. A student supplies understandable goals, tasks, availability, preferences,
   bounded academic context, and compulsory wellbeing context.
2. In an institutional deployment, governed LMS/SIS integrations supply
   enrolment, attendance, assessment, and engagement evidence.
3. The backend derives the fitted feature contract; students do not manually
   enter engineered columns.
4. An allowlisted model produces internal risk-support evidence.
5. The planner combines evidence, capacity, deadlines, preferences, and breaks
   into a reviewable schedule.
6. Monitoring records aggregate service and model behaviour without exposing
   student records.

## Implemented repository capabilities

- Reproducible OULAD cleaning, baseline comparison, and leakage-aware cutoff
  pipelines.
- Reproducible synthetic data generation, validation, and baseline modelling.
- KU Leuven external comparison and cross-dataset transfer diagnostics.
- Twelve executed and formally documented notebooks.
- MLflow/DagsHub experiment and candidate-registration support.
- DVC-managed data, model, metric, and validation lineage.
- A deterministic model-risk and quality assessment stage.
- FastAPI student and operator surfaces with production security controls.
- React/Vite student intake and separated administrator testing mode.
- Docker, Kubernetes, Prometheus, Grafana, CI/CD, monitoring, and rollback
  configuration.

## Current release posture

The canonical model-quality summary is
`artifacts/validation/model_quality/summary.json`. At the currently locked
revision, all three configured tracks pass structural integrity checks, but the
aggregate release decision is `blocked`.

The primary unresolved evidence requirements are institutionally approved
performance thresholds, an approved fairness policy, acceptable aggregate
fairness results, prospective institutional validation, a reviewed intervention
policy, and verified deployment eligibility. Synthetic evidence cannot satisfy
those requirements.

A registered candidate is not an approved production model. Production loading
requires an immutable numeric registry version and the repository's release,
fairness, feature-contract, and integrity gates.

## Canonical locations

- Generated models: `artifacts/models/`
- Generated metrics: `artifacts/metrics/`
- Validation evidence: `artifacts/validation/`
- Formal documentation: `docs/`
- Data and artifact lineage: `dvc.yaml` and `dvc.lock`
- Model-quality policy: `configs/model-quality.yaml`
- Deployment configuration: `deploy/`, `Dockerfile`, `docker-compose.yml`
- Monitoring configuration: `monitoring/`
- CI/CD workflows: `.github/workflows/`

Read the relevant formal document before changing a subsystem. In particular,
use `../docs/model-risk-quality.md`, `../docs/evaluation-and-release-policy.md`,
`../docs/deployment.md`, `../docs/security-hardening.md`, and
`../docs/production-readiness.md` for release-affecting work.
