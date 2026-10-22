"""Unit checks for the synthetic baseline modelling contract."""

import pandas as pd

from src.models.synthetic_baseline import MODEL_NAMES, make_pipeline, student_split


def test_student_split_keeps_each_student_in_one_partition() -> None:
    frame = pd.DataFrame(
        {
            "student_id": [f"S{i}" for i in range(8) for _ in range(2)],
            "risk_label": [0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1],
            "numeric_feature": list(range(16)),
        }
    )
    train, test = student_split(frame, random_state=42)
    assert set(train.student_id).isdisjoint(set(test.student_id))
    assert set(train.student_id) | set(test.student_id) == set(frame.student_id)


def test_model_pipeline_contains_the_declared_preprocessing_contract() -> None:
    features = pd.DataFrame({"numeric_feature": [1.0, 2.0], "category": ["a", "b"]})
    for model_name in MODEL_NAMES:
        pipeline = make_pipeline(features, model_name=model_name)
        assert pipeline.named_steps["preprocess"].transformers
        assert pipeline.named_steps["model"] is not None
