# Production-readiness control matrix

## Implemented repository controls

The repository now enforces the following controls before the production
deployment workflow can complete:

| Area | Enforced control |
|---|---|
| Container | Immutable full-commit API and React/Nginx image tags and private GHCR pull secret |
| Model | Bounded allowlist of immutable numeric MLflow versions; artifact download and registry-tag verification for every selectable option |
| Threshold | Registry operating threshold must exist and match deployment configuration |
| Fairness | Formal report tag is required; confidence intervals and minimum-group rules are generated during training |
| Schema | Every selectable model's runtime features must match its fitted contract and SHA-256 registry tag; forbidden post-outcome fields stop startup |
| API | Production requires a machine API key, PBKDF2 browser login, signed secure session, allowed host, registered model, disabled docs, and no local pickle path |
| Browser gateway | Same-origin API proxy, restrictive security headers, no browser-held API key, and Origin checks on session-authenticated mutations |
| Network | TLS ingress, HTTPS redirect, request-size/rate limits, and Kubernetes NetworkPolicy |
| Availability | Two minimum replicas, startup/readiness/liveness probes, HPA, and PodDisruptionBudget |
| Monitoring | Prometheus rules, Alertmanager, scheduled HTTPS checks, and aggregate drift publishing |
| Recovery | Release-specific secrets, retained deployment revisions, guarded rollback/restart workflow, and evidence artifacts |
| Planner | Validated task/availability contract, deterministic priorities, explicit breaks and capacity shortfalls, human review |
| Student feature adapter | Student-facing requests are converted server-side; unavailable LMS fields remain missing, evidence coverage is disclosed, and model internals are omitted from student responses |
| Data validation | OULAD and synthetic statistical reports are DVC stages and are reproduced by a credentialed scheduled workflow |
| Model quality | A DVC-owned three-track assessment records structural, fairness, threshold-policy, evidence, intervention-policy, and release-decision evidence without converting blocked models into approvals |

## External prerequisites that cannot be created by source code

A real release still requires all of the following external evidence:

1. an institution-controlled Kubernetes cluster with an ingress controller,
   metrics server, cert-manager or a provisioned TLS secret, and network-policy
   enforcement;
2. DNS for the production host;
3. protected GitHub environments, required reviewers, least-privilege
   kubeconfig, GHCR read token, MLflow credentials, DVC credentials, and API
   and session secrets;
4. a prospective institutional model version whose registry tags state
   `deployment_eligible=true` and `fairness_gate_passed=true`;
5. approved intervention capacity, false-positive/false-negative costs,
   notification, appeal, consent, retention, and accessibility procedures;
6. an external Alertmanager receiver and named incident owner; and
7. a measured non-production backup/restore and rollback drill; and
8. institution-approved SSO/OIDC, role assignment, operator account lifecycle,
   and audit retention before access expands beyond the protected single-user
   credential; and
9. a governed LMS/student-information-system integration with field-level data
   contracts, consent or lawful-basis review, freshness checks, reconciliation,
   retention limits, and failure handling before a self-reported demonstration
   can be replaced by institutional evidence.

Current OULAD models are retrospective and current synthetic models are
development-only. They are intentionally unable to pass the production model
verification step. This is the expected release boundary, not a deployment
bug.
