from prometheus_client import generate_latest

from src.monitoring import prometheus_exporter


def _training_metrics() -> dict:
    return {
        "best_model": "hist_gradient_boosting",
        "n_samples": 100,
        "n_train": 75,
        "n_test": 25,
        "models": {
            "hist_gradient_boosting": {
                "accuracy": 0.9,
                "balanced_accuracy": 0.88,
                "precision": 0.91,
                "recall": 0.89,
                "f1": 0.90,
                "roc_auc": 0.95,
            },
        },
    }


def test_training_metrics_are_not_pushed_without_configuration(monkeypatch):
    pushed = []
    monkeypatch.setattr(prometheus_exporter, "push_to_gateway", pushed.append)

    prometheus_exporter.push_training_metrics(_training_metrics())

    assert pushed == []


def test_training_metrics_are_exported_to_pushgateway(monkeypatch):
    captured = {}

    def capture(url, job, registry):
        captured.update(url=url, job=job, payload=generate_latest(registry).decode())

    monkeypatch.setattr(prometheus_exporter, "push_to_gateway", capture)

    prometheus_exporter.push_training_metrics(
        _training_metrics(),
        pushgateway_url="http://localhost:9091",
    )

    assert captured["url"] == "http://localhost:9091"
    assert captured["job"] == "smart-study-planner-training"
    assert 'oulad_model_roc_auc{job="smart-study-planner-training",model="hist_gradient_boosting"} 0.95' in captured["payload"]
    assert 'oulad_selected_model{job="smart-study-planner-training",model="hist_gradient_boosting"} 1.0' in captured["payload"]


def test_early_warning_metrics_include_cutoff_labels(monkeypatch):
    captured = {}

    def capture(url, job, registry):
        captured.update(payload=generate_latest(registry).decode())

    monkeypatch.setattr(prometheus_exporter, "push_to_gateway", capture)
    prometheus_exporter.push_early_warning_metrics(
        {
            "evaluations": {
                "30": {
                    "best_model": "random_forest",
                    "models": {
                        "random_forest": {
                            "roc_auc": 0.81,
                            "accuracy": 0.73,
                            "balanced_accuracy": 0.72,
                            "precision": 0.75,
                            "recall": 0.74,
                            "f1": 0.74,
                        },
                    },
                },
            },
        },
        pushgateway_url="http://localhost:9091",
    )

    assert 'cutoff_days="30"' in captured["payload"]
    assert 'oulad_early_warning_roc_auc{cutoff_days="30",job="smart-study-planner-early-warning",model="random_forest"} 0.81' in captured["payload"]
