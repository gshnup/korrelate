# ~/korrelate/korrelate/clients/prometheus.py

import logging
from datetime import datetime, timedelta
from typing import Any

import httpx

logger = logging.getLogger(__name__)


async def query_range(base_url: str, promql: str, minutes: int = 10) -> list[dict]:
    end = datetime.utcnow()
    start = end - timedelta(minutes=minutes)
    params = {
        "query": promql,
        "start": start.isoformat() + "Z",
        "end": end.isoformat() + "Z",
        "step": "30s",
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base_url}/api/v1/query_range", params=params)
            r.raise_for_status()
            data = r.json()
            results = data.get("data", {}).get("result", [])
            if not results:
                return []
            return [
                {"timestamp": float(ts), "value": float(val)}
                for ts, val in results[0].get("values", [])
            ]
    except Exception as e:
        logger.error(f"Prometheus query failed: {e}")
        return []


async def get_metrics(base_url: str, service: str) -> dict[str, Any]:
    logger.info(f"Querying Prometheus for service={service}")
    error_rate = await query_range(
        base_url,
        f'rate(flask_http_request_total{{status=~"5..",job=~".*{service}.*"}}[2m])',
    )
    request_rate = await query_range(
        base_url,
        f'rate(flask_http_request_total{{job=~".*{service}.*"}}[2m])',
    )
    p99_latency = await query_range(
        base_url,
        f'histogram_quantile(0.99, rate(flask_http_request_duration_seconds_bucket{{job=~".*{service}.*"}}[2m]))',
    )

    # Fallback: if service-specific queries return nothing, grab global error rate
    if not error_rate:
        logger.warning("Service-specific query empty, falling back to global error rate")
        error_rate = await query_range(
            base_url,
            'rate(flask_http_request_total{status=~"5.."}[2m])',
        )
    if not request_rate:
        request_rate = await query_range(
            base_url,
            'rate(flask_http_request_total[2m])',
        )

    return {
        "error_rate": error_rate,
        "request_rate": request_rate,
        "p99_latency": p99_latency,
    }
