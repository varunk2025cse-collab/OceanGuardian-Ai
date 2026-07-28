"""
V2 core build "GOD MODE" phases 9-15, 18, 20: Safety State Engine,
Weather Intelligence, Incident Engine, SOS 2.0, AI explainability/tools,
Notification Engine. See docs/GOD_MODE_STATUS.md.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.safety_engine import SafetyEngine, SafetyState
from app.services.weather_service import SimulatedProvider
from app.services.early_warning import evaluate as evaluate_early_warning

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


def _me(headers):
    return client.get("/api/v1/auth/me", headers=headers).json()


# ---------------------------------------------------------------- Safety ---

def test_safety_state_unknown_with_no_trip():
    fh = _reg("+912400000001", "Safety NoTrip", "fisherman")
    r = client.get("/api/v2/safety/", headers=fh)
    assert r.status_code == 200
    assert r.json()["safety_state"] == "UNKNOWN"


def test_safety_state_safe_with_fresh_location_and_trip():
    fh = _reg("+912400000002", "Safety Safe", "fisherman")
    client.post("/api/v1/trips/start", json={"start_latitude": 8.0, "start_longitude": 76.0}, headers=fh)
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "gm-safe-0001", "latitude": 8.0, "longitude": 76.0,
        "recorded_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    r = client.get("/api/v2/safety/", headers=fh)
    assert r.status_code == 200
    body = r.json()
    assert body["communication_state"] == "ONLINE"
    assert body["safety_state"] in ("SAFE", "MONITOR")  # depends on any active weather alerts near this point


def test_safety_state_critical_with_active_sos():
    fh = _reg("+912400000003", "Safety SOS", "fisherman")
    client.post("/api/v1/trips/start", json={"start_latitude": 9.0, "start_longitude": 77.0}, headers=fh)
    client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-sos-critical-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    r = client.get("/api/v2/safety/", headers=fh)
    assert r.status_code == 200
    assert r.json()["safety_state"] == SafetyState.CRITICAL
    assert r.json()["safety_score"] == 100


def test_safety_state_authorization_family_must_be_linked():
    fh = _reg("+912400000004", "Safety Auth Fisher", "fisherman")
    fam_linked = _reg("+912400000005", "Safety Auth Family Linked", "family")
    fam_unlinked = _reg("+912400000006", "Safety Auth Family Unlinked", "family")
    oph = _create_operator("+912400000007", "Safety Auth Operator")
    fisherman_id = _me(fh)["id"]

    assert client.get(f"/api/v2/safety/{fisherman_id}", headers=fam_unlinked).status_code == 403
    assert client.get(f"/api/v2/safety/{fisherman_id}", headers=oph).status_code == 200

    client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+912400000004", "relation": "Sister"}, headers=fam_linked)
    assert client.get(f"/api/v2/safety/{fisherman_id}", headers=fam_linked).status_code == 200


def test_early_warning_fires_on_multiple_combined_factors():
    """Pure unit test on the classifier itself (docs honesty note: this is
    a snapshot classifier, not a trend detector)."""
    from app.services.safety_engine import SafetyEvaluation

    ev = SafetyEvaluation(
        fisherman_id=1, safety_state="HIGH_RISK", safety_score=70,
        communication_state="OFFLINE", freshness="STALE",
        reasons=["Active weather advisory nearby.", "Location has not updated in a long time (STALE).",
                 "Vessel is far from the nearest known harbor (~55km)."],
        trip_status="active", evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
    warning = evaluate_early_warning(ev)
    assert warning.is_early_warning is True
    assert len(warning.categories) >= 2


def test_early_warning_does_not_fire_on_single_factor():
    from app.services.safety_engine import SafetyEvaluation

    ev = SafetyEvaluation(
        fisherman_id=1, safety_state="MONITOR", safety_score=25,
        communication_state="ONLINE", freshness="RECENT",
        reasons=["Active weather advisory nearby."],
        trip_status="active", evaluated_at=datetime.now(timezone.utc).isoformat(),
    )
    warning = evaluate_early_warning(ev)
    assert warning.is_early_warning is False


# --------------------------------------------------------------- Weather ---

def test_simulated_weather_provider_is_deterministic_and_labeled():
    obs1 = SimulatedProvider().fetch(11.0, 80.0)
    obs2 = SimulatedProvider().fetch(11.0, 80.0)
    assert obs1.source == "SIMULATED"
    assert obs1.available is True
    assert obs1.wind_speed_kmh == obs2.wind_speed_kmh  # deterministic, not random


def test_live_weather_endpoint_returns_observation():
    fh = _reg("+912400000008", "Weather User", "fisherman")
    r = client.get("/api/v2/weather/live", params={"lat": 11.0, "lon": 80.0}, headers=fh)
    assert r.status_code == 200
    body = r.json()
    assert body["latitude"] is not None
    assert body["source"] in ("open-meteo", "SIMULATED")
    # available=False is an acceptable outcome (provider unreachable in this
    # environment) but the field must always be a real boolean, never omitted.
    assert isinstance(body["available"], bool)


# --------------------------------------------------------------- SOS 2.0 ---

def test_sos_rejects_unknown_emergency_type():
    fh = _reg("+912400000009", "SOS Taxonomy", "fisherman")
    r = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-sos-badtype-0001", "latitude": 9.0, "longitude": 77.0,
        "alert_type": "ALIEN_INVASION", "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    assert r.status_code == 422


def test_sos_accepts_valid_emergency_type_and_network_state():
    fh = _reg("+912400000010", "SOS Taxonomy Valid", "fisherman")
    r = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-sos-goodtype-0001", "latitude": 9.0, "longitude": 77.0,
        "alert_type": "ENGINE_FAILURE", "network_type": "OFFLINE",
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    assert r.status_code == 201
    assert r.json()["alert_type"] == "ENGINE_FAILURE"
    assert r.json()["network_type"] == "OFFLINE"


# ------------------------------------------------------------- Incidents ---

def test_sos_trigger_auto_creates_incident_with_timeline():
    fh = _reg("+912400000011", "Incident Auto Fisher", "fisherman")
    oph = _create_operator("+912400000012", "Incident Auto Operator")

    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-incident-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    assert sos.status_code == 201

    active = client.get("/api/v2/incidents/active", headers=oph)
    assert active.status_code == 200
    matches = [i for i in active.json() if i["sos_alert_id"] == sos.json()["id"]]
    assert len(matches) == 1
    incident = matches[0]
    assert incident["status"] == "received"

    timeline = client.get(f"/api/v2/incidents/{incident['id']}/timeline", headers=oph)
    assert timeline.status_code == 200
    assert len(timeline.json()) == 1
    assert timeline.json()[0]["new_status"] == "received"


def test_incident_state_machine_legal_and_illegal_transitions():
    fh = _reg("+912400000013", "Incident SM Fisher", "fisherman")
    oph = _create_operator("+912400000014", "Incident SM Operator")

    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-incident-sm-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    incident_id = [i for i in client.get("/api/v2/incidents/active", headers=oph).json()
                   if i["sos_alert_id"] == sos.json()["id"]][0]["id"]

    # received -> rescue_dispatched is illegal (must acknowledge/assess first)
    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "rescue_dispatched"}, headers=oph)
    assert r.status_code == 409

    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "acknowledged", "reason": "Operator reviewing"}, headers=oph)
    assert r.status_code == 200 and r.json()["status"] == "acknowledged"

    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "rescue_dispatched"}, headers=oph)
    assert r.status_code == 200

    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "rescue_in_progress"}, headers=oph)
    assert r.status_code == 200

    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "safe", "reason": "Fisherman confirmed safe by radio"}, headers=oph)
    assert r.status_code == 200

    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "closed"}, headers=oph)
    assert r.status_code == 200 and r.json()["status"] == "closed"

    # Terminal — no further transitions.
    r = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "acknowledged"}, headers=oph)
    assert r.status_code == 409

    timeline = client.get(f"/api/v2/incidents/{incident_id}/timeline", headers=oph).json()
    assert [e["new_status"] for e in timeline] == [
        "received", "acknowledged", "rescue_dispatched", "rescue_in_progress", "safe", "closed"
    ]


def test_incident_transition_requires_operator():
    fh = _reg("+912400000015", "Incident NonOp Fisher", "fisherman")
    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-incident-nonop-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    oph = _create_operator("+912400000016", "Incident NonOp Operator")
    incident_id = [i for i in client.get("/api/v2/incidents/active", headers=oph).json()
                   if i["sos_alert_id"] == sos.json()["id"]][0]["id"]

    r = client.post(f"/api/v2/incidents/{incident_id}/transition", json={"status": "acknowledged"}, headers=fh)
    assert r.status_code == 403


def test_incident_report_contains_no_fabricated_fields():
    fh = _reg("+912400000017", "Incident Report Fisher", "fisherman")
    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-incident-report-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    oph = _create_operator("+912400000018", "Incident Report Operator")
    incident_id = [i for i in client.get("/api/v2/incidents/active", headers=oph).json()
                   if i["sos_alert_id"] == sos.json()["id"]][0]["id"]

    report = client.get(f"/api/v2/incidents/{incident_id}/report", headers=oph)
    assert report.status_code == 200
    body = report.json()
    assert body["incident_id"] == incident_id
    assert body["fisherman"]["full_name"] == "Incident Report Fisher"
    assert body["response_time_seconds"] is None  # not yet acknowledged — must be null, not guessed


# -------------------------------------------------------------- AI tools ---

def test_ai_query_active_sos_intent():
    fh = _reg("+912400000019", "AI SOS Fisher", "fisherman")
    oph = _create_operator("+912400000020", "AI SOS Operator")
    client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-ai-sos-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)

    r = client.post("/api/v2/ai/query", json={"intent": "active_sos"}, headers=oph)
    assert r.status_code == 200
    assert r.json()["data"]["count"] >= 1
    assert r.json()["provider"] is None or r.json()["provider"] == "template"


def test_ai_query_vessel_status_uses_template_provider_by_default():
    fh = _reg("+912400000021", "AI Vessel Fisher", "fisherman")
    oph = _create_operator("+912400000022", "AI Vessel Operator")
    fisherman_id = _me(fh)["id"]
    client.post("/api/v1/trips/start", json={"start_latitude": 9.0, "start_longitude": 77.0}, headers=fh)

    r = client.post("/api/v2/ai/query",
        json={"intent": "vessel_status", "fisherman_id": fisherman_id}, headers=oph)
    assert r.status_code == 200
    body = r.json()
    assert body["provider"] == "template"  # no ANTHROPIC_API_KEY configured in this environment
    assert "Safety State:" in body["answer"]
    assert "not a guarantee of safety" in body["answer"]


def test_ai_query_rejects_unrecognized_intent():
    oph = _create_operator("+912400000023", "AI Bad Intent Operator")
    r = client.post("/api/v2/ai/query", json={"intent": "does_not_exist"}, headers=oph)
    assert r.status_code == 400


def test_ai_tools_enforce_operator_authorization():
    fh = _reg("+912400000024", "AI Auth Fisher", "fisherman")
    r = client.post("/api/v2/ai/query", json={"intent": "high_risk_vessels"}, headers=fh)
    # Non-operator hits the tool's own _require_operator check -> surfaces as 403
    assert r.status_code == 403


# --------------------------------------------------------- Notifications ---

def test_sos_trigger_creates_simulated_family_notification():
    fh = _reg("+912400000025", "Notif Fisher", "fisherman")
    fam = _reg("+912400000026", "Notif Family", "family")
    client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+912400000025", "relation": "Wife"}, headers=fam)

    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "gm-notif-0001", "latitude": 9.0, "longitude": 77.0,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    assert sos.status_code == 201

    from app.database import SessionLocal
    from app.models.phase5 import FamilyNotification
    db = SessionLocal()
    rows = db.query(FamilyNotification).filter(FamilyNotification.related_event_id == sos.json()["id"]).all()
    db.close()
    assert len(rows) == 1
    assert rows[0].delivery_status == "simulated"  # honest: no real SMS/push provider configured
