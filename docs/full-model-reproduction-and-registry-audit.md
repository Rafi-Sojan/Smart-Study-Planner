# Full model reproduction and registry audit

This guide covers the all-tracks reproduction workflow added to the repository,
what it runs, what it checks, and what the results do and do not establish.

## What was added

The new workflow ties together the existing DVC, training, and MLflow tools:

1. `scripts/reproduce_all.ps1` runs the DVC synthetic-validation and formal
   model-quality stages.
2. It trains and registers the full-course OULAD baseline models, the selected
   OULAD early-warning models for days 30, 60, and 90, and synthetic comparison
   models for those same cutoffs.
3. `pipeline.audit_registry` checks that the MLflow versions created by those
   runs have the expected names, run links, and evidence tags.
4. Model registration now reads the saved tags back and verifies them before
   assigning the `candidate` alias. A mismatch raises an error.

This adds a repeatable way to produce and inspect model registrations. It does
not promote models or approve them for deployment.

## Before running

Use Windows PowerShell from a checkout with the required datasets available:

- processed OULAD data under `data/processed/oulad`;
- synthetic data under `data/raw/synthetic`; and
- MLflow tracking credentials set in the current PowerShell session.

Set these environment variables without writing credentials into the repo:

```powershell
$env:MLFLOW_TRACKING_URI = "<MLflow tracking URL>"
$env:MLFLOW_TRACKING_USERNAME = "<account name>"
$env:MLFLOW_TRACKING_PASSWORD = "<access token>"
```

The script stops if any of the three variables is missing. It also stops when
a DVC stage, training/registration command, or registry audit fails.

## Run the workflow

From the repository root:

```powershell
./scripts/reproduce_all.ps1
```

The script creates `.repro/` for its reports and temporary model files. That
directory is ignored by Git. The workflow uses separate MLflow experiment and
run names for the full-course OULAD, OULAD early-warning, and synthetic tracks,
so those runs can be found separately in MLflow.

## Expected registrations

| Track | Expected versions | What they represent |
|---|---:|---|
| OULAD full-course | 4 | One registered baseline for each of the four compared model families. |
| OULAD early warning | 3 | One selected candidate for each observation cutoff: day 30, 60, and 90. |
| Synthetic comparison | 12 | Four comparison models for each of the three cutoffs. These remain development-only. |

These are expected registration counts encoded by the audit, not a claim that a
particular run completed. Check the generated reports and MLflow run records
for actual results.

## What the registry audit checks

For each track, `pipeline.audit_registry` reads its JSON report and checks:

- the expected number of distinct registered model names;
- exactly one model version associated with the report's MLflow run;
- the required quality, fairness, selection, deployment, threshold,
  feature-contract, and evidence tags;
- valid true/false values for the gate tags;
- an operating threshold strictly between 0 and 1;
- a positive feature count; and
- a feature-contract digest in SHA-256 hexadecimal format.

The command prints a summary and exits with a non-zero status if a check fails.
This verifies registry metadata and links. It does not re-evaluate the model,
prove its performance on new students, or make it deployment-eligible.

## Registration safeguards

`src/tracking/model_registry.py` writes the requested tags to a newly
registered MLflow version, reads that version's tags back, and compares the
saved values with the requested ones. It assigns the `candidate` alias only
after the comparison succeeds. If MLflow did not save a requested tag as
expected, the code raises an error instead of silently marking that version as
the candidate.

The alias is a convenient pointer for candidate review. Since aliases can be
moved, deployment should use an immutable numeric model version and verify its
tags, threshold, and fitted feature contract.

## Evidence and release boundary

The workflow reproduces and registers research candidates. A successful audit
means the expected registration records and tags are present; it does not mean
that the quality gates passed or that deployment is approved. OULAD results are
retrospective benchmark evidence, and synthetic results are software and
planner-development evidence only. Production still requires prospective
institutional validation, an approved intervention policy and thresholds,
formal fairness approval, and the operational prerequisites in
[`production-readiness.md`](production-readiness.md).
