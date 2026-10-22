from pathlib import Path

import pandas as pd

from src.data.transfer import build_synthetic_transfer_features


def test_synthetic_transfer_features_are_cutoff_aware(tmp_path: Path) -> None:
    pd.DataFrame(
        {"enrollment_id": ["e1"], "student_id": ["s1"], "offering_id": ["o1"]}
    ).to_csv(tmp_path / "enrollments.csv", index=False)
    pd.DataFrame({"offering_id": ["o1"], "course_id": ["c1"], "term_id": ["t1"]}).to_csv(
        tmp_path / "course_offerings.csv", index=False
    )
    pd.DataFrame({"term_id": ["t1"], "start_date": ["2025-01-01"]}).to_csv(
        tmp_path / "academic_terms.csv", index=False
    )
    pd.DataFrame({"student_id": ["s1"], "offering_id": ["o1"], "passed": [False]}).to_csv(
        tmp_path / "outcomes.csv", index=False
    )
    pd.DataFrame(
        {
            "session_id": ["a", "b"],
            "student_id": ["s1", "s1"],
            "enrollment_id": ["e1", "e1"],
            "topic_id": ["t1", "t2"],
            "planned_start": ["2025-01-02", "2025-03-01"],
        }
    ).to_csv(tmp_path / "study_sessions.csv", index=False)

    frame = build_synthetic_transfer_features(tmp_path, cutoff_days=30)
    row = frame.iloc[0]
    assert row["activity_count"] == 1
    assert row["active_day_count"] == 1
    assert row["content_count"] == 1
    assert row["target_risk"] == 1
