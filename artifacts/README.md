# Machine-learning artifacts

This directory is the canonical local destination for generated machine-learning
outputs. Model source code remains under `src/models/`; generated files do not.

The layout is:

- `models/`: serialized fitted estimators used for local evaluation or inference;
- `metrics/`: machine-readable evaluation, calibration, fairness, and transfer reports;
- `validation/`: data-quality and statistical-validation evidence.

The generated contents of these subdirectories are owned by DVC and ignored by
Git. Their hashes and producing commands are recorded in `dvc.lock`. Restore them
with `dvc pull`, or reproduce them with `dvc repro`. MLflow/DagsHub remains the
system of record for remotely logged runs and registered release candidates; the
local artifact tree does not by itself prove that a model has been registered or
approved for deployment.
