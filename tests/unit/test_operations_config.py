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
    assert stages["train"]["outs"] == ["artifacts/models/baseline.pkl"]
    assert stages["train"]["metrics"] == ["artifacts/metrics/metrics.json"]
    assert stages["synthetic_baseline"]["outs"] == [
        "artifacts/models/synthetic_baseline"
    ]
    assert stages["synthetic_baseline"]["metrics"] == [
        "artifacts/metrics/synthetic_baseline_metrics.json"
    ]
    assert stages["model_quality"]["outs"] == [
        "artifacts/validation/model_quality"
    ]
    assert "configs/model-quality.yaml" in stages["model_quality"]["deps"]


def test_local_compose_mounts_the_canonical_model_artifact_tree() -> None:
    compose = _yaml("docker-compose.yaml")
    volumes = compose["services"]["api"]["volumes"]
    assert "./artifacts/models/pretrained:/models:ro" in volumes
    assert "./artifacts/models:/model-store:ro" in volumes
    assert all(not volume.startswith("./models") for volume in volumes)


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
    assert "web-deployment.yaml" in kustomization["resources"]
    assert {image["name"] for image in kustomization["images"]} == {
        "smart-study-planner-api",
        "smart-study-planner-web",
    }


def test_web_gateway_is_non_root_and_is_the_public_ingress_backend() -> None:
    deployment = _yaml("deploy/kubernetes/web-deployment.yaml")
    pod = deployment["spec"]["template"]["spec"]
    container = pod["containers"][0]
    assert pod["imagePullSecrets"] == [{"name": "ghcr-pull-secret"}]
    assert pod["securityContext"]["runAsNonRoot"] is True
    assert container["securityContext"]["readOnlyRootFilesystem"] is True
    assert container["ports"] == [{"name": "http", "containerPort": 8080}]
    ingress = _yaml("deploy/kubernetes/ingress.yaml")
    backend = ingress["spec"]["rules"][0]["http"]["paths"][0]["backend"]["service"]
    assert backend["name"] == "smart-study-planner-web"


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
    docker = (ROOT / ".github/workflows/docker.yml").read_text(encoding="utf-8")
    assert "pipeline.verify_registered_model" in deployment
    assert "pipeline.verify_model_catalog" in deployment
    assert "MODEL_CATALOG_JSON" in deployment
    assert "ghcr-pull-secret" in deployment
    assert 'secret["immutable"]=True' in deployment
    assert "https://${APP_HOST}/readyz" in deployment
    assert "smart-study-planner-web" in deployment
    assert 'git merge-base --is-ancestor "$IMAGE_TAG" origin/main' in deployment
    assert "Resolve immutable release image digests" in deployment
    assert "API_IMAGE_REFERENCE" in deployment
    assert "WEB_IMAGE_REFERENCE" in deployment
    assert "image-digest" in deployment
    assert "frontend/Dockerfile" in docker
    assert "if: github.event_name != 'push'" not in docker
    docker_config = _yaml(".github/workflows/docker.yml")
    assert set(docker_config["jobs"]) == {"images"}
    matrix = docker_config["jobs"]["images"]["strategy"]["matrix"]["include"]
    assert {item["component"] for item in matrix} == {"api", "web"}
