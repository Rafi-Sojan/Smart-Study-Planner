# Production-readiness control matrix

## Implemented repository controls

The repository now enforces the following controls before the production
deployment workflow can complete:

| Area | Enforced control |
|---|---|
| Container | Immutable full-commit image tag and private GHCR pull secret |
| Model | Immutable numeric MLflow version; artifact download and registry-tag verification |
| Threshold | Registry operating threshold must exist and match deployment configuration |
| Fairness | Formal report tag is required; confidence intervals and minimum-group rules are generated during training |
| Schema | Runtime feature names must exactly match the fitted model contract and its SHA-256 registry tag |
| API | Production requires API key, allowed host, registered model, disabled docs, and no local pickle path |
| Network | TLS ingress, HTTPS redirect, request-size/rate limits, and Kubernetes NetworkPolicy |
| Availability | Two minimum replicas, startup/readiness/liveness probes, HPA, and PodDisruptionBudget |
| Monitoring | Prometheus rules, Alertmanager, scheduled HTTPS checks, and aggregate drift publishing |
| Recovery | Release-specific secrets, retained deployment revisions, guarded rollback/restart workflow, and evidence artifacts |
| Planner | Validated task/availability contract, deterministic priorities, explicit breaks and capacity shortfalls, human review |
| Data validation | OULAD and synthetic statistical reports are DVC stages and are reproduced by a credentialed scheduled workflow |

## External prerequisites that cannot be created by source code

A real release still requires all of the following external evidence:

1. an institution-controlled Kubernetes cluster with an ingress controller,
   metrics server, cert-manager or a provisioned TLS secret, and network-policy
   enforcement;
2. DNS for the production host;
3. protected GitHub environments, required reviewers, least-privilege
   kubeconfig, GHCR read token, MLflow credentials, DVC credentials, and API
   key;
4. a prospective institutional model version whose registry tags state
   `deployment_eligible=true` and `fairness_gate_passed=true`;
5. approved intervention capacity, false-positive/false-negative costs,
   notification, appeal, consent, retention, and accessibility procedures;
6. an external Alertmanager receiver and named incident owner; and
7. a measured non-production backup/restore and rollback drill.

Current OULAD models are retrospective and current synthetic models are
development-only. They are intentionally unable to pass the production model
verification step. This is the expected release boundary, not a deployment
bug.
