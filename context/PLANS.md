# Smart Study Planner plans

This file records active and future work. It is not evidence that an operation
has occurred and does not authorise deployment, registration, pushing, or other
external side effects. Verify repository and external state before changing any
status.

## Status vocabulary

- `[x]` — completed and supported by repository or executed-command evidence.
- `[ ]` — not completed or not yet verified.
- `blocked` — requires institutional approval, external infrastructure, or new
  authorised evidence.

## Current completed foundation

- [x] Reproducible OULAD, synthetic, KU Leuven, and transfer-analysis pipelines.
- [x] Leakage-aware OULAD day 30, 60, and 90 evaluation.
- [x] Four-model baseline comparisons and stored confusion-matrix evidence.
- [x] DVC-managed canonical model, metric, and validation artifacts.
- [x] MLflow/DagsHub tracking and candidate-registration paths.
- [x] Student-facing FastAPI and React/Vite planning workflow.
- [x] Docker, Kubernetes, Prometheus, Grafana, CI/CD, and rollback definitions.
- [x] Deterministic three-track model-risk and quality assessment.
- [x] Consolidated repository context and agent guidance.

## Immediate repository handoff

- [ ] Review the current model-quality and context changes.
- [ ] Commit the accepted source, documentation, workflow, test, `dvc.yaml`, and
  `dvc.lock` changes.
- [ ] Push DVC artifacts only when the matching lockfile is accepted and remote
  credentials are available.
- [ ] Push the matching Git commit and allow GitHub Actions to run.
- [ ] Preserve the unrelated `deliverables/` directory unless the user gives a
  separate instruction for it.

These steps remain unchecked until the exact operations succeed.

## Production-readiness plan

### Phase 1 — Institutional governance (`blocked`)

- [ ] Approve task-specific minimum PR-AUC, balanced-accuracy, operating-recall,
  and maximum calibration-error thresholds.
- [ ] Approve fairness attributes, minimum group sizes, uncertainty rules, and
  allowable opportunity, false-positive-rate, and selection-rate gaps.
- [ ] Approve advisor capacity, false-positive/false-negative costs, support
  actions, notification, appeal, consent, retention, and access procedures.

### Phase 2 — Prospective evidence (`blocked`)

- [ ] Establish a governed LMS/SIS data contract and prediction horizon.
- [ ] Validate temporal availability, missingness, labels, calibration, and
  subgroup behaviour on representative prospective institutional data.
- [ ] Run a supervised pilot and measure intervention outcomes and unintended
  harms; do not treat prediction accuracy as intervention effectiveness.

### Phase 3 — Candidate promotion (`blocked`)

- [ ] Reproduce affected DVC stages with the approved policy and authorised data.
- [ ] Run the strict model-quality promotion gate.
- [ ] Register the exact candidate with immutable lineage and complete evidence
  tags.
- [ ] Complete human review and promote only the approved numeric model version.

### Phase 4 — Infrastructure release (`blocked`)

- [ ] Provision the institution-controlled cluster, DNS, TLS, network policy,
  protected environments, secret stores, and least-privilege credentials.
- [ ] Build and publish immutable full-commit container images through CI.
- [ ] Validate backup, restore, rollback, readiness, authentication, rate limits,
  and audit retention in a non-production environment.

### Phase 5 — Monitored operation (`blocked`)

- [ ] Assign incident and model owners and configure external alert delivery.
- [ ] Monitor service health, drift, calibration, subgroup outcomes, alert
  capacity, and intervention harms.
- [ ] Define retraining, recalibration, rollback, and retirement triggers with
  human approval.

## Plan template for future work

Copy this section when adding a substantial plan:

```markdown
## Objective

State the concrete outcome and evidence boundary.

### Scope

- In scope:
- Out of scope:

### Tasks

- [ ] Implementation task
- [ ] Test task
- [ ] Documentation and lineage task

### Validation

- Command:
- Expected evidence:

### Handoff

- Files changed:
- Measured results:
- Warnings:
- Remaining work:
```
