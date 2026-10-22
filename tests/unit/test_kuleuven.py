from pathlib import Path

import pandas as pd

from src.data.kuleuven import build_kuleuven_features


def _write_fixture(root: Path) -> None:
    for year in ("1819", "1920", "2021"):
        pd.DataFrame(
            {
                "COURSE_ID": ["Course A", "Course A"],
                "USER_ID": [1, 2],
                "SCORE_CATEGORY_FINAL": ["Pass", "Fail"],
                "PASSED": [1, 0],
            }
        ).to_excel(root / f"{year}_course_participation.xlsx", index=False)
        pd.DataFrame(
            {
                "ACTION_ID": [1, 2, 3],
                "COURSE_ID": ["Course A"] * 3,
                "USER_ID": [1, 1, 2],
                "CONTENT_ID": [10, 11, 12],
                "SESSION_ID": [100, 101, 102],
                "TIMESTAMP": [
                    f"20{year[:2]}-01-01 09:00:00",
                    f"20{year[:2]}-02-15 09:00:00",
                    f"20{year[:2]}-01-02 09:00:00",
                ],
            }
        ).to_csv(root / f"{year}_log_activity.csv", index=False)


def test_kuleuven_features_respect_cutoff_and_keep_final_outcome_as_label(tmp_path: Path) -> None:
    _write_fixture(tmp_path)
    frame = build_kuleuven_features(tmp_path, cutoff_days=30)

    user_one = frame.loc[frame["id_student"].eq(1)].iloc[0]
    user_two = frame.loc[frame["id_student"].eq(2)].iloc[0]
    assert user_one["activity_count"] == 1
    assert user_two["activity_count"] == 1
    assert user_one["target_risk"] == 0
    assert user_two["target_risk"] == 1
    assert "score_category_final" in frame.columns
