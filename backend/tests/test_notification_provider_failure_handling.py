"""
Notification provider verification (Final Release Engineering Phase E).

No Twilio credentials exist in this environment — see
docs/NOTIFICATIONS.md. As with the AI provider, what's verified here is
the contract that matters most: TwilioSmsProvider must never raise, must
report an honest DeliveryResult on auth failure/timeout/outage, and the
default SimulationNotificationProvider path (what's actually running in
this build) is fully exercised without mocks at all.

`test_twilio_live_send_if_configured` is a REAL integration test — only
runs if TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN/TWILIO_FROM_NUMBER AND a
TWILIO_TEST_TO_NUMBER are all set (a safe, explicit opt-in recipient —
this test will never message an arbitrary/real user by default). Skipped
otherwise, never faked as passing.
"""
import os
from unittest.mock import MagicMock, patch

import pytest

from app.database import SessionLocal
from app.models.phase5 import FamilyNotification
from app.models.family_link import FamilyLink
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.notification_service import (
    NotificationEngine,
    NotificationPriority,
    SimulationNotificationProvider,
    TwilioSmsProvider,
)


def test_simulation_provider_never_claims_real_delivery():
    result = SimulationNotificationProvider().send(to_user_id=1, message="test", priority=NotificationPriority.high)
    assert result.status == "simulated"
    assert result.simulated is True


@patch("httpx.Client")
def test_twilio_provider_reports_failure_on_auth_error(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.text = "Authentication error"
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = TwilioSmsProvider.__new__(TwilioSmsProvider)  # skip __init__'s real httpx.Client() construction
    provider._client = mock_client
    provider._sid = "fake-sid"
    provider._token = "fake-token"
    provider._from = "+10000000000"

    result = provider.send_sms(to_phone="+919999999999", message="test")
    assert result.status == "failed"
    assert result.simulated is False
    assert "401" in result.detail


@patch("httpx.Client")
def test_twilio_provider_reports_failure_on_timeout(mock_client_cls):
    import httpx

    mock_client = MagicMock()
    mock_client.post.side_effect = httpx.TimeoutException("timed out")
    mock_client_cls.return_value = mock_client

    provider = TwilioSmsProvider.__new__(TwilioSmsProvider)
    provider._client = mock_client
    provider._sid = "fake-sid"
    provider._token = "fake-token"
    provider._from = "+10000000000"

    result = provider.send_sms(to_phone="+919999999999", message="test")
    assert result.status == "failed"
    assert "timed out" in result.detail.lower()


@patch("httpx.Client")
def test_twilio_provider_reports_success(mock_client_cls):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.status_code = 201
    mock_client.post.return_value = mock_response
    mock_client_cls.return_value = mock_client

    provider = TwilioSmsProvider.__new__(TwilioSmsProvider)
    provider._client = mock_client
    provider._sid = "fake-sid"
    provider._token = "fake-token"
    provider._from = "+10000000000"

    result = provider.send_sms(to_phone="+919999999999", message="test")
    assert result.status == "sent"
    assert result.simulated is False


def test_notification_engine_deduplicates_by_related_event_id(db):
    fisherman = User(phone_number="+912500000001", password_hash=hash_password("x"),
                      full_name="Notif Dedup Fisher", role=UserRole.fisherman, preferred_language="en")
    family = User(phone_number="+912500000002", password_hash=hash_password("x"),
                   full_name="Notif Dedup Family", role=UserRole.family, preferred_language="en")
    db.add_all([fisherman, family]); db.commit()
    db.add(FamilyLink(fisherman_id=fisherman.id, family_user_id=family.id, relation="Wife")); db.commit()

    first = NotificationEngine.notify_family_of_event(db, fisherman.id, "Event A", related_event_id=999)
    second = NotificationEngine.notify_family_of_event(db, fisherman.id, "Event A duplicate call", related_event_id=999)

    assert len(first) == 1
    assert len(second) == 1
    assert first[0].id == second[0].id  # same row reused, not a new one

    rows = db.query(FamilyNotification).filter(FamilyNotification.related_event_id == 999).all()
    assert len(rows) == 1  # no duplicate notification created


@pytest.mark.skipif(
    not (os.environ.get("TWILIO_ACCOUNT_SID") and os.environ.get("TWILIO_AUTH_TOKEN")
         and os.environ.get("TWILIO_FROM_NUMBER") and os.environ.get("TWILIO_TEST_TO_NUMBER")),
    reason="Twilio credentials + an explicit TWILIO_TEST_TO_NUMBER not set — real Twilio integration is UNVERIFIED (docs/NOTIFICATIONS.md)",
)
def test_twilio_live_send_if_configured():
    provider = TwilioSmsProvider()
    result = provider.send_sms(to_phone=os.environ["TWILIO_TEST_TO_NUMBER"], message="OceanGuardian verification test message.")
    assert result.status == "sent"
