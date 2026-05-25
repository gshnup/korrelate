# Korrelate

AI-powered incident correlation engine. Prometheus fires → Korrelate thinks → Slack knows.

---

## Architecture

When an alert fires, Korrelate has 60 seconds to pull metrics from Prometheus, 
pull logs from Loki, bundle the context, call a local LLM, and post a structured 
root cause diagnosis to Slack. No cloud LLMs. No alert fatigue. Just signal.

---

## Step 1 — Slack Webhook

**What it does:** Provides the output channel for all incident diagnosis cards.
Korrelate POSTs structured Block Kit JSON to this endpoint at pipeline completion.

**Why Incoming Webhooks over the full Slack API:** No token refresh, no OAuth,
no bot user management. A webhook is a signed URL — deterministic, stateless,
exactly right for a fire-and-forget notifier.

**Verification:**
```bash
source .env
curl -s -X POST "$SLACK_WEBHOOK_URL" \
  -H 'Content-type: application/json' \
  -d '{"text": "webhook live"}' | cat
# Expected: ok
```

