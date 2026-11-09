"""Run formal statistical validation for the OULAD and synthetic tracks.

The command writes compact JSON reports consumed by the corresponding
validation notebooks.  It never combines the two training populations: the
real-world comparisons are distribution and metric comparisons against the
authorised KU Leuven release, not claims that the synthetic data is real.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import pandas as pd

from src.data.cleaner import clean_oulad_tables
from src.data.kuleuven import build_kuleuven_cutoff_features
from src.data.loader import load_oulad_tables
from src.data.synthetic_validation import validate_synthetic_dataset
from src.features.feature_engineering import build_oulad_features
from src.features.synthetic_features import build_cutoff_features
from src.data.transfer import build_synthetic_transfer_features
from src.validation.statistical import (
    binary_rate_test,
    categorical_distribution_tests,
    json_records,
    map_oulad_engagement,
    numeric_association_tests,
    numeric_distribution_tests,
    selected_metric_rows,
    student_disjoint_split,
)


OULAD_STATIC_NUMERIC = ("num_of_prev_attempts", "studied_credits")
OULAD_CATEGORICAL = (
    "gender",
    "region",
    "highest_education",
    "age_band",
    "disability",
    "code_module",
)
ENGAGEMENT_NUMERIC = (
    "activity_count",
    "active_day_count",
    "content_count",
    "mean_daily_activity",
)
SYNTHETIC_NUMERIC = (
    "prior_cumulative_gpa",
    "attendance_pct_at_cutoff",
    "assessment_mean_score",
    "active_study_minutes",
    "session_completion_rate",
    "mean_sleep_hours",
    "mean_total_screen_minutes",
    "mean_stress_score",
    "mean_available_hours",
)


def _presentation_key(value: object) -> tuple[int, int, str]:
    text = str(value)
    year = int(text[:4]) if text[:4].isdigit() else 0
    suffix = text[4:]
    suffix_order = {"B": 0, "J": 1}
    return year, suffix_order.get(suffix, 2), suffix


def _read_json(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _write_json(report: dict[str, Any], output: str | Path | None) -> dict[str, Any]:
    if output is not None:
        path = Path(output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True, default=_json_default) + "\n", encoding="utf-8")
    return report


def _json_default(value: Any) -> Any:
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object is not JSON serializable: {type(value).__name__}")


def _report_metadata() -> dict[str, Any]:
    return {
        "alpha": 0.05,
        "multiple_testing_correction": "Holm-Bonferroni within each test family",
        "interpretation": (
            "P-values test distributional or rate differences under the observed sample; "
            "they do not establish causality, fairness, population representativeness, "
            "or intervention effectiveness. Effect sizes and domain context must be read together."
        ),
    }


def _metric_documents(
    *,
    oulad_metrics: str | Path,
    synthetic_metrics: str | Path | None,
    kuleuven_metrics: str | Path | None,
    cutoffs: Iterable[int],
) -> pd.DataFrame:
    documents: dict[str, dict[str, Any]] = {"OULAD": _read_json(oulad_metrics)}
    if synthetic_metrics is not None and Path(synthetic_metrics).is_file():
        documents["Synthetic"] = _read_json(synthetic_metrics)
    if kuleuven_metrics is not None and Path(kuleuven_metrics).is_file():
        documents["KU Leuven"] = _read_json(kuleuven_metrics)
    return selected_metric_rows(documents, cutoffs)


def _oulad_feature_frames(
    data_dir: str | Path,
    cutoffs: Iterable[int],
) -> tuple[dict[str, pd.DataFrame], list[str], str]:
    tables = clean_oulad_tables(load_oulad_tables(data_dir))
    presentations = sorted(
        tables["studentInfo"]["code_presentation"].dropna().unique(),
        key=_presentation_key,
    )
    latest = str(presentations[-1])
    frames: dict[str, pd.DataFrame] = {}
    for cutoff in sorted({int(value) for value in cutoffs}):
        frame = build_oulad_features(tables, clean=False, cutoff_days=cutoff)
        frames[str(cutoff)] = map_oulad_engagement(frame)
    return frames, [str(value) for value in presentations[:-1]], latest


def run_oulad_statistical_validation(
    data_dir: str | Path = "data/processed/oulad",
    kuleuven_path: str | Path = "data/raw/external/kuleuven/dataset.zip",
    early_warning_metrics: str | Path = "artifacts/metrics/early_warning_metrics.json",
    kuleuven_metrics: str | Path = "artifacts/metrics/kuleuven_external_metrics.json",
    output: str | Path | None = "artifacts/validation/oulad_statistical_validation.json",
    cutoffs: Iterable[int] = (30, 60, 90),
) -> dict[str, Any]:
    """Validate OULAD internally and compare it with KU Leuven."""

    cutoffs = tuple(sorted({int(value) for value in cutoffs}))
    tables = clean_oulad_tables(load_oulad_tables(data_dir))
    info = tables["studentInfo"].copy()
    presentations = sorted(info["code_presentation"].dropna().unique(), key=_presentation_key)
    latest = str(presentations[-1])
    prior = info.loc[info["code_presentation"].astype(str).ne(latest)].copy()
    latest_frame = info.loc[info["code_presentation"].astype(str).eq(latest)].copy()
    prior["target_risk"] = prior["final_result"].isin(["Fail", "Withdrawn"]).astype(int)
    latest_frame["target_risk"] = latest_frame["final_result"].isin(["Fail", "Withdrawn"]).astype(int)

    feature_frames: dict[str, pd.DataFrame] = {}
    for cutoff in cutoffs:
        feature_frames[str(cutoff)] = map_oulad_engagement(
            build_oulad_features(tables, clean=False, cutoff_days=cutoff)
        )

    internal_feature_tests = {}
    for cutoff in cutoffs:
        frame = feature_frames[str(cutoff)]
        previous = frame.loc[frame["code_presentation"].astype(str).ne(latest)]
        current = frame.loc[frame["code_presentation"].astype(str).eq(latest)]
        internal_feature_tests[str(cutoff)] = json_records(
            numeric_distribution_tests(
                previous,
                current,
                ENGAGEMENT_NUMERIC,
                reference_name="prior_presentations",
                comparison_name=latest,
            )
        )

    ku_frames = build_kuleuven_cutoff_features(kuleuven_path, tuple(cutoffs))
    real_world_feature_tests: dict[str, list[dict[str, Any]]] = {}
    real_world_rate_tests: dict[str, dict[str, Any]] = {}
    for cutoff in cutoffs:
        oulad_current = feature_frames[str(cutoff)].loc[
            feature_frames[str(cutoff)]["code_presentation"].astype(str).eq(latest)
        ]
        ku_current = ku_frames[cutoff].loc[ku_frames[cutoff]["code_presentation"].eq("2021")].copy()
        real_world_feature_tests[str(cutoff)] = json_records(
            numeric_distribution_tests(
                oulad_current,
                ku_current,
                ENGAGEMENT_NUMERIC,
                reference_name=f"OULAD_{latest}",
                comparison_name="KU_Leuven_2021",
            )
        )
        real_world_rate_tests[str(cutoff)] = binary_rate_test(
            oulad_current["target_risk"],
            ku_current["target_risk"],
            reference_name=f"OULAD_{latest}",
            comparison_name="KU_Leuven_2021",
        )

    report = {
        "dataset": "OULAD",
        "task": "internal_temporal_and_external_statistical_validation",
        "data_source": "Open University Learning Analytics Dataset",
        "evaluation_unit": "student-course-presentation enrollment",
        "latest_presentation": latest,
        "prior_presentations": [str(value) for value in presentations[:-1]],
        "test_protocol": "prior OULAD presentations compared with latest presentation; KU Leuven 2021 used as external real-world reference",
        "statistical_methodology": _report_metadata(),
        "internal_temporal_validation": {
            "numeric_distribution_tests": json_records(
                numeric_distribution_tests(
                    prior,
                    latest_frame,
                    OULAD_STATIC_NUMERIC,
                    reference_name="prior_presentations",
                    comparison_name=latest,
                )
            ),
            "categorical_distribution_tests": json_records(
                categorical_distribution_tests(
                    prior,
                    latest_frame,
                    OULAD_CATEGORICAL,
                    reference_name="prior_presentations",
                    comparison_name=latest,
                )
            ),
            "risk_rate_test": binary_rate_test(
                prior["target_risk"],
                latest_frame["target_risk"],
                reference_name="prior_presentations",
                comparison_name=latest,
            ),
            "engagement_distribution_tests_by_cutoff": internal_feature_tests,
            "interpretation": (
                "A significant shift indicates that the latest OULAD presentation differs from the prior "
                "presentations for the tested field. It is a generalisation warning, not proof that the model fails."
            ),
        },
        "real_world_comparison": {
            "reference_dataset": "KU Leuven Open Data, Private Learners",
            "reference_cohort": "2021 locked test presentation",
            "feature_mapping": {
                "activity_count": "OULAD VLE clicks versus KU Leuven LMS activity records",
                "active_day_count": "distinct observed activity dates",
                "content_count": "distinct OULAD VLE sites versus KU Leuven content IDs",
                "mean_daily_activity": "activity count divided by active observed days",
            },
            "numeric_distribution_tests_by_cutoff": real_world_feature_tests,
            "risk_rate_tests_by_cutoff": real_world_rate_tests,
            "selected_model_metric_comparison": json_records(
                _metric_documents(
                    oulad_metrics=early_warning_metrics,
                    synthetic_metrics=None,
                    kuleuven_metrics=kuleuven_metrics,
                    cutoffs=cutoffs,
                )
            ),
            "interpretation": (
                "The feature tests assess measurement and cohort differences between two real datasets. "
                "The model table is descriptive because each dataset contributes one aggregate metric per cutoff; "
                "it is not a hypothesis test of equal model performance."
            ),
        },
        "limitations": [
            "OULAD and KU Leuven measure different LMS systems, courses, institutions, and observation anchors.",
            "The KU Leuven comparison is a same-institution prospective-year benchmark with repeated anonymised IDs, not an unseen-person study.",
            "Statistical significance is sensitive to sample size; effect sizes and operational relevance must also be reviewed.",
            "The final outcome label is retrospective and does not establish intervention benefit or causality.",
        ],
    }
    return _write_json(report, output)


def run_synthetic_statistical_validation(
    data_dir: str | Path = "data/raw/synthetic",
    oulad_dir: str | Path = "data/processed/oulad",
    kuleuven_path: str | Path = "data/raw/external/kuleuven/dataset.zip",
    synthetic_metrics: str | Path = "artifacts/metrics/synthetic_baseline_metrics.json",
    oulad_metrics: str | Path = "artifacts/metrics/early_warning_metrics.json",
    kuleuven_metrics: str | Path = "artifacts/metrics/kuleuven_external_metrics.json",
    output: str | Path | None = "artifacts/validation/synthetic_statistical_validation.json",
    cutoffs: Iterable[int] = (30, 60, 90),
) -> dict[str, Any]:
    """Validate synthetic planner distributions and compare them with real data."""

    cutoffs = tuple(sorted({int(value) for value in cutoffs}))
    integrity = validate_synthetic_dataset(data_dir)
    cutoff_features = build_cutoff_features(data_dir, cutoffs)
    risk_association: dict[str, list[dict[str, Any]]] = {}
    split_shift: dict[str, list[dict[str, Any]]] = {}
    for cutoff in cutoffs:
        frame = cutoff_features[cutoff]
        risk_association[str(cutoff)] = json_records(
            numeric_association_tests(frame, "risk_label", SYNTHETIC_NUMERIC)
        )
        train_frame, test_frame = student_disjoint_split(
            frame,
            student_column="student_id",
            target_column="risk_label",
            random_state=42,
        )
        split_shift[str(cutoff)] = json_records(
            numeric_distribution_tests(
                train_frame,
                test_frame,
                SYNTHETIC_NUMERIC,
                reference_name="student_disjoint_train",
                comparison_name="student_disjoint_test",
            )
        )

    term_frame = cutoff_features[cutoffs[0]][["term_number", "risk_label"]].copy()
    first_term = term_frame.loc[term_frame["term_number"].eq(term_frame["term_number"].min()), "risk_label"]
    last_term = term_frame.loc[term_frame["term_number"].eq(term_frame["term_number"].max()), "risk_label"]

    transfer_frames = {
        cutoff: build_synthetic_transfer_features(data_dir, cutoff)
        for cutoff in cutoffs
    }
    oulad_features: dict[int, pd.DataFrame] = {}
    oulad_tables = clean_oulad_tables(load_oulad_tables(oulad_dir))
    oulad_presentations = sorted(
        oulad_tables["studentInfo"]["code_presentation"].dropna().unique(), key=_presentation_key
    )
    oulad_latest = str(oulad_presentations[-1])
    for cutoff in cutoffs:
        oulad_features[cutoff] = map_oulad_engagement(
            build_oulad_features(oulad_tables, clean=False, cutoff_days=cutoff)
        )

    ku_frames = build_kuleuven_cutoff_features(kuleuven_path, tuple(cutoffs))
    synthetic_vs_real: dict[str, Any] = {}
    synthetic_vs_oulad: dict[str, Any] = {}
    synthetic_vs_ku: dict[str, Any] = {}
    for cutoff in cutoffs:
        synthetic = transfer_frames[cutoff]
        ku = ku_frames[cutoff].loc[ku_frames[cutoff]["code_presentation"].eq("2021")]
        oulad = oulad_features[cutoff].loc[
            oulad_features[cutoff]["code_presentation"].astype(str).eq(oulad_latest)
        ]
        synthetic_vs_ku[str(cutoff)] = {
            "numeric_distribution_tests": json_records(
                numeric_distribution_tests(
                    synthetic,
                    ku,
                    ENGAGEMENT_NUMERIC,
                    reference_name="synthetic",
                    comparison_name="KU_Leuven_2021",
                )
            ),
            "risk_rate_test": binary_rate_test(
                synthetic["target_risk"],
                ku["target_risk"],
                reference_name="synthetic",
                comparison_name="KU_Leuven_2021",
            ),
        }
        synthetic_vs_oulad[str(cutoff)] = {
            "numeric_distribution_tests": json_records(
                numeric_distribution_tests(
                    synthetic,
                    oulad,
                    ENGAGEMENT_NUMERIC,
                    reference_name="synthetic",
                    comparison_name=f"OULAD_{oulad_latest}",
                )
            ),
            "risk_rate_test": binary_rate_test(
                synthetic["target_risk"],
                oulad["target_risk"],
                reference_name="synthetic",
                comparison_name=f"OULAD_{oulad_latest}",
            ),
        }
        synthetic_vs_real[str(cutoff)] = {
            "ku_leuven_2021": synthetic_vs_ku[str(cutoff)],
            "oulad_latest": synthetic_vs_oulad[str(cutoff)],
        }

    report = {
        "dataset": "Synthetic Indian-university planner",
        "task": "synthetic_integrity_distribution_and_external_statistical_validation",
        "evaluation_unit": "student-course-offering enrollment",
        "statistical_methodology": _report_metadata(),
        "integrity_validation": integrity,
        "student_disjoint_split_validation": {
            "numeric_distribution_tests_by_cutoff": split_shift,
            "interpretation": (
                "These tests check whether the student-disjoint test cohort is compositionally different "
                "from training for the selected planner variables. A non-significant result does not prove "
                "representativeness; it only indicates that this sample did not detect a shift."
            ),
        },
        "risk_association_tests": {
            "numeric_feature_tests_by_cutoff": risk_association,
            "first_term_vs_last_term_risk_rate_test": binary_rate_test(
                first_term,
                last_term,
                reference_name="synthetic_first_term",
                comparison_name="synthetic_last_term",
            ),
            "interpretation": (
                "A feature-level association is evidence of dependence in the generated records, not evidence "
                "that the feature causes academic risk. Strong associations may reflect simulator rules."
            ),
        },
        "real_world_comparison": {
            "references": [
                "KU Leuven Open Data, Private Learners, 2021 locked test cohort",
                f"OULAD latest presentation ({oulad_latest})",
            ],
            "feature_mapping": {
                "activity_count": "synthetic study sessions versus LMS activity records",
                "active_day_count": "distinct observed study/activity dates",
                "content_count": "distinct synthetic topics versus LMS content items",
                "session_count": "synthetic study sessions versus LMS sessions",
                "mean_daily_activity": "activity count divided by active observed days",
            },
            "synthetic_vs_kuleuven_by_cutoff": synthetic_vs_ku,
            "synthetic_vs_oulad_by_cutoff": synthetic_vs_oulad,
            "selected_model_metric_comparison": json_records(
                _metric_documents(
                    oulad_metrics=oulad_metrics,
                    synthetic_metrics=synthetic_metrics,
                    kuleuven_metrics=kuleuven_metrics,
                    cutoffs=cutoffs,
                )
            ),
            "interpretation": (
                "The real-world comparison is a stress test of measurement compatibility and risk prevalence. "
                "It cannot validate synthetic sleep, wellbeing, screen-time, or Indian-university attributes "
                "because the real datasets do not contain those constructs."
            ),
        },
        "limitations": [
            "The synthetic data is generated and its statistical relationships may reflect simulator design.",
            "KU Leuven and OULAD use different institutions, curricula, LMS schemas, and outcome definitions.",
            "A significant feature-distribution difference is expected to be common across institutions and is not alone a reason to discard the synthetic dataset.",
            "The comparison does not establish external calibration, fairness, causal validity, or intervention effectiveness.",
        ],
    }
    return _write_json(report, output)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="dataset", required=True)
    oulad = subparsers.add_parser("oulad")
    oulad.add_argument("--data-dir", type=Path, default=Path("data/processed/oulad"))
    oulad.add_argument("--kuleuven-path", type=Path, default=Path("data/raw/external/kuleuven/dataset.zip"))
    oulad.add_argument(
        "--early-warning-metrics",
        type=Path,
        default=Path("artifacts/metrics/early_warning_metrics.json"),
    )
    oulad.add_argument(
        "--kuleuven-metrics",
        type=Path,
        default=Path("artifacts/metrics/kuleuven_external_metrics.json"),
    )
    oulad.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/validation/oulad_statistical_validation.json"),
    )
    oulad.add_argument("--cutoffs", type=int, nargs="+", default=[30, 60, 90])
    synthetic = subparsers.add_parser("synthetic")
    synthetic.add_argument("--data-dir", type=Path, default=Path("data/raw/synthetic"))
    synthetic.add_argument("--oulad-dir", type=Path, default=Path("data/processed/oulad"))
    synthetic.add_argument("--kuleuven-path", type=Path, default=Path("data/raw/external/kuleuven/dataset.zip"))
    synthetic.add_argument(
        "--synthetic-metrics",
        type=Path,
        default=Path("artifacts/metrics/synthetic_baseline_metrics.json"),
    )
    synthetic.add_argument(
        "--oulad-metrics",
        type=Path,
        default=Path("artifacts/metrics/early_warning_metrics.json"),
    )
    synthetic.add_argument(
        "--kuleuven-metrics",
        type=Path,
        default=Path("artifacts/metrics/kuleuven_external_metrics.json"),
    )
    synthetic.add_argument(
        "--output",
        type=Path,
        default=Path("artifacts/validation/synthetic_statistical_validation.json"),
    )
    synthetic.add_argument("--cutoffs", type=int, nargs="+", default=[30, 60, 90])
    args = parser.parse_args()
    if args.dataset == "oulad":
        report = run_oulad_statistical_validation(
            data_dir=args.data_dir,
            kuleuven_path=args.kuleuven_path,
            early_warning_metrics=args.early_warning_metrics,
            kuleuven_metrics=args.kuleuven_metrics,
            output=args.output,
            cutoffs=args.cutoffs,
        )
    else:
        report = run_synthetic_statistical_validation(
            data_dir=args.data_dir,
            oulad_dir=args.oulad_dir,
            kuleuven_path=args.kuleuven_path,
            synthetic_metrics=args.synthetic_metrics,
            oulad_metrics=args.oulad_metrics,
            kuleuven_metrics=args.kuleuven_metrics,
            output=args.output,
            cutoffs=args.cutoffs,
        )
    print(json.dumps({"dataset": report["dataset"], "output": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

