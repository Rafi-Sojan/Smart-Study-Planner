# FastAPI inference service specification

## 1. Service purpose

The FastAPI service provides a narrow research/deployment interface for
returning an enrollment risk score from a preloaded model. It is not an
automated academic, disciplinary, admissions, attendance, or financial-aid
decision service. A score must not be presented as a causal finding or as a
guarantee about a student's outcome.

The application is defined in `src/api/main.py`, with routes in
`src/api/routes.py` and request/response schemas in `src/api/schemas.py`.

## 2. Endpoint contract

| Method | Path | Purpose | Availability condition |
|---|---|---|---|
| GET | `/healthz` | Process liveness | Returns while the process is serving |
| GET | `/readyz` | Model readiness | Returns 200 only when a model is loaded |
| GET | `/metrics` | Prometheus metrics | Exposes request count and latency metrics |
| GET | `/v1/session` | Browser authentication state | Does not expose credentials or service keys |
| POST | `/v1/session` | Exchange an operator credential for an HttpOnly session | Requires configured browser authentication |
| POST | `/v1/session/logout` | Delete the browser session | Same-origin when a session is active |
| GET | `/v1/models` | List the deployment's allowlisted model options and default | Requires configured authentication |
| GET | `/v1/model-metadata` | Resolved version, threshold, and fitted feature contract | Requires a loaded model and configured authentication |
| POST | `/v1/risk-score` | Score one feature dictionary | Requires a loaded model and configured authentication |
| POST | `/v1/study-plan` | Score risk and generate a reviewable task schedule | Requires the risk endpoint controls plus valid tasks and availability |
| POST | `/v1/student-study-plan` | Derive the default model contract from a small student intake and generate a plan | Requires configured authentication; does not accept raw model fields or a model ID |

Example request shape:

```json
{
  "model_id": "oulad-day-30",
  "features": {
    "total_clicks": 12,
    "assessment_mean": 64.5
  }
}
```

`model_id` is optional for backward compatibility; omission selects the
deployment default. When supplied, it must match an entry returned by
`GET /v1/models`. Paths, registry URIs, aliases, thresholds, and arbitrary
model names are never accepted from a scoring request.

The request contains a non-empty mapping of scalar strings, integers, floats,
booleans, or nulls. Nested values, non-finite numbers, invalid names,
identifiers, labels, and post-outcome fields are rejected. Supplied names must
exactly equal the fitted model's ordered raw feature contract; missing and
unexpected names return 422 rather than being silently imputed or discarded.

Example response shape:

```json
{
  "model_id": "oulad-day-30",
  "risk_score": 0.42,
  "threshold": 0.50,
  "alert": false,
  "model_version": "registered-name/7",
  "feature_contract_sha256": "<64-character digest>",
  "threshold_source": "mlflow_registry_tag"
}
```

The values above describe the response schema only; they are not measured
project results.

### Student-facing plan contract

`POST /v1/student-study-plan` is the normal browser path. Its request contains:

- a structured goal and one or more subject names;
- course style and current term;
- optional self-reported CGPA, recent score, attendance, submission rate,
  weekly study time, credit load, and confidence;
- optional numeric sleep, stress, fatigue, and concentration context;
- structured tasks and deadlines;
- availability windows; and
- preferred study-session and break lengths.

The endpoint always uses the configured default approved model. The server
builds every fitted input in contract order, maps only meaning-compatible
student values, and supplies `null` for unavailable institutional fields. It
does not infer or fabricate LMS clicks, verified attendance events, assessment
events, registration dates, or outcomes. The model's fitted imputation pipeline
handles unavailable values.

The student response returns a support level, task priorities, scheduled
sessions, unscheduled minutes, recommendations, and an evidence summary. It
does not return the numerical risk score, threshold, model identifier, model
version, registry URI, fitted column names, or feature-contract digest. The
evidence summary identifies the standalone path as `self_reported_demo`, states
that institutional data is not connected, and records whether evidence coverage
is limited or partial. This boundary prevents a demonstration estimate from
being presented as an institutionally verified early-warning score.

## 3. Status semantics

- `200`: request completed successfully;
- `401`: neither a valid service API key nor a valid browser session was supplied;
- `403`: a cookie-authenticated mutation failed the same-origin check;
- `422`: request schema validation failed;
- `503`: no trusted model is loaded; and
- `500`: an unexpected server error occurred.

The readiness endpoint must be used by orchestration platforms. A live process
without a loaded model is healthy enough to report diagnostics but is not ready
to serve predictions.

## 4. Model loading and integrity controls

The service supports two mutually exclusive loading paths:

1. `MODEL_URI=models:/...`, loaded through MLflow; or
2. `MODEL_PATH=...`, loaded as a pickle only when explicit trust is enabled.

For local pickle artifacts, `MODEL_SHA256` provides an integrity check. Pickle
is executable serialization, so the artifact source and checksum must be
independently verified. Registry credentials and model artifacts are supplied
at runtime and are not baked into the container image. Production accepts only
an immutable numeric registered-model URI and validates its release tags,
threshold, and fitted feature digest before readiness can succeed.
Startup also refuses a model whose fitted contract contains an identifier,
outcome, or post-outcome field forbidden by the inference payload policy. This
prevents deployment of an artifact that can load but can never accept a valid
request.

## 5. Authentication and privacy

Machine clients authenticate with `X-API-Key`. Browser users authenticate with
the configured operator credential and receive a signed, time-limited,
HttpOnly, SameSite=Strict cookie. Production cookies are Secure and
cookie-authenticated POST requests require an HTTPS same-origin `Origin`
header. The service API key is never returned to or compiled into the browser.
This single-operator mechanism does not replace institutional SSO, role-based
authorization, account lifecycle controls, or a reviewed audit policy.

Requests must not contain student names, raw identifiers, free-text wellbeing
records, credentials, diagnoses, or unnecessary sensitive attributes. The
student schema accepts bounded numeric wellbeing context only. The service
metrics expose aggregate request counts and latency, not request payloads.

## 6. Configuration

| Variable | Required | Meaning |
|---|---:|---|
| `APP_ENV` | Production | `production` activates strict registry, secret, and host checks |
| `MODEL_URI` | Conditional | MLflow `models:/` URI; production requires a numeric version |
| `MODEL_PATH` | Conditional | Trusted local model path |
| `ALLOW_TRUSTED_PICKLE_MODEL` | For pickle | Must be `1` for local pickle loading |
| `MODEL_SHA256` | Recommended for pickle | Expected SHA-256 digest |
| `MODEL_THRESHOLD` | Production | Must match the registered version's approved threshold tag |
| `MODEL_VERSION` | No | Version label returned by the API |
| `MODEL_CATALOG_JSON` | No | Bounded allowlist of 1–12 selectable models; mutually exclusive with `MODEL_URI` and `MODEL_PATH` |
| `DEFAULT_MODEL_ID` | Catalog mode | Recommended model returned when requests omit `model_id` |
| `MODEL_LABEL` | No | User-facing label for legacy single-model mode |
| `MODEL_DESCRIPTION` | No | User-facing explanation for legacy single-model mode |
| `MODEL_DATASET` | No | Dataset label for legacy single-model mode |
| `MODEL_CUTOFF_DAYS` | No | Positive observation cutoff for legacy single-model mode |
| `API_KEY` | Recommended | Expected `X-API-Key` value |
| `ALLOWED_HOSTS` | Production | Comma-separated trusted HTTP hostnames |
| `CORS_ALLOWED_ORIGINS` | No | Explicit development origins; wildcard is forbidden in production |
| `WEB_AUTH_USERNAME` | Production | Human operator login name |
| `WEB_AUTH_PASSWORD_HASH` | Production | PBKDF2 verifier generated by `python -m src.api.auth` |
| `SESSION_SECRET` | Production | Random signing value of at least 32 characters |
| `SESSION_TTL_SECONDS` | No | Session lifetime from 300 to 86400 seconds; default 28800 |
| `SESSION_COOKIE_SECURE` | No | Forces Secure cookies outside production when set to `1` |
| `ENABLE_API_DOCS` | No | Enables `/docs` only when set to `1` |

The 0.5 fallback exists only for local development without a registry model.
A registered model must supply its validation-selected operating threshold;
production additionally requires the deployment value to match it exactly.
Threshold approval still requires capacity, error-cost, calibration, and
human-support review.

The study-planner calculation and safety boundary are specified in
`docs/planner-service.md`.

## 7. Observability

Prometheus records aggregate HTTP request counts by method, path, and status,
and request-duration histograms. Grafana can visualize these metrics through
the Compose monitoring stack. Operational monitoring does not establish model
validity; model quality, calibration, subgroup outcomes, and intervention
effects require separate evaluation reports.
