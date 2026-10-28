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
| POST | `/v1/risk-score` | Score one feature dictionary | Requires a loaded model and, when configured, a valid API key |

Example request shape:

```json
{
  "features": {
    "total_clicks": 12,
    "assessment_mean": 64.5
  }
}
```

The request contains a non-empty feature mapping with no undeclared top-level
fields. Identifiers and raw file paths are not accepted as separate request
fields. The feature names and preprocessing contract must match the selected
model; schema validation cannot guarantee semantic compatibility.

Example response shape:

```json
{
  "risk_score": 0.42,
  "threshold": 0.50,
  "alert": false,
  "model_version": "candidate"
}
```

The values above describe the response schema only; they are not measured
project results.

## 3. Status semantics

- `200`: request completed successfully;
- `401`: `API_KEY` is configured and the `X-API-Key` header is invalid or
  missing;
- `422`: request schema validation failed;
- `503`: no trusted model is loaded; and
- `500`: an unexpected server error occurred.

The readiness endpoint must be used by orchestration platforms. A live process
without a loaded model is healthy enough to report diagnostics but is not ready
to serve predictions.

## 4. Model loading and integrity controls

The service supports two mutually exclusive loading paths:

1. `MODEL_URI=models:/...` or `runs:/...`, loaded through MLflow; or
2. `MODEL_PATH=...`, loaded as a pickle only when explicit trust is enabled.

For local pickle artifacts, `MODEL_SHA256` provides an integrity check. Pickle
is executable serialization, so the artifact source and checksum must be
independently verified. Registry credentials and model artifacts are supplied
at runtime and are not baked into the container image.

## 5. Authentication and privacy

When `API_KEY` is set, the prediction route requires the matching
`X-API-Key` header. This is a minimal service guard, not a complete identity,
authorization, or institutional access-control solution. Production exposure
requires an authenticated gateway, TLS, rate limits, authorization, audit
logging, secret rotation, and network controls.

Requests must not contain student names, raw identifiers, free-text wellbeing
records, credentials, or unnecessary sensitive attributes. The service
metrics expose aggregate request counts and latency, not request payloads.

## 6. Configuration

| Variable | Required | Meaning |
|---|---:|---|
| `MODEL_URI` | Conditional | MLflow `models:/` or `runs:/` URI |
| `MODEL_PATH` | Conditional | Trusted local model path |
| `ALLOW_TRUSTED_PICKLE_MODEL` | For pickle | Must be `1` for local pickle loading |
| `MODEL_SHA256` | Recommended for pickle | Expected SHA-256 digest |
| `MODEL_THRESHOLD` | No | Numeric operating threshold; default `0.5` |
| `MODEL_VERSION` | No | Version label returned by the API |
| `API_KEY` | Recommended | Expected `X-API-Key` value |
| `ENABLE_API_DOCS` | No | Enables `/docs` only when set to `1` |

The threshold is an operating configuration, not a validated intervention
policy. It must be reviewed using capacity, error costs, calibration, and
human-support procedures.

## 7. Observability

Prometheus records aggregate HTTP request counts by method, path, and status,
and request-duration histograms. Grafana can visualize these metrics through
the Compose monitoring stack. Operational monitoring does not establish model
validity; model quality, calibration, subgroup outcomes, and intervention
effects require separate evaluation reports.
