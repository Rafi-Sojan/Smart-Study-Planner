# Smart Study Planner risk register

## Purpose and scope

This register records the risks that remain relevant after the reproducibility,
evaluation, API, monitoring, and container safeguards were added. It is a
governance document, not evidence that the system is ready for live student
decision-making.

The repository contains three distinct evidence tracks:

1. OULAD retrospective enrollment-risk benchmarking;
2. synthetic Indian-university planner development; and
3. future application and recommendation components.

Results from these tracks must not be combined. Synthetic performance does not
measure real student performance, and retrospective OULAD results do not prove
prospective intervention benefit.

## Risk register

| ID | Risk | Severity | Current control | Residual action / release gate |
|---|---|---:|---|---|
| R-01 | A student may appear in multiple enrollments. | Critical | OULAD baseline evaluation now uses grouped student partitions; synthetic evaluation is student-disjoint. | Verify the group-disjoint invariant on every future dataset and report student-level as well as enrollment-level results. |
| R-02 | Selecting a model or threshold on the final test set inflates performance. | Critical | Model selection uses validation data; the final test partition is evaluated after refitting. Thresholds are selected on validation data. | Lock the final test set and require an independent review before model promotion. |
| R-03 | Final course outcomes are retrospective labels. | Critical | Early-warning predictors exclude post-cutoff events. | Complete prospective validation with a defined prediction horizon and intervention outcome. |
| R-04 | Synthetic labels are generated from simulator logic. | Critical | Synthetic results are labelled development-only. | Validate against consented institutional data before making performance claims. |
| R-05 | Rare risk cases make accuracy misleading. | High | PR-AUC, ROC-AUC, balanced accuracy, confusion matrices, threshold diagnostics, and validation thresholds are recorded. | Select thresholds from intervention capacity and reviewed false-positive/false-negative costs. |
| R-06 | Model probabilities may be poorly calibrated. | High | Brier score is recorded. | Add calibration curves, reliability checks, and calibrated models before displaying probabilities to users. |
| R-07 | Protected or socioeconomic variables may create disparate errors. | High | Audit-only fields are excluded from default predictors and subgroup error rates are recorded. | Add equal-opportunity analysis, uncertainty intervals, minimum group sizes, and a human fairness review. |
| R-08 | Missingness may be informative or not-at-random. | High | Missing values are not fabricated as zero; missingness and drift utilities exist. | Validate missingness mechanisms on institutional data and monitor missingness by subgroup. |
| R-09 | OULAD identifiers and wellbeing fields may be sensitive. | Critical | Raw data is excluded from Git; API requests forbid arbitrary identifiers; logs redact identifiers and credentials. | Confirm dataset licence, institutional approval, retention, access control, deletion, and consent requirements. |
| R-10 | A pickle artifact can execute code when loaded. | Critical | Model loading is opt-in and supports SHA-256 verification. | Load only trusted registry artifacts, restrict registry permissions, and review serialization alternatives. |
| R-11 | MLflow/DVC provenance can be incomplete. | High | Metrics include data hash, schema version, runtime, platform, and Git commit when available. | Push DVC cache, record the exact commit in CI, and require provenance fields before registration. |
| R-12 | Drift or stale batch metrics can go unnoticed. | High | Schema, missingness, and numeric drift checks are available; monitoring remains opt-in. | Schedule monitoring, configure alerts, manage Pushgateway stale series, and track calibration and subgroup metrics. |
| R-13 | The API or planner could be mistaken for a production decision system. | Critical | The API is not ready until a trusted model is explicitly configured; readiness fails otherwise. | Add authentication, authorization, rate limits, audit logs, human review, notice, appeal, and intervention safeguards. |
| R-14 | Container and dependency supply-chain risk exists. | High | Container runs as non-root and images are version-pinned. | Pin image digests, scan dependencies/images, and review GitHub Actions provenance. |
| R-15 | Notebook outputs can become stale. | Medium | Reusable pipeline functions remain the source of truth. | Execute notebooks in CI with controlled fixtures and fail on execution errors. |
| R-16 | Multiple alerts may overload advisers or students. | High | Threshold diagnostics expose alert volume. | Define intervention capacity, deduplicate at student level, and measure support outcomes. |
| R-17 | Fail and withdrawal outcomes may require different support. | High | Original outcome categories remain available for analysis. | Evaluate separate targets or a multi-task approach before prescribing interventions. |
| R-18 | Sleep, screen time, fatigue, and wellbeing fields may be intrusive. | High | The synthetic track is explicitly synthetic and API inputs are schema-validated. | Apply data minimization, consent, opt-out, access controls, and explainable support policies. |

## Release policy

The project may be used for local research and reproducibility testing after
the automated tests pass. It must not be used to make automated academic,
disciplinary, admissions, financial-aid, or attendance decisions.

Model registration is not model approval. A registered artifact remains a
candidate until the following are complete:

- locked-test evaluation and prospective validation;
- calibration and threshold review;
- subgroup fairness review;
- data-protection and institutional approval;
- a documented intervention and appeal process;
- monitoring and rollback procedures; and
- reproducible Git, DVC, and MLflow provenance.

## Operational security checklist

- Rotate any credential that has been pasted into chat, terminals, notebooks,
  or logs.
- Keep DVC credentials in machine-local configuration only.
- Keep MLflow credentials in environment variables or a secret manager.
- Do not log raw student identifiers or row-level wellbeing data.
- Set `GRAFANA_ADMIN_PASSWORD` before starting the monitoring stack.
- Set `ALLOW_TRUSTED_PICKLE_MODEL=1` only when the artifact source and checksum
  have been independently verified.
- Keep the monitoring ports bound to localhost unless authentication and network
  controls are configured.
