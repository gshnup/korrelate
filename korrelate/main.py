# ~/korrelate/korrelate/main.py

import asyncio
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

from dotenv import load_dotenv
from fastapi import FastAPI, Request, BackgroundTasks
from fastapi.responses import JSONResponse

load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), "..", ".env"))

from korrelate.clients.prometheus import get_metrics
from korrelate.clients.loki import get_logs
from korrelate import bundler, llm, notifier

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger("korrelate.main")

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
LOKI_URL       = os.getenv("LOKI_URL",       "http://localhost:3100")
OLLAMA_URL     = os.getenv("OLLAMA_URL",      "http://localhost:11434")
OLLAMA_MODEL   = os.getenv("OLLAMA_MODEL",    "mistral:7b")
SLACK_WEBHOOK  = os.getenv("SLACK_WEBHOOK_URL", "")

pipeline_status = {"last_alert": None, "last_run_seconds": None, "total_runs": 0}

# ── Deduplication ──────────────────────────────────────────────────
seen_alerts: dict[str, float] = {}
DEDUP_TTL = 300  # 5 minutes

def _dedup_key(alert: dict) -> str:
    return f"{alert['name']}::{alert['service']}"

def _is_duplicate(key: str) -> bool:
    now = time.monotonic()
    if key in seen_alerts:
        if now - seen_alerts[key] < DEDUP_TTL:
            return True
    seen_alerts[key] = now
    return False
# ──────────────────────────────────────────────────────────────────


async def run_pipeline(alert: dict[str, Any]) -> None:
    t_start = time.time()
    service = alert.get("service", "paymentservice")
    logger.info(f"Pipeline START — alert={alert['name']} service={service}")

    t1 = time.time()
    metrics = await get_metrics(PROMETHEUS_URL, service)
    logger.info(f"[{time.time()-t1:.2f}s] Metrics pulled")

    t2 = time.time()
    logs = await get_logs(LOKI_URL, service)
    logger.info(f"[{time.time()-t2:.2f}s] Logs pulled — {len(logs)} entries")

    t3 = time.time()
    context = bundler.bundle(alert, metrics, logs)
    logger.info(f"[{time.time()-t3:.2f}s] Context bundled")

    t4 = time.time()
    diagnosis = await llm.diagnose(OLLAMA_URL, OLLAMA_MODEL, context)
    logger.info(f"[{time.time()-t4:.2f}s] LLM diagnosis complete")

    t5 = time.time()
    await notifier.post(SLACK_WEBHOOK, context, diagnosis)
    logger.info(f"[{time.time()-t5:.2f}s] Slack notified")

    elapsed = time.time() - t_start
    pipeline_status["last_run_seconds"] = round(elapsed, 2)
    pipeline_status["total_runs"] += 1
    logger.info(f"Pipeline COMPLETE in {elapsed:.2f}s")


def parse_alertmanager_payload(payload: dict) -> dict[str, Any]:
    alerts = payload.get("alerts", [{}])
    first = alerts[0] if alerts else {}
    labels = first.get("labels", {})
    annotations = first.get("annotations", {})
    return {
        "name":        labels.get("alertname", "UnknownAlert"),
        "service":     labels.get("job", labels.get("service", "paymentservice")),
        "severity":    labels.get("severity", "critical"),
        "fired_at":    first.get("startsAt", datetime.utcnow().isoformat()),
        "description": annotations.get("description", annotations.get("summary", "")),
    }


app = FastAPI(title="Korrelate", version="0.2.0")


@app.post("/webhook")
async def webhook(request: Request, background_tasks: BackgroundTasks):
    payload = await request.json()
    alert = parse_alertmanager_payload(payload)
    key = _dedup_key(alert)

    if _is_duplicate(key):
        logger.info(f"DEDUPLICATED — alert={key} (TTL {DEDUP_TTL}s)")
        return JSONResponse({"status": "deduplicated", "alert": alert["name"]})

    pipeline_status["last_alert"] = alert["name"]
    logger.info(f"Webhook received: {alert['name']} severity={alert['severity']}")
    background_tasks.add_task(run_pipeline, alert)
    return JSONResponse({"status": "accepted", "alert": alert["name"]})


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "pipeline": pipeline_status,
        "config": {
            "prometheus": PROMETHEUS_URL,
            "loki": LOKI_URL,
            "ollama": OLLAMA_URL,
            "model": OLLAMA_MODEL,
            "slack_configured": bool(SLACK_WEBHOOK),
        },
    }


@app.post("/test")
async def test_pipeline(background_tasks: BackgroundTasks):
    fake_alert = {
        "name":        "PaymentServiceHighErrorRate",
        "service":     "paymentservice",
        "severity":    "critical",
        "fired_at":    datetime.utcnow().isoformat(),
        "description": "Error rate exceeded 50% for paymentservice",
    }
    pipeline_status["last_alert"] = fake_alert["name"]
    logger.info("Test pipeline triggered via /test endpoint")
    background_tasks.add_task(run_pipeline, fake_alert)
    return JSONResponse({"status": "test pipeline started", "alert": fake_alert})
