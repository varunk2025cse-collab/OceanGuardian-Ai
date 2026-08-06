import pytest
from datetime import datetime
from unittest.mock import Mock, patch

from app.models.phase5 import Harbor
from app.models.sos import SOSAlert, SOSStatus
from app.models.user import User, UserRole
from app.services.intelligence.sos_intelligence import SOSIntelligenceService


@pytest.fixture
def fisherman(db):
    from app.models.user import User, UserRole

    u = User(
        phone_number="+919876500001",
        password_hash="x",
        full_name="Murugan",
        role=UserRole.fisherman,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def make_alert(db, fisherman, alert_type="medical", battery=50, accuracy=10):
    alert = SOSAlert(
        user_id=fisherman.id,
        alert_type=alert_type,
        triggered_at=datetime.utcnow(),
        latitude=10.5,
        longitude=79.8,
        battery_level_percent=battery,
        accuracy_meters=accuracy,
        status=SOSStatus.active,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert


def test_all_sos_types_return_tamil_fields(db, fisherman):
    for alert_type in ["medical", "sinking", "piracy", "engine_failure", "weather", "fire", "man_overboard"]:
        alert = make_alert(db, fisherman, alert_type=alert_type)
        report = SOSIntelligenceService.evaluate(db, alert)
        assert report.severity_reason_ta
        assert report.resource_recommendation_ta
        assert report.fisherman_message_ta
        assert report.priority_label_ta
        assert report.status_ta
        assert report.rescue_time_ta


def test_tamil_battery_and_gps_warnings_are_visible(db, fisherman):
    alert = make_alert(db, fisherman, alert_type="engine_failure", battery=10, accuracy=300)
    report = SOSIntelligenceService.evaluate(db, alert)
    assert "தொடர்பு" in report.severity_assessment.reason
    assert "துல்லியம்" in report.severity_assessment.reason
    assert "battery" in report.severity_assessment.reason.lower()


def test_rescue_time_ta_uses_harbor_when_available(db, fisherman):
    harbor = Harbor(name="Tuticorin", latitude=10.5, longitude=79.8)
    db.add(harbor)
    db.commit()
    alert = make_alert(db, fisherman, alert_type="medical")
    report = SOSIntelligenceService.evaluate(db, alert)
    assert report.rescue_time_ta != "தூரம் தெரியவில்லை"


def test_rescue_time_ta_is_unknown_when_no_harbor(db, fisherman):
    alert = make_alert(
        db,
        fisherman,
        alert_type="weather",
        battery=50,
        accuracy=10,
    )
    alert.latitude = -33.9
    alert.longitude = -151.2
    db.commit()
    db.refresh(alert)

    report = SOSIntelligenceService.evaluate(db, alert)
    assert report.rescue_time_ta == "தூரம் தெரியவில்லை"


def test_priority_and_status_labels_are_tamil(db, fisherman):
    alert = make_alert(db, fisherman, alert_type="medical")
    report = SOSIntelligenceService.evaluate(db, alert)
    assert report.priority_label_ta == "மிக அவசரம்"
    assert report.status_ta == "செயலில் உள்ளது"


def test_unknown_sos_type_falls_back_gracefully(db, fisherman):
    alert = make_alert(db, fisherman, alert_type="unknown")
    report = SOSIntelligenceService.evaluate(db, alert)
    assert report.severity_reason_ta
    assert report.resource_recommendation_ta
    assert report.fisherman_message_ta
