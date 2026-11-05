from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[2]


def _yaml(path: str) -> dict:
    return yaml.safe_load((ROOT / path).read_text(encoding="utf-8"))


def test_dvc_contains_both_statistical_validation_stages() -> None:
    stages = _yaml("dvc.yaml")["stages"]
    assert "oulad_statistical_validation" in stages
    assert "synthetic_statistical_validation" in stages
    assert stages["oulad_statistical_validation"]["outs"] == [
        "artifacts/validation/oulad_statistical_validation.json"
    ]


def test_kubernetes_deployment_requires_private_image_and_release_secret() -> None:
    deployment = _yaml("deploy/kubernetes/deployment.yaml")
    pod = deployment["spec"]["template"]["spec"]
    assert pod["imagePullSecrets"] == [{"name": "ghcr-pull-secret"}]
    container = pod["containers"][0]
    secret_names = {
        item["valueFrom"]["secretKeyRef"]["name"]
        for item in container["env"]
        if "valueFrom" in item
    }
    assert secret_names == {"APP_SECRET_PLACEHOLDER"}
    assert any(item["name"] == "APP_ENV" and item["value"] == "production" for item in container["env"])
    kustomization = _yaml("deploy/kubernetes/kustomization.yaml")
    assert "namespace.yaml" not in kustomization["resources"]


def test_ingress_and_alerting_require_tls_and_critical_api_alerts() -> None:
    ingress = _yaml("deploy/kubernetes/ingress.yaml")
    assert ingress["spec"]["tls"][0]["secretName"] == "TLS_SECRET_PLACEHOLDER"
    deployment = _yaml("deploy/kubernetes/deployment.yaml")
    container = deployment["spec"]["template"]["spec"]["containers"][0]
    ingress_host = ingress["spec"]["rules"][0]["host"]
    for probe_name in ("startupProbe", "readinessProbe", "livenessProbe"):
        headers = container[probe_name]["httpGet"]["httpHeaders"]
        assert {header["name"]: header["value"] for header in headers}["Host"] == ingress_host
    alerts = _yaml("monitoring/alerts.yml")
    alert_names = {
        rule["alert"]
        for group in alerts["groups"]
        for rule in group["rules"]
    }
    assert "SmartStudyPlannerApiUnavailable" in alert_names
    assert "SmartStudyPlannerDataDriftWarning" in alert_names


def test_operations_workflows_cover_monitoring_validation_and_recovery() -> None:
    workflows = {path.name for path in (ROOT / ".github/workflows").glob("*.yml")}
    assert {"data-validation.yml", "monitoring.yml", "recovery.yml"}.issubset(workflows)
    deployment = (ROOT / ".github/workflows/deploy.yml").read_text(encoding="utf-8")
    assert "pipeline.verify_registered_model" in deployment
    assert "ghcr-pull-secret" in deployment
    assert 'secret["immutable"]=True' in deployment
    assert "https://${APP_HOST}/readyz" in deployment
