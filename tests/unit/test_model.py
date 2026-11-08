from types import SimpleNamespace

import numpy as np
import pytest

from src.models.predict import (
    FeatureContractError,
    feature_contract,
    validate_feature_payload,
    validate_model_feature_contract,
)
from src.tracking.model_registry import parse_registered_model_uri, verify_registered_model


class _ContractModel:
    feature_names_in_ = np.array(["activity_count", "assessment_mean"])


class _RegistryClient:
    def get_model_version(self, name, version):
        return SimpleNamespace(
            name=name,
            version=version,
            run_id="run-1",
            status="READY",
            tags={
                "quality_gate_passed": "true",
                "deployment_eligible": "true",
                "fairness_gate_passed": "true",
                "selected_for_release": "true",
                "operating_threshold": "0.35",
                "threshold_source": "validation_intervention_policy",
                "feature_contract_sha256": feature_contract(_ContractModel())["sha256"],
                "feature_count": "2",
                "evidence_type": "prospective_institutional_validation",
                "deployment_claim": "prospective_validated",
            },
        )


def test_feature_contract_is_ordered_and_stable() -> None:
    contract = feature_contract(_ContractModel())
    assert contract["feature_names"] == ["activity_count", "assessment_mean"]
    assert len(contract["sha256"]) == 64


def test_feature_payload_rejects_identifiers_and_contract_mismatches() -> None:
    with pytest.raises(FeatureContractError, match="forbidden"):
        validate_feature_payload({"student_id": "S1"})
    with pytest.raises(FeatureContractError, match="missing"):
        validate_feature_payload({"activity_count": 2}, ["activity_count", "assessment_mean"])


def test_serving_contract_rejects_post_outcome_model_features() -> None:
    model = SimpleNamespace(feature_names_in_=np.array(["activity_count", "date_unregistration"]))

    with pytest.raises(FeatureContractError, match="cannot be served"):
        validate_model_feature_contract(model)


def test_registry_verification_requires_pinned_governed_version() -> None:
    report = verify_registered_model(
        "models:/risk-model/7",
        expected_threshold=0.35,
        client=_RegistryClient(),
    )
    assert report["passed"] is True
    assert report["resolved_uri"] == "models:/risk-model/7"


def test_registry_uri_parser_rejects_mutable_stage_syntax() -> None:
    assert parse_registered_model_uri("models:/risk-model@candidate")["reference_type"] == "alias"
    with pytest.raises(ValueError):
        parse_registered_model_uri("models:/risk-model/Production")
