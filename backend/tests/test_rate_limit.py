"""
Unit test for app.core.rate_limit — exercised directly since the app-wide
test suite runs with ENVIRONMENT=test, which deliberately disables rate
limiting (see conftest.py / app/core/rate_limit.py docstring).
"""
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.rate_limit import rate_limit, _buckets


def _fake_request(ip: str):
    req = MagicMock()
    req.client.host = ip
    return req


def test_rate_limit_blocks_after_threshold(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    _buckets.clear()
    dep = rate_limit("unit-test-key", limit=3)
    req = _fake_request("10.0.0.1")

    for _ in range(3):
        dep(req)  # should not raise

    with pytest.raises(HTTPException) as exc_info:
        dep(req)
    assert exc_info.value.status_code == 429


def test_rate_limit_is_per_client_ip(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    _buckets.clear()
    dep = rate_limit("unit-test-key-2", limit=1)

    dep(_fake_request("10.0.0.2"))  # uses up client A's quota
    dep(_fake_request("10.0.0.3"))  # client B is unaffected

    with pytest.raises(HTTPException):
        dep(_fake_request("10.0.0.2"))


def test_rate_limit_disabled_in_test_environment():
    assert settings.environment == "test"
    _buckets.clear()
    dep = rate_limit("unit-test-key-3", limit=1)
    req = _fake_request("10.0.0.4")
    for _ in range(10):
        dep(req)  # never raises regardless of count
