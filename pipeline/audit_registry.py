
"""Audit MLflow model versions created by reproduction runs."""

import json
import re
from pathlib import Path

from mlflow.tracking import MlflowClient


REPORTS = {
    "oulad_full": (".repro/oulad_full.json", 4),
    "oulad_early": (".repro/oulad_early.json", 3),
    "synthetic": (".repro/synthetic_all.json", 12),
}

REQUIRED_TAGS = {
    "quality_gate_passed",
    "fairness_gate_passed",
    "selected_for_release",
    "deployment_eligible",
    "operating_threshold",
    "threshold_source",
    "feature_contract_sha256",
    "feature_count",
    "evidence_type",
    "deployment_claim",
}


def extract_names(value):
    """Flatten the pipeline's registered_models structure."""
    if isinstance(value, str):
        return [value]

    if isinstance(value, dict):
        return [
            name
            for child in value.values()
            for name in extract_names(child)
        ]

    raise ValueError(f"Invalid registry entry: {value!r}")


def main():
    client = MlflowClient()
    failures = []
    verified = 0

    for track, (filename, expected) in REPORTS.items():
        report = json.loads(
            Path(filename).read_text(encoding="utf-8")
        )

        run_id = report["mlflow_run_id"]
        names = extract_names(report["registered_models"])

        print(f"\n--- {track} ---")
        print(f"Run: {run_id}")

        if len(names) != expected or len(set(names)) != expected:
            failures.append(
                f"{track}: expected {expected} distinct models, "
                f"found {len(names)} entries"
            )

        for name in names:
            versions = [
                version
                for version in client.search_model_versions(
                    f"name='{name}'"
                )
                if version.run_id == run_id
            ]

            if len(versions) != 1:
                failures.append(
                    f"{name}: expected one version for run {run_id}, "
                    f"found {len(versions)}"
                )
                continue

            version = versions[0]
            tags = dict(version.tags or {})

            missing = REQUIRED_TAGS - tags.keys()

            if missing:
                failures.append(
                    f"{name}/v{version.version}: "
                    f"missing {sorted(missing)}"
                )
                continue

            for key in (
                "quality_gate_passed",
                "fairness_gate_passed",
                "selected_for_release",
                "deployment_eligible",
            ):
                if tags[key] not in ("true", "false"):
                    failures.append(
                        f"{name}/v{version.version}: invalid {key}"
                    )

            try:
                threshold = float(tags["operating_threshold"])
                assert 0 < threshold < 1
                assert int(tags["feature_count"]) > 0
                assert re.fullmatch(
                    r"[0-9a-fA-F]{64}",
                    tags["feature_contract_sha256"],
                )
            except (ValueError, AssertionError):
                failures.append(
                    f"{name}/v{version.version}: "
                    "invalid threshold or feature contract"
                )

            print(
                f"{name}/v{version.version} | "
                f"quality={tags['quality_gate_passed']} | "
                f"selected={tags['selected_for_release']}"
            )

            verified += 1

    expected_total = sum(count for _, count in REPORTS.values())

    print(f"\nVerified: {verified}/{expected_total}")

    if failures:
        for error in failures:
            print("FAIL:", error)
        raise SystemExit(1)

    if verified != expected_total:
        raise SystemExit("Registration count mismatch")

    print("SUCCESS: All model registrations have valid metadata.")


if __name__ == "__main__":
    main()
