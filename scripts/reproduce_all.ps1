
$ErrorActionPreference = "Stop"

Set-Location (Split-Path $PSScriptRoot -Parent)

if (-not $env:MLFLOW_TRACKING_URI) {
    throw "MLFLOW_TRACKING_URI is missing"
}
if (-not $env:MLFLOW_TRACKING_USERNAME) {
    throw "MLFLOW_TRACKING_USERNAME is missing"
}
if (-not $env:MLFLOW_TRACKING_PASSWORD) {
    throw "MLFLOW_TRACKING_PASSWORD is missing"
}

New-Item -ItemType Directory -Force ".repro" |
    Out-Null

Write-Host "Reproducing DVC experiment..."

dvc repro synthetic_validate model_quality

if ($LASTEXITCODE -ne 0) {
    throw "DVC reproduction failed"
}


Write-Host "Training OULAD full-course models..."

python -m pipeline.training_pipeline `
    --data-dir data/processed/oulad `
    --metrics-output .repro/oulad_full.json `
    --model-output .repro/oulad_best.pkl `
    --mlflow `
    --register-models `
    --experiment-name smart-study-planner-oulad `
    --run-name reproduce-oulad-full

if ($LASTEXITCODE -ne 0) {
    throw "OULAD full-course registration failed"
}


Write-Host "Training OULAD early-warning models..."

python -m pipeline.early_warning_pipeline `
    --data-dir data/processed/oulad `
    --metrics-output .repro/oulad_early.json `
    --cutoffs-days 30 60 90 `
    --mlflow `
    --register-models `
    --experiment-name smart-study-planner-oulad-early-warning `
    --run-name reproduce-oulad-early

if ($LASTEXITCODE -ne 0) {
    throw "OULAD early-warning registration failed"
}


Write-Host "Training synthetic models..."

python -m pipeline.synthetic_baseline_pipeline `
    --data-dir data/raw/synthetic `
    --metrics-output .repro/synthetic_all.json `
    --model-dir .repro/synthetic_models `
    --cutoffs-days 30 60 90 `
    --random-state 42 `
    --mlflow `
    --register-models `
    --experiment-name smart-study-planner-synthetic-baseline `
    --run-name reproduce-synthetic-all

if ($LASTEXITCODE -ne 0) {
    throw "Synthetic model registration failed"
}


Write-Host "Auditing MLflow registrations..."

python -m pipeline.audit_registry

if ($LASTEXITCODE -ne 0) {
    throw "Registry audit failed"
}

Write-Host "All reproduction stages completed."
