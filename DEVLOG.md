# Korrelate DevLog

---

## Step 1 — Slack Webhook Setup

**Built:** Slack workspace, #korrelate-incidents channel, Korrelate app,
Incoming Webhook, .env with secret management, .gitignore.

**Broke:** Nothing in this step is code. The only failure mode is a
copy-paste error on the webhook URL. If curl returns anything other
than `ok`, the URL is wrong.

**Time:** ~8 minutes.

**Non-obvious insight:** Slack's Incoming Webhooks are scoped to a
*specific channel at creation time* — you cannot dynamically route
to different channels from the same webhook URL. For multi-team
alerting (e.g., #payments-oncall vs #infra-oncall), you need one
webhook per channel. Design your notifier module to support multiple
webhook URLs keyed by service or severity. Korrelate will need this
in Phase 3.

