# ~/korrelate/korrelate/llm.py

import json
import logging
import re
import time
from typing import Any

import httpx

logger = logging.getLogger(__name__)

PROMPT_TEMPLATE = """\
You are an SRE incident analysis engine. Analyze the following incident data and return ONLY a JSON object — no explanation, no markdown, no code fences.

INCIDENT DATA:
{context}

Return exactly this JSON structure:
{{
  "root_cause": "<1-2 sentences, specific, based on the data>",
  "confidence": "<high|medium|low>",
  "evidence": ["<data point 1>", "<data point 2>", "<data point 3>"],
  "fix": "<single actionable step an engineer should take right now>",
  "severity_assessment": "<one sentence on blast radius and user impact>",
  "time_to_resolve_estimate": "<realistic estimate e.g. 15 minutes, 2 hours>"
}}
"""


def _extract_json(raw: str) -> dict[str, Any]:
    # Strip markdown fences if model ignored instructions
    cleaned = re.sub(r"```(?:json)?|```", "", raw).strip()
    # Find first { ... } block
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if match:
        return json.loads(match.group())
    raise ValueError("No JSON object found in LLM response")


async def diagnose(ollama_url: str, model: str, context_bundle: dict[str, Any]) -> dict[str, Any]:
    # Trim bundle for LLM — send summary + logs, not full metric arrays
    llm_context = {
        "alert": context_bundle["alert"],
        "summary": context_bundle["summary"],
        "most_frequent_error": context_bundle["logs"]["most_frequent_error"],
        "error_count": context_bundle["logs"]["error_count"],
        "recent_error_logs": [
            e["line"] for e in context_bundle["logs"]["entries"][:10]
        ],
        "peak_error_rate": context_bundle["summary"]["peak_error_rate"],
        "service_healthy_before_alert": context_bundle["summary"]["service_healthy_before_alert"],
    }

    prompt = PROMPT_TEMPLATE.format(context=json.dumps(llm_context, indent=2))

    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,  # Low temp = deterministic, structured output
            "num_predict": 512,
        },
    }

    t0 = time.time()
    try:
        async with httpx.AsyncClient(timeout=55) as client:
            r = await client.post(f"{ollama_url}/api/generate", json=payload)
            r.raise_for_status()
            raw = r.json().get("response", "")
            elapsed = time.time() - t0
            logger.info(f"Ollama responded in {elapsed:.2f}s")

            try:
                result = _extract_json(raw)
                logger.info(f"LLM diagnosis: confidence={result.get('confidence')} root_cause={result.get('root_cause','')[:80]}")
                return result
            except (ValueError, json.JSONDecodeError) as e:
                logger.warning(f"JSON parse failed ({e}), returning raw text fallback")
                return {
                    "root_cause": raw[:300],
                    "confidence": "low",
                    "evidence": [],
                    "fix": "Manual investigation required",
                    "severity_assessment": "Unknown",
                    "time_to_resolve_estimate": "Unknown",
                }
    except Exception as e:
        elapsed = time.time() - t0
        logger.error(f"Ollama call failed after {elapsed:.2f}s: {e}")
        return {
            "root_cause": f"LLM unavailable: {e}",
            "confidence": "low",
            "evidence": [],
            "fix": "Check Ollama service at localhost:11434",
            "severity_assessment": "Unknown",
            "time_to_resolve_estimate": "Unknown",
        }
