# Fairness evaluation and release gate

## Purpose

Fairness evaluation is performed on the locked test partition after model and
threshold selection. Protected and contextual attributes are retained for
auditing but are excluded from the default predictor matrix. The report is a
quantitative review aid; it is not proof that a model or intervention is fair.

OULAD audits `gender`, `age_band`, `imd_band`, `disability`, and `region` when
the fields are available. The synthetic track audits `category`, residence,
employment status, and study mode. Synthetic results test software behavior
only and cannot establish fairness for real students.

## Decision point and metrics

Fairness is evaluated at the operating threshold selected without using the
test labels. The intervention-policy threshold is used when reviewed capacity
or cost inputs configure one; otherwise the validation-F1 threshold is used.
The report records this threshold explicitly.

For every subgroup, `src/models/fairness.py` records:

- sample size and actual positive/negative counts;
- selection rate;
- true-positive rate, used for the equal-opportunity comparison;
- false-positive rate;
- precision and accuracy; and
- a two-sided Wilson score confidence interval for every defined rate.

The Wilson interval is preferred to an uncorrected normal interval because
subgroup denominators can be modest and observed rates can approach zero or
one. A zero denominator produces an undefined rate rather than an invented
zero.

## Minimum-group rule

The default comparison requires at least 30 observations, five positive
labels, and five negative labels in each group. Every group remains visible,
but a group below a minimum is marked ineligible and its exclusion reasons are
recorded. An attribute requires at least two eligible groups before a gap is
reported. Insufficient evidence is therefore distinguished from evidence of
no disparity.

For eligible groups, the report calculates the maximum pairwise difference in
true-positive rate, false-positive rate, and selection rate. The default
research review limit is 0.20 for each gap. This value is an engineering
default, not an institutionally approved tolerance. A production review must
set limits from legal, ethical, educational, and population-specific analysis.

## Automated gate

`pipeline.model_quality` supports the following controls:

```powershell
python -m pipeline.model_quality `
  --metrics artifacts/metrics/early_warning_metrics.json `
  --output artifacts/validation/fairness-quality.json `
  --require-fairness `
  --min-fairness-group-size 30 `
  --max-equal-opportunity-gap 0.20 `
  --max-false-positive-rate-gap 0.20 `
  --max-selection-rate-gap 0.20
```

The command fails when the selected model lacks a formal report, has no
evaluable attribute, uses a weaker minimum-group rule, or exceeds a supplied
gap. Pull-request CI tests the report calculations and gate behavior with
controlled unit fixtures; it does not claim an evaluable fairness result from
the deliberately small synthetic smoke dataset. The credentialed full-data
workflow enforces evaluability, while production deployment requires the
registered version's `fairness_gate_passed=true` tag and prospective deployment
eligibility.

## Interpretation boundary

Observed gaps can reflect sampling, measurement, label, access, or historical
inequity. They do not identify the cause. Passing a numerical gap does not
validate consent, accessibility, the support intervention, or downstream
impact. Unevaluable groups require additional representative data, and every
promotion requires a documented human fairness review.
