# ~/korrelate/korrelate/bundler.py

import logging
from collections import Counter
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


def bundle(
    alert: dict[str, Any],
    metrics: dict[str, Any],
    logs: list[dict[str, Any]],
) -> dict[str, Any]:

    error_rate_values = [p["value"] for p in metrics.get("error_rate", [])]
    request_rate_values = [p["value"] for p in metrics.get("request_rate", [])]
    peak_error_rate = max(error_rate_values, default=0.0)
    avg_request_rate = (
        sum(request_rate_values) / len(request_rate_values) if request_rate_values else 0.0
    )

    # Was service healthy before the alert? 
    # Heuristic: first 20% of error_rate window was near zero
    early_errors = error_rate_values[: max(1, len(error_rate_values) // 5)]
    service_healthy_before = all(v < 0.01 for v in early_errors)

    log_lines = [e["line"] for e in logs]
    most_frequent = ""
    if log_lines:
        # Use first 60 chars of each line as a fingerprint
        fingerprints = [l[:60] for l in log_lines]
        most_frequent = Counter(fingerprints).most_common(1)[0][0]

    bundle = {
        "alert": {
            "name": alert.get("name", "unknown"),
            "service": alert.get("service", "unknown"),
            "severity": alert.get("severity", "unknown"),
            "fired_at": alert.get("fired_at", datetime.utcnow().isoformat()),
            "description": alert.get("description", ""),
        },
        "metrics": {
            "error_rate": metrics.get("error_rate", []),
            "request_rate": metrics.get("request_rate", []),
            "p99_latency": metrics.get("p99_latency", []),
        },
        "logs": {
            "error_count": len(logs),
            "entries": logs[:20],  # cap at 20 for LLM context size
            "most_frequent_error": most_frequent,
        },
        "summary": {
            "peak_error_rate": round(peak_error_rate, 4),
            "avg_request_rate": round(avg_request_rate, 4),
            "total_errors_10min": len(logs),
            "service_healthy_before_alert": service_healthy_before,
        },
    }

    logger.info(
        f"Bundle ready — peak_error_rate={peak_error_rate:.4f} "
        f"log_entries={len(logs)} healthy_before={service_healthy_before}"
    )
    return bundle
