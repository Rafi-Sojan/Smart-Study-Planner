# Evaluation, intervention, validity, and release policy

## Status of the evidence

The repository contains two evidence tracks with different meanings:

1. OULAD is a retrospective, de-identified historical benchmark. Its labels
   are final course outcomes, so even the time-aware 30-, 60-, and 90-day
   evaluations measure predictive association with a later observed outcome.
   They do not establish that an alert would change that outcome.
2. The Indian-university dataset is generated data. Integrity checks can show
   that the generated tables are reproducible and relationally consistent,
   but they cannot establish population validity or representativeness.

Every metrics artifact records an `evidence_type` and a deployment-claim
restriction. These fields are part of the reporting contract and must not be
removed when a model is registered.

## Probability calibration

The evaluation code records the Brier score and a ten-bin reliability summary.
For each populated probability bin it reports the mean predicted probability,
the observed positive rate, the number of observations, and the absolute gap.
The expected calibration error (ECE) is the observation-weighted mean of those
absolute gaps. Lower Brier score and lower ECE indicate better agreement
between scores and observed frequencies, but neither metric proves future
calibration under distribution shift.

Calibration is descriptive until it has been checked on a representative,
time-respecting validation sample. A model score must not be shown to a
student or advisor as a literal probability until a calibration method and
recalibration schedule have been reviewed. The current baseline reports
calibration diagnostics; it does not claim calibrated production probabilities.

## Intervention threshold policy

The default 0.5 threshold is a technical diagnostic, not a support policy.
The reusable policy function accepts either:

- a reviewed maximum alert rate, representing advisor or support capacity; or
- reviewed relative false-negative and false-positive costs.

The selected policy threshold is computed on validation predictions only. The
locked test partition is then evaluated at that threshold without using it for
selection. If neither capacity nor costs are supplied, the artifact marks the
policy as `not_configured` and does not present an intervention threshold as
approved.

Example:

```powershell
python -m pipeline.early_warning_pipeline `
  --data-dir data/processed/oulad `
  --max-alert-rate 0.20 `
  --cutoffs-days 30 60 90
```

The capacity value and error costs must come from an institutional review of
available support resources, the harm of missed risk, the burden of
unnecessary alerts, and a human appeal process. F1 optimisation remains a
comparison diagnostic and is not a substitute for that review.

## Synthetic-data validity

Run the integrity report with:

```powershell
python -m src.data.synthetic_validation `
  --data-dir data/raw/synthetic `
  --output models/validation/synthetic_data_validation.json
```

The report checks manifest row counts, primary-key uniqueness, and selected
foreign-key relationships without copying row-level records into the report.
It explicitly records `external_validity: not_assessed`. The report therefore
supports software-quality and relational-integrity claims only. It cannot be
used to claim that the simulated distributions match Indian universities.
Validation against authorised aggregate institutional statistics or consented,
de-identified observations is a future evidence requirement and must not be
fabricated.

## Retrospective OULAD release gate

OULAD results may be used for research benchmarking and pipeline testing. They
must not be used alone to automate academic, disciplinary, admissions,
financial-aid, or attendance decisions. Before an intervention deployment,
the project requires:

- prospective validation with a defined prediction horizon;
- calibration and threshold review on representative data;
- subgroup fairness analysis with uncertainty and minimum-group rules;
- an approved human support, notice, and appeal process; and
- measurement of intervention outcomes, including unintended harms.

## Git, DVC, and release state

DVC data and artifacts can be uploaded before the Git commit, but a release is
not reproducible until the matching source, `dvc.yaml`, and `dvc.lock` changes
are committed and pushed to Git. The release sequence is:

```powershell
python -m pytest -q
ruff check src pipeline tests
dvc status
dvc push
git add .
git commit -m "feat: harden evaluation and MLOps pipelines"
git push
```

The final Git commit hash must be retained in the metrics provenance and in
the MLflow run. GitHub Actions remains the authoritative CI gate; DVC remote
storage alone is not a source-code release.
