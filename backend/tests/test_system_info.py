"""System info endpoint — backs the mobile/dashboard "DEMO / SIMULATION
MODE" banner (Final Release Engineering, Phase C)."""
from fastapi.testclient import TestClient
from app.main import app
from app.config import settings

client = TestClient(app)


def test_system_info_reports_simulation_by_default():
    r = client.get("/api/v1/system-info")
    assert r.status_code == 200
    body = r.json()
    assert body["demo_mode"] is False
    assert body["ai_provider"].startswith("template")
    assert body["notification_provider"].startswith("simulation")
    # Never leaks actual secret values, only mode.
    assert "anthropic_api_key" not in str(body)
    assert "twilio_auth_token" not in str(body)


def test_system_info_reflects_demo_mode(monkeypatch):
    monkeypatch.setattr(settings, "demo_mode", True)
    r = client.get("/api/v1/system-info")
    assert r.json()["demo_mode"] is True
