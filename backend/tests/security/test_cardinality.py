import pytest
from app.core.metrics import metrics_registry, record_http_request


def test_metric_label_whitelist_and_cardinality():
    PERMITTED_LABEL_KEYS = {
        "method",
        "route",
        "status_class",
        "route_class",
        "provider",
        "status",
        "mode",
        "task_type",
        "le",
    }

    # Simulate recordings with various parameters
    for i in range(10):
        record_http_request("GET", "/projects/{project_id}/documents", 200, 0.05)
        record_http_request("POST", "/projects/{project_id}/search", 200, 0.12)

    for metric in metrics_registry.collect():
        for sample in metric.samples:
            for label_name, label_val in sample.labels.items():
                # 1. Label name must be in the approved whitelist
                assert (
                    label_name in PERMITTED_LABEL_KEYS
                ), f"Unapproved label name '{label_name}' detected in metric {metric.name}"

                # 2. Label value must not contain dynamic IDs or raw URLs
                assert not label_val.startswith("http://") and not label_val.startswith(
                    "https://"
                ), f"Raw URL detected in metric label: {label_val}"
                assert "@" not in label_val, f"Email detected in metric label: {label_val}"
