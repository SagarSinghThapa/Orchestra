import math
from typing import Dict, List


def compute_nearest_rank_percentile(latencies: List[float], percentile: float) -> float:
    """
    Computes percentile using the deterministic nearest-rank method on sorted latencies.
    Formula: rank = ceil((p / 100) * N), 1-indexed.
    """
    if not latencies:
        return 0.0
    sorted_l = sorted(latencies)
    n = len(sorted_l)
    rank = math.ceil((percentile / 100.0) * n)
    idx = max(0, min(n - 1, rank - 1))
    return sorted_l[idx]


def compute_latency_summary(latencies: List[float]) -> Dict[str, float]:
    """
    Computes standard latency summary metrics (P50, P95, mean, max).
    """
    if not latencies:
        return {
            "latency_p50_ms": 0.0,
            "latency_p95_ms": 0.0,
            "latency_mean_ms": 0.0,
            "latency_max_ms": 0.0,
        }

    return {
        "latency_p50_ms": compute_nearest_rank_percentile(latencies, 50.0),
        "latency_p95_ms": compute_nearest_rank_percentile(latencies, 95.0),
        "latency_mean_ms": sum(latencies) / len(latencies),
        "latency_max_ms": max(latencies),
    }
