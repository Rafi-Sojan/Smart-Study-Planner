# Notebook-specific agent guide

This file applies to `notebooks/` in addition to the repository-level guide.

## Notebook standard

Preserve the numbered `01` through `12` sequence and existing subject split.
Notebooks must contain formal explanations inside the notebook, not only links
to external documentation. Explain the purpose of each cleaning, processing,
feature, statistical, and modelling step; define important statistics; interpret
every material plot; and connect conclusions to the Smart Study Planner.

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

After editing, run:

```powershell
.\.venv\Scripts\python.exe -m pipeline.validate_notebooks notebooks
```

When execution is required, use the repository notebook execution utility and
confirm that stored outputs correspond to the executed code and current artifact
paths.

