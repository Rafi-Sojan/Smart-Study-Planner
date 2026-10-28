# Model-risk and model-quality control specification

## 1. Purpose

This document defines the minimum quality, evidence, and governance checks
applied before a Smart Study Planner model is treated as a registered
candidate. It distinguishes numerical integrity from deployment suitability.
Passing a quality check means that the stored evaluation report is internally
consistent. It does not mean that the model is accurate for a new institution,
calibrated for student-facing use, fair across groups, or approved for
automated intervention.

The executable implementation is
`src/risk/model_risk.py`, with the command-line entry point
`python -m pipeline.model_quality`. The same checks support full-course OULAD
reports and nested cutoff reports such as the 30-, 60-, and 90-day studies.

## 2. Evidence classification

Every report is interpreted according to its evidence type:

| Evidence type | Permitted interpretation | Prohibited interpretation |
|---|---|---|
| `retrospective_historical_benchmark` | Historical research benchmark | Evidence of prospective intervention benefit |
| `synthetic_development_only` | Software, schema, and experiment development | Evidence of real student performance or fairness |
| `prospective_institutional_validation` | Candidate evidence for an approved validation setting | Automatic approval for broader deployment |

The report also contains a `deployment_claim`. A registered model retains its
evidence restriction; registration is an artifact-management action, not an
approval decision.

## 3. Structural checks

For a full-course report, the following top-level fields are required:

`best_model`, `models`, `n_samples`, `n_train`, `n_test`, and `target`.

The selected model must contain:

`accuracy`, `balanced_accuracy`, `f1`, `precision`, `recall`, `roc_auc`,
`pr_auc`, `brier_score`, and a two-by-two `confusion_matrix`.

The validator additionally checks that:

1. all required metrics are finite numbers;
2. rate metrics lie between 0 and 1;
3. the Brier score lies between 0 and 1;
4. calibration error, when present, lies between 0 and 1;
5. confusion-matrix entries are non-negative integers and the matrix contains
   at least one observation; and
6. training, test, and total sample counts are positive integers.

For nested cutoff reports, the validator applies the same contract separately
to every evaluation. The overall report passes only when every cutoff passes.
This prevents a valid-looking aggregate report from hiding a malformed or
failed cutoff.

## 4. Optional release thresholds

The validator accepts explicit thresholds for a particular task:

```powershell
python -m pipeline.model_quality `
  --metrics models/metrics/metrics.json `
  --output models/metrics/model_quality.json `
  --min-pr-auc 0.20 `
  --min-balanced-accuracy 0.60 `
  --max-expected-calibration-error 0.10
```

These values are examples of configuration syntax, not project results or
approved thresholds. Thresholds must be set from the intended support
capacity, error costs, prevalence, calibration requirements, and institutional
review. A universal threshold would be inappropriate across OULAD, synthetic,
and future institutional data.

The command exits with a non-zero status when a structural check or supplied
threshold fails. CI uses the same mechanism on the synthetic smoke report.

## 5. Deployment eligibility

`passed: true` and `deployment_eligible: true` are intentionally different.
Deployment eligibility requires all structural checks to pass and all of the
following evidence fields:

- `evidence_type: prospective_institutional_validation`;
- `deployment_claim: prospective_validated`; and
- a selected model whose `intervention_policy.status` is `configured`.

The current OULAD retrospective and synthetic development tracks therefore
remain ineligible by design. This is a safety control, not a statement that
the models are numerically unusable for research.

## 6. Required review before promotion

Before an artifact can move beyond candidate status, reviewers must confirm:

1. the final test partition was not used for model or threshold selection;
2. data, code, environment, and model provenance are recorded;
3. calibration was assessed on representative, time-respecting data;
4. subgroup performance includes minimum-group and uncertainty rules;
5. an intervention policy specifies capacity, error costs, human review,
   notification, and appeal procedures;
6. privacy, consent, retention, access, and deletion requirements are met; and
7. monitoring, rollback, and incident ownership are defined.

These controls are further described in `docs/risk-register.md` and
`docs/evaluation-and-release-policy.md`.

## 7. Limitations

The quality validator cannot detect every form of leakage, sampling bias,
label error, distribution shift, unfair impact, or harmful intervention. It
checks the supplied report and cannot substitute for data governance,
independent review, or prospective validation.
