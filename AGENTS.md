# Smart Study Planner agent guide

## Project purpose

This repository implements a leakage-aware academic-risk and study-planning
demonstrator. OULAD supplies the principal academic-risk benchmark, the
authorised KU Leuven release supplies external comparison evidence, and the
synthetic Indian-university dataset supports planner development only. Do not
present synthetic results as real-student validation or deployment evidence.

## Repository map

- `src/`: data, feature, model, risk, monitoring, planner, and FastAPI code.
- `frontend/`: React and Vite student/operator interface.
- `pipeline/`: reproducible training, validation, inference-smoke, and release utilities.
- `notebooks/`: executed, formally documented analyses numbered `01` through `12`.
- `data/`: DVC-managed raw, processed, synthetic, and external data.
- `artifacts/`: the only canonical local destination for generated ML outputs.
- `docs/`: formal technical, governance, deployment, and model-risk documentation.
- `deploy/`, `monitoring/`, and `.github/workflows/`: operational configuration.

## Non-negotiable rules

1. Inspect `git status` and existing code before editing. Preserve unrelated and
   untracked user work, including `deliverables/`.
2. Never fabricate datasets, metrics, run IDs, registry versions, test results,
   or notebook outputs. Report only values produced by an executed command or
   already stored evidence.
3. Keep outcome labels, final-course information, withdrawal dates, and future
   activity out of early-warning features. Day 30, 60, and 90 features may use
   only evidence available by the corresponding cutoff.
4. Student-facing forms request understandable information, not engineered model
   columns. Institutional/LMS features are loaded or derived by the backend.
5. Sleep hours, stress, fatigue, and concentration are compulsory in the
   standalone student intake. They remain self-reported, non-clinical context
   subject to privacy, purpose, retention, and access controls.
6. A registered model is not automatically approved for deployment. Preserve
   quality gates, human review, model cards, fairness evidence, and immutable
   production registry references.
7. Never commit credentials. DagsHub tokens, API keys, session secrets, and
   deployment credentials belong in environment variables or secret stores.

## Artifact and versioning contract

Generated files belong under:

- `artifacts/models/` for fitted estimators;
- `artifacts/metrics/` for evaluation and transfer metrics;
- `artifacts/validation/` for data-quality and statistical evidence.

The generated contents are ignored by Git and versioned by DVC through
`dvc.yaml` and `dvc.lock`. Model implementation code remains under `src/models/`.
MLflow/DagsHub tracks experiments and registered candidates; it does not replace
DVC's local data/artifact lineage.

When only artifact locations change and bytes are verified unchanged, a forced
DVC commit may record the relocation. If code, data, features, splits, model
parameters, or evaluation logic changes, reproduce the affected stages instead.
Do not hand-edit hashes or measured values in `dvc.lock` or JSON reports.

On restricted Windows sessions, use a writable DVC site cache before DVC commands:

```powershell
$env:DVC_SITE_CACHE_DIR = Join-Path $env:TEMP "smart-study-planner-dvc-site-cache"
```

## Required validation

Run checks in proportion to the change. Before handing off a repository-wide
change, use:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests pipeline
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pipeline.validate_notebooks notebooks
.\.venv\Scripts\dvc.exe status
```

For frontend changes:

```powershell
Set-Location frontend
npm run check
npm test -- --run
npm run build
```

For model-path changes, run `pipeline.api_smoke` against a real stored artifact.
Validate Docker Compose when Docker is available; otherwise state that it was not
executed and rely only on explicit YAML/unit checks.

## Documentation and handoff

Update code, tests, DVC definitions, workflows, notebooks, and formal docs
together whenever a contract or canonical path changes. Report files changed,
commands run, measured outcomes, warnings, and remaining work. Do not claim a
Git commit, DVC push, MLflow run, registration, image build, or deployment unless
that exact operation completed successfully.

