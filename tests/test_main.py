from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from korrelate.main import app

client = TestClient(app)

def test_health_returns_200():
    response = client.get("/health")
    assert response.status_code == 200

def test_webhook_empty_alerts():
    response = client.post("/webhook", json={"alerts": []})
    assert response.status_code == 200

def test_deduplication():
    from korrelate.main import seen_alerts
    seen_alerts.clear()

    payload = {"alerts": [{
        "status": "firing",
        "labels": {"alertname": "PaymentServiceHighErrorRate", "job": "paymentservice"},
        "annotations": {"summary": "High error rate"},
        "startsAt": "2024-01-01T00:00:00Z"
    }]}

    with patch("korrelate.main.run_pipeline", new_callable=AsyncMock):
        r1 = client.post("/webhook", json=payload)
        r2 = client.post("/webhook", json=payload)

    assert r1.json()["status"] == "accepted"
    assert r2.json()["status"] == "deduplicated"
