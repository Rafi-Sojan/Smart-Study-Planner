# Pipeline-specific agent guide

This file applies to `pipeline/` in addition to the repository-level guide.

## Reproducibility

Pipeline defaults and DVC stage commands must write generated outputs only to
the canonical `artifacts/` tree. Keep defaults, `dvc.yaml`, `dvc.lock`, workflow
paths, documentation, notebooks, Compose mounts, and tests aligned.

Use deterministic seeds and the documented grouped/student-disjoint splits.
Select models and operating thresholds with training/validation evidence only;
report locked-test metrics only after selection. For early-warning stages, apply
the cutoff before feature aggregation and exclude post-cutoff information.

The baseline comparison intentionally includes logistic regression, random
forest, extra trees, and histogram gradient boosting so linear, bagged-tree,
randomised-tree, and boosted-tree behaviours are compared under one contract.
Do not silently replace or add a model without updating rationale, tests,
metrics schema, documentation, and notebooks.

## Tracking and registration

Local pipeline execution must not contact DagsHub unless `--mlflow` or
`--register-models` is explicitly supplied. Registration records a candidate;
it does not promote or approve it. Never invent run IDs or model versions when
tracking is unavailable.

Use `dvc repro <stage>` when producing new evidence. Use `dvc commit --force`
only for a verified byte-preserving relocation. Run `dvc status` afterward and
state separately whether `dvc push` was performed.

For model-path changes, verify loading and prediction with:

```powershell
.\.venv\Scripts\python.exe -m pipeline.api_smoke `
  --data-dir data/raw/synthetic `
  --metrics artifacts/metrics/synthetic_baseline_metrics.json `
  --model-dir artifacts/models/synthetic_baseline `
  --cutoff 30
```

