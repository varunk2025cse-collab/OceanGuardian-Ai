import os
import pytest

from app.notifications import provider_registry


def test_simulation_provider_send_and_health():
    sim = provider_registry.get_provider("simulation")
    assert sim is not None
    # send should succeed and return ok True
    res = sim.send(to="+15551234567", template="Hello {name}", context={"name": "Alice"})
    assert isinstance(res, dict)
    assert res.get("ok") is True

    health = sim.health_check()
    assert isinstance(health, dict)
    assert health.get("ok") is True


def test_list_providers_contains_simulation():
    names = provider_registry.list_providers()
    assert "simulation" in names


def test_provider_health_aggregated():
    h = provider_registry.provider_health()
    assert isinstance(h, dict)
    assert "simulation" in h
    assert h["simulation"].get("ok") is True


def test_twilio_provider_not_configured_by_default(monkeypatch):
    # ensure env vars are not set to simulate default dev environment
    monkeypatch.delenv("TWILIO_ACCOUNT_SID", raising=False)
    monkeypatch.delenv("TWILIO_AUTH_TOKEN", raising=False)
    monkeypatch.delenv("TWILIO_FROM_NUMBER", raising=False)

    tw = provider_registry.get_provider("twilio")
    # Twilio provider is registered as a scaffold but likely not configured
    assert tw is not None
    h = tw.health_check()
    assert isinstance(h, dict)
    assert h.get("configured") is False or h.get("ok") is False

    # send should raise RuntimeError when not configured
    with pytest.raises(RuntimeError):
        tw.send(to="+15551234567", template="Hi", context={})
