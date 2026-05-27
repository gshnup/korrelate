# ~/korrelate/korrelate/clients/loki.py

import logging
from datetime import datetime, timedelta
from typing import Any
import httpx

logger = logging.getLogger(__name__)


async def get_logs(base_url: str, service: str, limit: int = 50) -> list[dict[str, Any]]:
    end = datetime.utcnow()
    start = end - timedelta(minutes=10)

    params = {
        "query": f'{{app="{service}"}} |~ "(?i)(error|critical|exception|traceback|500)"',
        "start": str(int(start.timestamp() * 1e9)),
        "end": str(int(end.timestamp() * 1e9)),
        "limit": limit,
        "direction": "backward",
    }

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(f"{base_url}/loki/api/v1/query_range", params=params)
            r.raise_for_status()
            data = r.json()
            streams = data.get("data", {}).get("result", [])
            entries = []
            for stream in streams:
                for ts, line in stream.get("values", []):
                    entries.append({
                        "timestamp": int(ts) / 1e9,
                        "line": line,
                        "labels": stream.get("stream", {}),
                    })
            entries.sort(key=lambda x: x["timestamp"], reverse=True)
            logger.info(f"Loki returned {len(entries)} error log entries for {service}")
            return entries[:limit]
    except Exception as e:
        logger.error(f"Loki query failed: {e}")
        return []
