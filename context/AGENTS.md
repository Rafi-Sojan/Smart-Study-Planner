# Smart Study Planner unified agent guide

This is the single authoritative operating guide for the repository. It merges
the former repository, API, pipeline, notebook, and frontend `AGENTS.md` files.
The root `AGENTS.md` exists only as a discovery pointer to this file. Read this
guide completely before changing the project.

## 1. Project purpose and evidence boundary

This repository implements a leakage-aware academic-risk and study-planning
demonstrator. OULAD supplies the principal academic-risk benchmark, the
authorised KU Leuven release supplies external comparison evidence, and the
synthetic Indian-university dataset supports planner development only. EdNet is
a complementary TOEIC activity-analysis dataset. Do not present synthetic
results as real-student validation or deployment evidence, and do not infer
causality from retrospective associations.

## 2. Repository map

- `src/`: data, feature, model, risk, monitoring, planner, and FastAPI code.
- `src/api/`: student, operator, authentication, model-loading, and planner API
  contracts.
- `frontend/`: React and Vite student/operator interface.
- `pipeline/`: reproducible training, validation, inference-smoke, model-quality,
  and release utilities.
- `notebooks/`: executed, formally documented analyses numbered `01` through
  `12`.
- `data/`: DVC-managed raw, processed, synthetic, and external data.
- `artifacts/`: the only canonical local destination for generated ML outputs.
- `configs/`: simulation, monitoring, and model-quality policies.
- `docs/`: formal technical, governance, deployment, and model-risk
  documentation.
- `deploy/`, `monitoring/`, and `.github/workflows/`: operational configuration.
- `context/`: consolidated agent guidance, project context, plans, and durable
  decisions.

## 3. Non-negotiable repository rules

1. Inspect `git status` and existing code before editing. Preserve unrelated and
   untracked user work, including `deliverables/`.
2. Continue from the current implementation; do not recreate working components
   or overwrite unrelated changes.
3. Never fabricate datasets, metrics, run IDs, registry versions, test results,
   notebook outputs, deployment state, or external validation evidence. Report
   only values produced by an executed command or already stored evidence.
4. Keep outcome labels, final-course information, withdrawal dates, and future
   activity out of early-warning features. Day 30, 60, and 90 features may use
   only evidence available by the corresponding cutoff.
5. Student-facing forms request understandable information, not engineered model
   columns. Institutional/LMS features are loaded or derived by the backend.
6. Sleep hours, stress, fatigue, and concentration are compulsory in the
   standalone student intake. They remain self-reported, non-clinical context
   subject to privacy, purpose, retention, and access controls.
7. A registered model is not automatically approved for deployment. Preserve
   quality gates, human review, model cards, fairness evidence, and immutable
   production registry references.
8. Never commit credentials. DagsHub tokens, API keys, session secrets, and
   deployment credentials belong in environment variables or secret stores.
9. Treat a completed but blocked quality assessment as valid evidence. Never
   weaken thresholds, alter measured reports, or relabel evidence to obtain a
   passing result.

## 4. Artifact, data, and versioning contract

Generated files belong under:

- `artifacts/models/` for fitted estimators;
- `artifacts/metrics/` for evaluation and transfer metrics; and
- `artifacts/validation/` for data-quality, statistical, and model-quality
  evidence.

The generated contents are ignored by Git and versioned by DVC through
`dvc.yaml` and `dvc.lock`. Model implementation code remains under `src/models/`.
MLflow/DagsHub tracks experiments and registered candidates; it does not replace
DVC data and artifact lineage.

When only artifact locations change and bytes are verified unchanged, a forced
DVC commit may record the relocation. If code, data, features, splits, model
parameters, or evaluation logic changes, reproduce the affected stages instead.
Do not hand-edit hashes or measured values in `dvc.lock` or JSON reports.

On restricted Windows sessions, use a writable DVC site cache before DVC
commands:

```powershell
$env:DVC_SITE_CACHE_DIR = Join-Path $env:TEMP "smart-study-planner-dvc-site-cache"
```

## 5. Pipeline and model-development rules

Pipeline defaults and DVC stage commands must write generated outputs only to
the canonical `artifacts/` tree. Keep defaults, `dvc.yaml`, `dvc.lock`, workflow
paths, documentation, notebooks, Compose mounts, and tests aligned.

Use deterministic seeds and documented grouped or student-disjoint splits.
Select models and operating thresholds using training/validation evidence only;
report locked-test metrics only after selection. For early-warning stages, apply
the cutoff before feature aggregation and exclude post-cutoff information.

The baseline comparison intentionally includes logistic regression, random
forest, extra trees, and histogram gradient boosting so linear, bagged-tree,
randomised-tree, and boosted-tree behaviours are compared under one contract.
Do not silently replace or add a model without updating the rationale, tests,
metrics schema, documentation, and notebooks.

Local pipeline execution must not contact DagsHub unless `--mlflow` or
`--register-models` is explicitly supplied. Registration records a candidate;
it does not promote or approve it. Never invent run IDs or model versions when
tracking is unavailable.

Use `dvc repro <stage>` when producing new evidence. Use `dvc commit --force`
only for a verified byte-preserving relocation. Run `dvc status` afterward and
state separately whether `dvc push` was performed.

Formal release assessments are generated by `dvc repro model_quality` from
`configs/model-quality.yaml` and stored under
`artifacts/validation/model_quality/`. A completed assessment may be blocked;
never edit its decision or choose thresholds merely to obtain a pass.

For model-path changes, verify loading and prediction with a real stored
artifact:

```powershell
.\.venv\Scripts\python.exe -m pipeline.api_smoke `
  --data-dir data/raw/synthetic `
  --metrics artifacts/metrics/synthetic_baseline_metrics.json `
  --model-dir artifacts/models/synthetic_baseline `
  --cutoff 30
```

## 6. API contract and security rules

`/v1/student-study-plan` is the student-facing endpoint. It accepts goals,
subjects, tasks, availability, planning preferences, bounded academic context,
and compulsory wellbeing context.

- `sleep_hours` is required and bounded to `0..24`.
- `stress_level`, `fatigue_level`, and `concentration_level` are required and
  bounded to `0..10`.
- Missing required wellbeing fields must produce FastAPI/Pydantic HTTP `422`.
- Student responses must explain evidence quality and support level without
  exposing internal feature hashes, raw model contracts, or registry internals.
- `/v1/risk-score` and raw feature entry are operator/integration surfaces, not
  the normal student experience.

Development may load explicitly trusted local artifacts from
`artifacts/models/` when `ALLOW_TRUSTED_PICKLE_MODEL=1`. Production must reject
local pickle paths and use immutable numeric MLflow registered-model versions
that pass registry-tag and release-gate verification.

Keep model selection allowlisted through the model catalog. Preserve host,
CORS, authentication, session, rate-limit, payload-size, model-integrity, and
readiness controls. Never weaken production checks to simplify a local demo.

Update `tests/integration/test_api.py` and relevant unit tests whenever request,
response, authentication, model catalog, or validation behaviour changes. Run a
real-artifact API smoke test after changing model locations or loading logic.

## 7. Frontend and student-experience rules

The default interface is a student-friendly intake and planner. Do not expose
the model's engineered feature vector, registry URI, feature hash, or raw model
metadata to students. Raw feature entry and detailed model diagnostics belong in
an explicitly separated administrator/model-testing mode.

Student input includes goals, subjects, tasks, deadlines, availability, session
length, break preferences, and academic context. Sleep, stress, fatigue, and
concentration are compulsory and must be visibly labelled as required. Frontend
validation is usability support; the API remains the authoritative validator.

Display risk output as reviewed support guidance rather than a deterministic or
clinical judgement. Preserve evidence-quality explanations, human-review
language, accessible labels, keyboard operation, responsive layout, and clear
loading/error states.

Keep API payload types in `frontend/src/types.ts`, request logic in
`frontend/src/api.ts`, and behavioural coverage in Vitest. Required fields must
be represented in both TypeScript types and rendered HTML validation. Do not
leave the Vite development server running unless the user asks for it.

## 8. Notebook rules

Preserve the numbered `01` through `12` sequence and existing subject split.
Notebooks must contain formal explanations inside the notebook, not only links
to external documentation. Explain the purpose of each cleaning, processing,
feature, statistical, and modelling step; define important statistics;
interpret every material plot; and connect conclusions to the Smart Study
Planner.

Use colourful but accessible visualisations with titles, units, legends, and
explicit sample sizes where relevant. Baseline evaluation notebooks must include
model comparisons and confusion matrices. Early-warning analysis must explain
why day 30, 60, and 90 cutoffs prevent future-information leakage and preserve
intervention time.

Do not fabricate output cells. Execute notebooks against available versioned
data and save outputs in the notebook. If required data is unavailable, leave a
clear reproducibility instruction rather than constructing substitute results.
Generated JSON evidence must use `artifacts/metrics/` or
`artifacts/validation/`; model binaries use `artifacts/models/`.

Keep synthetic findings explicitly labelled as development evidence and retain
the limitations of OULAD and KU Leuven comparisons. Do not infer causality from
association plots or claim real-world validity for unobserved synthetic fields.
When execution is required, use the repository notebook execution utility and
confirm that stored outputs correspond to the executed code and current artifact
paths.

## 9. Required validation

Run checks in proportion to the change. Before handing off a repository-wide
change, use:

```powershell
.\.venv\Scripts\python.exe -m ruff check src tests pipeline
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m pipeline.validate_notebooks notebooks
.\.venv\Scripts\dvc.exe status
```

For frontend changes, run from `frontend/`:

```powershell
npm run check
npm test -- --run
npm run build
```

For model-path changes, run `pipeline.api_smoke` against a real stored artifact.
Validate Docker Compose when Docker is available; otherwise state that it was
not executed and rely only on explicit YAML/unit checks.

## 10. Documentation, plans, and handoff

Update code, tests, DVC definitions, workflows, notebooks, formal docs, and the
relevant `context/` files together whenever a contract, evidence boundary, or
canonical path changes. Use `context/PLANS.md` for active and future work and
`context/DECISIONS.md` for durable architectural or governance decisions.

Report files changed, commands run, measured outcomes, warnings, and remaining
work. Do not claim a Git commit, DVC push, MLflow run, model registration, image
build, or deployment unless that exact operation completed successfully.
