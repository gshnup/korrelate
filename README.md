# Korrelate
### AI-Powered Incident Correlation Engine

> Automatically diagnoses production failures by correlating metrics, logs, traces, git commits, and deployment history — then posts a root cause hypothesis to Slack within 60 seconds of an alert firing.

![Phase](https://img.shields.io/badge/Phase-1%20Complete-brightgreen)
![Stack](https://img.shields.io/badge/Stack-Kubernetes%20%7C%20Prometheus%20%7C%20Loki%20%7C%20Grafana-blue)
![License](https://img.shields.io/badge/License-MIT-lightgrey)

---

## What Problem Phase 1 Solves

When production breaks at 3am, engineers wake up blind. They manually open Grafana, search logs, cross-reference deployments, and form a hypothesis — all while the incident is live.

**Phase 1 builds the foundation** — a fully instrumented local observability stack with a deliberately broken sample app that generates real alerts and logs. This gives Korrelate (Phase 2) the data sources it needs to correlate signals and diagnose incidents automatically.

---

## Architecture

\`\`\`mermaid
flowchart TD
    A[PaymentService :8088] -->|scrape /metrics every 15s| B[Prometheus :9090]
    A -->|structured JSON logs| C[Promtail]
    C -->|ship logs| D[Loki]
    B -->|evaluate alert rules| E[Alertmanager :9093]
    B -->|visualize metrics| F[Grafana :3000]
    D -->|visualize logs| F
    E -->|webhook - Phase 2| G[Korrelate Engine]
    G -->|query signals| B
    G -->|query logs| D
    G -->|root cause hypothesis| H[Slack]
\`\`\`

---

## Stack

| Component | Purpose | Version |
|---|---|---|
| kind | Local Kubernetes cluster | v0.23.0 |
| kube-prometheus-stack | Prometheus + Alertmanager + Grafana | latest |
| Loki | Log aggregation | 2.9.6 (chart 5.47.2) |
| Promtail | Log shipping agent | 3.5.1 |
| paymentservice | Sample broken Flask app | v1 |

---

## Prerequisites

| Tool | Install |
|---|---|
| Docker Desktop (WSL2 mode) | [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) |
| kind | `curl -Lo ./kind https://kind.sigs.k8s.io/dl/v0.23.0/kind-linux-amd64 && chmod +x ./kind && sudo mv ./kind /usr/local/bin/kind` |
| kubectl | `curl -LO "https://dl.k8s.io/release/$(curl -L -s https://dl.k8s.io/release/stable.txt)/bin/linux/amd64/kubectl" && chmod +x kubectl && sudo mv kubectl /usr/local/bin/kubectl` |
| Helm | `curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 \| bash` |

> **WSL2 note:** Run all commands inside WSL Ubuntu terminal. Enable Docker Desktop WSL2 integration under Settings → Resources → WSL Integration.

---

## Quick Start

### 1. Create the kind cluster

\`\`\`bash
kind create cluster --config kind-config.yaml
\`\`\`

### 2. Install Prometheus + Alertmanager + Grafana

\`\`\`bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update
kubectl create namespace monitoring
helm install kube-prometheus-stack prometheus-community/kube-prometheus-stack \
  --namespace monitoring \
  --values prometheus-values.yaml \
  --wait --timeout 10m
\`\`\`

### 3. Install Loki + Promtail

\`\`\`bash
helm repo add grafana https://grafana.github.io/helm-charts
helm install loki grafana/loki --namespace monitoring --version 5.47.2 \
  --set loki.auth_enabled=false \
  --set loki.useTestSchema=true \
  --set singleBinary.replicas=1 \
  --set singleBinary.persistence.enabled=true \
  --set singleBinary.persistence.storageClass=standard \
  --set singleBinary.persistence.size=2Gi \
  --set read.replicas=0 --set write.replicas=0 --set backend.replicas=0 \
  --set monitoring.selfMonitoring.enabled=false \
  --set monitoring.selfMonitoring.grafanaAgent.installOperator=false \
  --set monitoring.lokiCanary.enabled=false \
  --set test.enabled=false --set gateway.enabled=false
helm install promtail grafana/promtail --namespace monitoring \
  --set config.clients[0].url=http://loki:3100/loki/api/v1/push
\`\`\`

### 4. Deploy paymentservice

\`\`\`bash
cd paymentservice
docker build -t paymentservice:v1 .
kind load docker-image paymentservice:v1 --name korrelate-dev
kubectl apply -f deployment.yaml
kubectl apply -f alert-rule.yaml
\`\`\`

### 5. Trigger and verify

\`\`\`bash
for i in $(seq 1 300); do curl -s http://localhost:8088/crash > /dev/null; sleep 0.2; done
\`\`\`

---

## Service URLs

| Service | URL | Credentials |
|---|---|---|
| Grafana | http://localhost:3000 | admin / korrelate123 |
| Prometheus | http://localhost:9090 | — |
| Alertmanager | http://localhost:9093 | — |
| PaymentService | http://localhost:8088 | — |

---

## Verification Checklist

- [ ] All 3 nodes show `Ready`
- [ ] No pods in `Error` or `CrashLoopBackOff`
- [ ] Grafana loads at localhost:3000
- [ ] Loki datasource visible in Grafana Explore
- [ ] `paymentservice_requests_total` metric exists in Prometheus
- [ ] `PaymentServiceHighErrorRate` rule loaded in Prometheus Alerts tab
- [ ] Alert flips to `firing` after hitting `/crash` for 60+ seconds

---

## Useful Queries

**Prometheus — error rate:**
\`\`\`promql
rate(paymentservice_requests_total{status_code="500"}[1m])
/
rate(paymentservice_requests_total[1m])
\`\`\`

**Loki — error logs:**
\`\`\`logql
{namespace="default"} |= "Cascade failure"
\`\`\`

---

## Project Structure

\`\`\`
~/korrelate/
├── kind-config.yaml
├── prometheus-values.yaml
├── loki-values.yaml
├── loki-datasource.yaml
└── paymentservice/
    ├── app.py
    ├── requirements.txt
    ├── Dockerfile
    ├── deployment.yaml
    └── alert-rule.yaml
\`\`\`

---

## Screenshots

> **Grafana Dashboard**
> `[ screenshot — error rate spike ]`

> **Alert Firing**
> `[ screenshot — PaymentServiceHighErrorRate firing ]`

> **Loki Logs**
> `[ screenshot — Cascade failure log stream ]`

---

## What's Next — Phase 2

| Phase | What Gets Built |
|---|---|
| **Phase 2** | Korrelate engine — receives Alertmanager webhook, queries Prometheus + Loki, calls Claude API, posts root cause to Slack in <60s |
| **Phase 3** | Git + deployment correlation |
| **Phase 4** | Trace correlation with Tempo/Jaeger |
| **Phase 5** | Production hardening — multi-cluster, real storage, RBAC |

---

*Built with ☕ and too many Helm chart version conflicts.*
