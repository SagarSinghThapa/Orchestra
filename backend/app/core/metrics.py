from typing import Optional
from prometheus_client import CollectorRegistry, Counter, Histogram, generate_latest

from app.core.config import settings

# Isolated collector registry prevents test suite pollution and duplicate registration errors
metrics_registry = CollectorRegistry(auto_describe=True)

# 1. HTTP Request Counter (bounded labels: method, route, status_class)
http_requests_total = Counter(
    "orchestra_http_requests_total",
    "Total incoming HTTP requests partitioned by method, route template, and status class",
    ["method", "route", "status_class"],
    registry=metrics_registry,
)

# 2. HTTP Request Duration Histogram (bounded labels: method, route)
http_request_duration_seconds = Histogram(
    "orchestra_http_request_duration_seconds",
    "HTTP request latency in seconds partitioned by method and route template",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0),
    registry=metrics_registry,
)

# 3. Rate Limit Rejections Counter (bounded label: route_class)
rate_limit_rejections_total = Counter(
    "orchestra_rate_limit_rejections_total",
    "Total requests rejected by rate limiting partitioned by route class",
    ["route_class"],
    registry=metrics_registry,
)

# 4. LLM Calls Counter (bounded labels: provider, status)
llm_calls_total = Counter(
    "orchestra_llm_calls_total",
    "Total LLM provider calls partitioned by provider and execution status",
    ["provider", "status"],
    registry=metrics_registry,
)

# 5. LLM Call Duration Histogram (bounded label: provider)
llm_call_duration_seconds = Histogram(
    "orchestra_llm_call_duration_seconds",
    "LLM provider call latency in seconds partitioned by provider",
    ["provider"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 45.0),
    registry=metrics_registry,
)

# 6. Retrieval Duration Histogram (bounded label: mode)
retrieval_duration_seconds = Histogram(
    "orchestra_retrieval_duration_seconds",
    "Vector and hybrid retrieval latency in seconds partitioned by mode",
    ["mode"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0),
    registry=metrics_registry,
)

# 7. Developer Tasks Counter (bounded labels: task_type, status)
developer_tasks_total = Counter(
    "orchestra_developer_tasks_total",
    "Total Developer Agent task dispatches partitioned by task type and status",
    ["task_type", "status"],
    registry=metrics_registry,
)


def get_status_class(status_code: int) -> str:
    """Classifies an HTTP status code into a bounded 3-character class."""
    if 200 <= status_code < 300:
        return "2xx"
    elif 300 <= status_code < 400:
        return "3xx"
    elif 400 <= status_code < 500:
        return "4xx"
    elif 500 <= status_code < 600:
        return "5xx"
    return "other"


def record_http_request(method: str, route: str, status_code: int, duration_seconds: float) -> None:
    """Safely increments request count and records latency observation."""
    status_class = get_status_class(status_code)
    clean_route = route if route else "unmatched"
    try:
        http_requests_total.labels(method=method, route=clean_route, status_class=status_class).inc()
        http_request_duration_seconds.labels(method=method, route=clean_route).observe(duration_seconds)
    except Exception:
        pass


def record_rate_limit_rejection(route_class: str) -> None:
    """Safely increments rate-limit rejection count for a route class."""
    try:
        rate_limit_rejections_total.labels(route_class=route_class).inc()
    except Exception:
        pass


def record_llm_call(provider: str, status: str, duration_seconds: float) -> None:
    """Safely records LLM provider call count and latency."""
    clean_provider = provider if provider in ("openai_compatible", "test", "mock") else "other"
    clean_status = status if status in ("success", "error", "timeout") else "other"
    try:
        llm_calls_total.labels(provider=clean_provider, status=clean_status).inc()
        llm_call_duration_seconds.labels(provider=clean_provider).observe(duration_seconds)
    except Exception:
        pass


def get_metrics_output() -> bytes:
    """Generates standard Prometheus scrape exposition format from the isolated registry."""
    return generate_latest(metrics_registry)
