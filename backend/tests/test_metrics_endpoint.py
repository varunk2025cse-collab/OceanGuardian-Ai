from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_metrics_endpoint_available():
    r = client.get("/metrics")
    assert r.status_code == 200
    assert "og_events_published_total" in r.text
