"""Prometheus metrics for the inference service."""

from prometheus_client import Counter, Histogram


REQUEST_COUNT = Counter(
    "smart_study_planner_http_requests_total",
    "HTTP requests handled by the risk API.",
    ("method", "path", "status"),
)
REQUEST_LATENCY = Histogram(
    "smart_study_planner_http_request_duration_seconds",
    "HTTP request duration for the risk API.",
    ("method", "path"),
)
