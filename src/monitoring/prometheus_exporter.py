"""Publish batch-pipeline metrics to a Prometheus Pushgateway.

The OULAD pipelines are short-lived batch jobs, so they do not expose a
long-running ``/metrics`` endpoint. This module creates an isolated registry
for each completed run and pushes the resulting gauges to a Pushgateway when
the caller explicitly supplies a URL.
"""

from __future__ import annotations

import os
import time
from typing import Any

from prometheus_client import CollectorRegistry, Gauge, push_to_gateway


METRIC_KEYS = (
    "accuracy",
    "balanced_accuracy",
    "precision",
    "recall",
    "f1",
    "roc_auc",
)


def _configured_url(pushgateway_url: str | None) -> str | None:
    return pushgateway_url or os.getenv("PROMETHEUS_PUSHGATEWAY_URL")


def _set_if_numeric(gauge: Gauge, value: Any, labels: dict[str, str]) -> None:
    if value is not None:
        gauge.labels(**labels).set(float(value))


def _common_gauges(registry: CollectorRegistry) -> dict[str, Gauge]:
    gauges = {
        "last_success": Gauge(
            "oulad_pipeline_last_success_timestamp",
            "Unix timestamp of the last successful OULAD pipeline execution.",
            ["job"],
            registry=registry,
        ),
        "samples": Gauge(
            "oulad_pipeline_samples",
            "Number of enrollment rows processed by the pipeline.",
            ["job"],
            registry=registry,
        ),
        "train_samples": Gauge(
            "oulad_pipeline_train_samples",
            "Number of training rows used by the pipeline.",
            ["job"],
            registry=registry,
        ),
        "test_samples": Gauge(
            "oulad_pipeline_test_samples",
            "Number of test rows used by the pipeline.",
            ["job"],
            registry=registry,
        ),
    }
    return gauges


def push_training_metrics(
    metrics: dict[str, Any],
    pushgateway_url: str | None = None,
    job: str = "smart-study-planner-training",
) -> None:
    """Push full-course baseline metrics when a Pushgateway URL is configured."""

    url = _configured_url(pushgateway_url)
    if not url:
        return

    registry = CollectorRegistry()
    common = _common_gauges(registry)
    common["last_success"].labels(job=job).set(time.time())
    common["samples"].labels(job=job).set(float(metrics["n_samples"]))
    common["train_samples"].labels(job=job).set(float(metrics["n_train"]))
    common["test_samples"].labels(job=job).set(float(metrics["n_test"]))

    selected = Gauge(
        "oulad_selected_model",
        "One for the model selected by the pipeline.",
        ["job", "model"],
        registry=registry,
    )
    selected.labels(job=job, model=str(metrics["best_model"])).set(1)

    model_gauges = {
        key: Gauge(
            f"oulad_model_{key}",
            f"Full-course baseline {key}.",
            ["job", "model"],
            registry=registry,
        )
        for key in METRIC_KEYS
    }
    for model_name, model_metrics in metrics["models"].items():
        labels = {"job": job, "model": str(model_name)}
        for key, gauge in model_gauges.items():
            _set_if_numeric(gauge, model_metrics.get(key), labels)

    push_to_gateway(url, job=job, registry=registry)


def push_early_warning_metrics(
    metrics: dict[str, Any],
    pushgateway_url: str | None = None,
    job: str = "smart-study-planner-early-warning",
) -> None:
    """Push cutoff-specific early-warning metrics to a Pushgateway."""

    url = _configured_url(pushgateway_url)
    if not url:
        return

    registry = CollectorRegistry()
    common = _common_gauges(registry)
    metric_gauges = {
        key: Gauge(
            f"oulad_early_warning_{key}",
            f"Early-warning {key} by cutoff and model.",
            ["job", "cutoff_days", "model"],
            registry=registry,
        )
        for key in METRIC_KEYS
    }
    selected = Gauge(
        "oulad_early_warning_selected_model",
        "One for the selected early-warning model at a cutoff.",
        ["job", "cutoff_days", "model"],
        registry=registry,
    )
    last_success = common["last_success"]
    last_success.labels(job=job).set(time.time())

    for cutoff_text, evaluation in metrics["evaluations"].items():
        cutoff = str(cutoff_text)
        selected.labels(
            job=job,
            cutoff_days=cutoff,
            model=str(evaluation["best_model"]),
        ).set(1)
        for model_name, model_metrics in evaluation["models"].items():
            labels = {"job": job, "cutoff_days": cutoff, "model": str(model_name)}
            for key, gauge in metric_gauges.items():
                _set_if_numeric(gauge, model_metrics.get(key), labels)

    push_to_gateway(url, job=job, registry=registry)
