# ~/korrelate/korrelate/notifier.py

import logging
from typing import Any

import httpx

logger = logging.getLogger(__name__)

CONFIDENCE_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}


def _build_blocks(bundle: dict[str, Any], diagnosis: dict[str, Any]) -> list[dict]:
    alert = bundle["alert"]
    summary = bundle["summary"]
    confidence = diagnosis.get("confidence", "low")
    evidence = diagnosis.get("evidence", [])

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "🚨 KORRELATE INCIDENT REPORT"},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Alert*\n{alert['name']}"},
                {"type": "mrkdwn", "text": f"*Service*\n{alert['service']}"},
                {"type": "mrkdwn", "text": f"*Severity*\n{alert['severity'].upper()}"},
                {"type": "mrkdwn", "text": f"*Fired At*\n{alert['fired_at']}"},
            ],
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*ROOT CAUSE*\n{diagnosis.get('root_cause', 'N/A')}\n\n"
                        f"Confidence: {CONFIDENCE_EMOJI.get(confidence, '⚪')} `{confidence.upper()}`",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*EVIDENCE*\n" + "\n".join(f"• {e}" for e in evidence) if evidence else "*EVIDENCE*\nNone collected",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*SUGGESTED FIX*\n{diagnosis.get('fix', 'N/A')}",
            },
        },
        {"type": "divider"},
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*SEVERITY ASSESSMENT*\n{diagnosis.get('severity_assessment', 'N/A')}",
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"⏱ Fired: {alert['fired_at']}"},
                {"type": "mrkdwn", "text": f"📊 Peak error rate: {summary['peak_error_rate']}"},
                {"type": "mrkdwn", "text": f"📋 Errors (10 min): {summary['total_errors_10min']}"},
                {"type": "mrkdwn", "text": f"🔧 Est. resolution: {diagnosis.get('time_to_resolve_estimate', 'N/A')}"},
            ],
        },
    ]


async def post(webhook_url: str, bundle: dict[str, Any], diagnosis: dict[str, Any]) -> bool:
    blocks = _build_blocks(bundle, diagnosis)
    payload = {"blocks": blocks}
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(webhook_url, json=payload)
            r.raise_for_status()
            logger.info("Slack notification posted successfully")
            return True
    except Exception as e:
        logger.error(f"Slack notification failed: {e}")
        return False
