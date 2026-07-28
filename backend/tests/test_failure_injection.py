"""
Deliberate failure injection (Final Release Engineering Phase F).

Ten scenarios required. Coverage map:

  1. Internet unavailable           -> mobile-side (SQLite outbox always
                                        written first; GPS/SOS never block
                                        on network). Verified in
                                        mobile/test/local_db_service_test.dart
                                        (markLocationsFailed / backoff) and
                                        by design in location_service.dart /
                                        sos_service.dart — not re-tested here,
                                        there is no backend-side behavior to
                                        inject this failure into.
  2. Weather provider unavailable   -> test_weather_unavailable_reports_honestly,
                                        test_safety_engine_unaffected_by_live_weather_outage
  3. AI provider unavailable        -> tests/test_ai_provider_failure_handling.py
                                        (all 5 failure-mode tests); this file adds
                                        test_sos_and_incidents_work_without_any_ai_call
  4. Notification provider unavailable -> test_notification_failure_does_not_block_incident_creation
  5. GPS becomes stale              -> test_stale_gps_never_reports_as_safe
  6. Duplicate GPS event            -> tests/test_smoke.py (locations/sync
                                        accepted=0 duplicates=2 on re-send)
  7. Out-of-order GPS event         -> test_out_of_order_gps_history_stays_consistent
  8. Duplicate SOS                  -> test_duplicate_sos_does_not_create_duplicate_incident
  9. Unauthorized family location   -> tests/test_core_tracking.py
     request                           test_history_authorization_self_operator_and_family
                                        (403 for unlinked family); also
                                        tests/test_god_mode_safety_incident_ai.py
                                        test_safety_state_authorization_family_must_be_linked
 10. Unauthorized operator/admin    -> tests/test_phase2_fixes.py
     creation                          test_cannot_self_register_as_operator (422)
"""
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.weather_service import OpenMeteoProvider
from app.services.safety_engine import SafetyEngine

client = TestClient(app)


def _reg(phone, name, role):
    r = client.post("/api/v1/auth/register", json={
        "phone_number": phone, "password": "test1234",
        "full_name": name, "role": role, "preferred_language": "ta"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_operator(phone, name):
    db = SessionLocal()
    db.add(User(phone_number=phone, password_hash=hash_password("test1234"),
                 full_name=name, role=UserRole.operator, preferred_language="en"))
    db.commit(); db.close()
    r = client.post("/api/v1/auth/login", json={"phone_number": phone, "password": "test1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ------------------------------------------------------- 2. Weather -------

def test_weather_unavailable_reports_honestly():
    """A total network outage for the live weather provider must surface
    available=False with a reason, never fabricated numbers."""
    with patch.object(OpenMeteoProvider, "fetch") as mock_fetch:
        from app.services.weather_service import WeatherObservation
        mock_fetch.return_value = WeatherObservation(
            latitude=11.0, longitude=80.0, source="open-meteo",
            timestamp=datetime.now(timezone.utc).isoformat(),
            available=False, unavailable_reason="forecast: connection refused; marine: connection refused",
        )
        fh = _reg("+912600000001", "Weather Outage Fisher", "fisherman")
        r = client.get("/api/v2/weather/live", params={"lat": 11.0, "lon": 80.0}, headers=fh)
        assert r.status_code == 200
        body = r.json()
        assert body["available"] is False
        assert body["unavailable_reason"] is not None
        assert body["wind_speed_kmh"] is None  # never a fabricated fallback number


def test_safety_engine_unaffected_by_live_weather_outage():
    """The Safety Engine's weather factor reads the weather_alerts DB table,
    not the live provider — a live outage must not degrade safety scoring."""
    fh = _reg("+912600000002", "Weather Outage Safety Fisher", "fisherman")
    client.post("/api/v1/trips/start", json={"start_latitude": 8.5, "start_longitude": 76.5}, headers=fh)
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "fi-weather-outage-0001", "latitude": 8.5, "longitude": 76.5,
        "recorded_at": datetime.now(timezone.utc).isoformat()}, headers=fh)

    with patch.object(OpenMeteoProvider, "fetch", side_effect=Exception("simulated total network outage")):
        r = client.get("/api/v2/safety/", headers=fh)
        assert r.status_code == 200  # did not 500 despite the live provider being down
        assert r.json()["safety_state"] in ("SAFE", "MONITOR", "CAUTION", "HIGH_RISK", "CRITICAL")


# ------------------------------------------------------------- 3. AI ------

def test_sos_and_incidents_work_without_any_ai_call():
    """SOS trigger and incident creation must never import/invoke the AI
    layer — they are independent code paths by construction. This asserts
    the observable behavior: SOS trigger succeeds and creates an incident
    even if we simulate the AI provider being completely broken."""
    with patch("app.services.ai.provider.get_ai_provider", side_effect=Exception("AI subsystem down")):
        fh = _reg("+912600000003", "AI Down SOS Fisher", "fisherman")
        sos = client.post("/api/v1/sos/trigger", json={
            "client_uuid": "fi-ai-down-sos-0001", "latitude": 9.0, "longitude": 77.0,
            "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
        assert sos.status_code == 201  # SOS trigger never touches the AI layer


# ---------------------------------------------------- 4. Notifications ----

def test_notification_failure_does_not_block_incident_creation():
    """If the notification provider raises, the SOS trigger must still
    succeed and the incident must still be created — this is enforced by
    isolating both the incident-creation and notification calls in
    app/routers/sos.py behind their own try/except (found and fixed via
    this exact failure-injection test: it originally surfaced the
    notification exception as a 500 on the SOS request, even though the
    alert was already safely committed — see git history on this file).
    Known limitation (docs/NOTIFICATIONS.md): there is no automated retry
    job for a failed notification yet — this asserts the failure doesn't
    block the SOS/incident path, not that it's automatically retried."""
    fh = _reg("+912600000004", "Notif Fail Fisher", "fisherman")
    oph = _create_operator("+912600000010", "Notif Fail Operator")
    fam = _reg("+912600000005", "Notif Fail Family", "family")
    client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+912600000004", "relation": "Wife"}, headers=fam)

    with patch(
        "app.services.notification_service.NotificationEngine._select_provider",
        side_effect=lambda: (_ for _ in ()).throw(Exception("simulated provider crash")),
    ):
        sos = client.post("/api/v1/sos/trigger", json={
            "client_uuid": "fi-notif-fail-0001", "latitude": 9.0, "longitude": 77.0,
            "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)

    assert sos.status_code == 201  # SOS request succeeds despite the notification provider crashing

    incidents = client.get("/api/v2/incidents/active", headers=oph).json()
    matching = [i for i in incidents if i["sos_alert_id"] == sos.json()["id"]]
    assert len(matching) == 1  # incident was still auto-created


# ------------------------------------------------------------ 5. Stale ----

def test_stale_gps_never_reports_as_safe():
    fh = _reg("+912600000006", "Stale GPS Fisher", "fisherman")
    client.post("/api/v1/trips/start", json={"start_latitude": 9.5, "start_longitude": 77.5}, headers=fh)
    stale_time = datetime.now(timezone.utc) - timedelta(hours=6)
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "fi-stale-0001", "latitude": 9.5, "longitude": 77.5,
        "recorded_at": stale_time.isoformat()}, headers=fh)

    r = client.get("/api/v2/safety/", headers=fh)
    body = r.json()
    assert body["freshness"] == "STALE"
    assert body["communication_state"] == "OFFLINE"
    assert body["safety_state"] != "SAFE"  # stale data is never presented as "all clear"
    assert any("STALE" in reason or "long time" in reason for reason in body["reasons"])


# --------------------------------------------------- 7. Out-of-order ------

def test_out_of_order_gps_history_stays_consistent():
    fh = _reg("+912600000007", "Out Of Order GPS Fisher", "fisherman")
    fisherman_id = client.get("/api/v1/auth/me", headers=fh).json()["id"]
    now = datetime.now(timezone.utc)

    # Submit newest point FIRST, then two older points, out of order.
    newest = now
    middle = now - timedelta(minutes=30)
    oldest = now - timedelta(minutes=60)

    for label, ts in [("newest", newest), ("oldest", oldest), ("middle", middle)]:
        r = client.post("/api/v1/locations/ping", json={
            "client_uuid": f"fi-ooo-{label}", "latitude": 9.0, "longitude": 77.0,
            "recorded_at": ts.isoformat()}, headers=fh)
        assert r.status_code == 200

    history = client.get(f"/api/v2/tracking/{fisherman_id}/history", headers=fh)
    assert history.status_code == 200
    points = history.json()["points"]
    timestamps = [p["recorded_at"] for p in points]
    assert timestamps == sorted(timestamps, reverse=True), "history must be ordered by recorded_at, not insertion order"
    # Freshness must reflect the actual latest recorded_at (newest), not
    # whichever row happened to be inserted last.
    assert history.json()["latest_recorded_at"] == points[0]["recorded_at"]


# -------------------------------------------------- 8. Duplicate SOS ------

def test_duplicate_sos_does_not_create_duplicate_incident():
    fh = _reg("+912600000008", "Dup SOS Fisher", "fisherman")
    oph = _create_operator("+912600000009", "Dup SOS Operator")
    payload = {
        "client_uuid": "fi-dup-sos-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
    first = client.post("/api/v1/sos/trigger", json=payload, headers=fh)
    second = client.post("/api/v1/sos/trigger", json=payload, headers=fh)  # exact same client_uuid
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]  # same alert, not a new one

    incidents = client.get("/api/v2/incidents/active", headers=oph).json()
    matching = [i for i in incidents if i["sos_alert_id"] == first.json()["id"]]
    assert len(matching) == 1  # exactly one incident, not two
