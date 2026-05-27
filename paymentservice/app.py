import random, time, logging, json, uuid
from flask import Flask, jsonify
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

class JSONFormatter(logging.Formatter):
    def format(self, record):
        return json.dumps({
            "timestamp":  self.formatTime(record),
            "level":      record.levelname,
            "service":    "paymentservice",
            "message":    record.getMessage(),
            "endpoint":   getattr(record, "endpoint", ""),
            "error_type": getattr(record, "error_type", None),
            "trace_id":   getattr(record, "trace_id", None),
            "status_code": getattr(record, "status_code", ""),
        })

handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logging.root.handlers = [handler]
logging.root.setLevel(logging.INFO)
logger = logging.getLogger("paymentservice")

REQUEST_COUNT   = Counter("paymentservice_requests_total", "Total requests", ["endpoint", "status_code"])
REQUEST_LATENCY = Histogram("paymentservice_request_latency_seconds", "Latency", ["endpoint"])
ERROR_RATE_GAUGE = Gauge("paymentservice_error_rate", "Error rate")

_recent = []
def _record(is_error):
    _recent.append(is_error)
    if len(_recent) > 50: _recent.pop(0)
    ERROR_RATE_GAUGE.set(sum(_recent) / len(_recent))

app = Flask(__name__)

@app.route("/health")
def health():
    return jsonify({"status": "ok"}), 200

@app.route("/metrics")
def metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.route("/pay")
def pay():
    start = time.time()
    tid = str(uuid.uuid4())
    if random.random() < 0.30:
        REQUEST_COUNT.labels("/pay", "500").inc()
        REQUEST_LATENCY.labels("/pay").observe(time.time() - start)
        _record(True)
        logger.error("Downstream payment processor unreachable", extra={
            "endpoint": "/pay", "error_type": "UpstreamConnectionError",
            "trace_id": tid, "status_code": 500})
        return jsonify({"error": "upstream timeout", "trace_id": tid}), 500
    REQUEST_COUNT.labels("/pay", "200").inc()
    REQUEST_LATENCY.labels("/pay").observe(time.time() - start)
    _record(False)
    logger.info("Payment success", extra={"endpoint": "/pay", "trace_id": tid, "status_code": 200})
    return jsonify({"status": "success", "txn": f"txn_{random.randint(10000,99999)}"}), 200

@app.route("/crash")
def crash():
    start = time.time()
    tid = str(uuid.uuid4())
    if random.random() < 0.95:
        REQUEST_COUNT.labels("/crash", "500").inc()
        REQUEST_LATENCY.labels("/crash").observe(time.time() - start)
        _record(True)
        logger.error("Payment gateway timeout after 30s", extra={
            "endpoint": "/crash", "error_type": "PaymentProcessingError",
            "trace_id": tid, "status_code": 500})
        return jsonify({"error": "system overload", "trace_id": tid}), 500
    REQUEST_COUNT.labels("/crash", "200").inc()
    REQUEST_LATENCY.labels("/crash").observe(time.time() - start)
    _record(False)
    return jsonify({"status": "survived"}), 200

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
