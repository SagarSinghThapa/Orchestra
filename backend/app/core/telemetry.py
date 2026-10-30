import contextlib
import logging
import time
from typing import Any, Dict, Generator, Optional

from app.core.config import settings
from app.core.context import get_request_id

logger = logging.getLogger("orchestra.telemetry")

SAFE_ATTRIBUTE_KEYS = {
    "operation",
    "route",
    "provider",
    "status",
    "duration_ms",
    "tokens_prompt",
    "tokens_completion",
    "task_type",
    "mode",
}

# In-memory captured spans for testing and inspection
captured_spans: list[Dict[str, Any]] = []


def sanitize_span_attributes(attributes: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Strips any attribute not in the safe whitelist.
    Guarantees that prompts, messages, source code, diffs, and secrets NEVER enter traces.
    """
    if not attributes:
        return {}
    sanitized = {}
    for k, v in attributes.items():
        if k in SAFE_ATTRIBUTE_KEYS:
            if isinstance(v, (str, int, float, bool)):
                sanitized[k] = v
    return sanitized


@contextlib.contextmanager
def trace_span(
    operation: str, attributes: Optional[Dict[str, Any]] = None
) -> Generator[Dict[str, Any], None, None]:
    """
    Context manager for distributed tracing spans.
    When settings.otel_enabled is False (default), behaves as a zero-cost no-op.
    When enabled, records bounded metadata to captured_spans or active tracer.
    """
    if not settings.otel_enabled:
        yield {}
        return

    start_time = time.perf_counter()
    safe_attrs = sanitize_span_attributes(attributes)
    safe_attrs["operation"] = operation
    safe_attrs["request_id"] = get_request_id()

    span_record: Dict[str, Any] = {
        "operation": operation,
        "start_time": start_time,
        "attributes": safe_attrs,
        "status": "active",
    }

    try:
        yield span_record
        span_record["status"] = "ok"
    except Exception as exc:
        span_record["status"] = "error"
        span_record["error_type"] = exc.__class__.__name__
        raise
    finally:
        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        span_record["duration_ms"] = duration_ms
        span_record["attributes"]["duration_ms"] = duration_ms
        captured_spans.append(span_record)
