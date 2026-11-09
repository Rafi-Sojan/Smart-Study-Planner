# API-specific agent guide

This file applies to `src/api/` in addition to the repository-level guide.

## Public contracts

- `/v1/student-study-plan` is the student-facing endpoint. It accepts goals,
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

## Model loading and security

Development may load explicitly trusted local artifacts from
`artifacts/models/` when `ALLOW_TRUSTED_PICKLE_MODEL=1`. Production must reject
local pickle paths and use immutable numeric MLflow registered-model versions
that pass registry-tag and release-gate verification.

Keep model selection allowlisted through the model catalog. Preserve host,
CORS, authentication, session, rate-limit, payload-size, model-integrity, and
readiness controls. Never weaken production checks to simplify a local demo.

## Validation

Update `tests/integration/test_api.py` and relevant unit tests whenever request,
response, authentication, model catalog, or validation behaviour changes. Run a
real-artifact API smoke test after changing model locations or loading logic.

