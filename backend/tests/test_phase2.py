"""Phase 2 tests: operator role, SOS security, boats, trips, risk engine. DB from conftest.py."""
from datetime import datetime, timezone, timedelta, date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.models.weather_alert import WeatherAlert, HazardSeverity, HazardType
from app.core.security import hash_password

client = TestClient(app)
FISH_PHONE = "+912200000001"
FISH2_PHONE = "+912200000009"
FAM_PHONE  = "+912200000002"
OP_PHONE   = "+912200000003"


def _reg(phone, name, role):
    r = client.post("/api/v1/auth/register", json={
        "phone_number": phone, "password": "test1234",
        "full_name": name, "role": role, "preferred_language": "ta"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_operator(phone, name):
    """Operator accounts can't self-register via the public API (security
    fix) — provision directly, the same way seed.py / an admin path would."""
    db = SessionLocal()
    db.add(User(phone_number=phone, password_hash=hash_password("test1234"),
                 full_name=name, role=UserRole.operator, preferred_language="en"))
    db.commit(); db.close()
    return _login(phone)


def _login(phone):
    r = client.post("/api/v1/auth/login", json={"phone_number": phone, "password": "test1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_operator_sos_security():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    db.add(WeatherAlert(title="Ph2 Warning", description="d",
        hazard_type=HazardType.high_waves, severity=HazardSeverity.warning,
        center_latitude=11.0, center_longitude=80.0, radius_km=150,
        valid_from=now, valid_until=now + timedelta(days=1), source="T"))
    db.commit(); db.close()

    fh  = _reg(FISH_PHONE,  "Rajan Ph2",  "fisherman")
    fh2 = _reg(FISH2_PHONE, "Other Fish",  "fisherman")
    fam = _reg(FAM_PHONE,   "Meena Ph2",  "family")
    oph = _create_operator(OP_PHONE, "Rescue Op")

    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "ph2t-sos-00001", "latitude": 11.05, "longitude": 79.85,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    assert sos.status_code == 201
    aid = sos.json()["id"]

    assert client.patch(f"/api/v1/sos/{aid}/status",
        json={"status": "false_alarm"}, headers=fam).status_code == 403
    assert client.patch(f"/api/v1/sos/{aid}/status",
        json={"status": "false_alarm"}, headers=fh2).status_code == 403
    assert client.patch(f"/api/v1/sos/{aid}/status",
        json={"status": "resolved"}, headers=fh).status_code == 403

    r = client.patch(f"/api/v1/sos/{aid}/status",
        json={"status": "false_alarm"}, headers=fh)
    assert r.status_code == 200 and r.json()["status"] == "false_alarm"

    sos2 = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "ph2t-sos-00002", "latitude": 11.1, "longitude": 79.9,
        "triggered_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    aid2 = sos2.json()["id"]

    r = client.patch(f"/api/v1/admin/sos/{aid2}/status",
        json={"status": "acknowledged", "rescue_notes": "Team dispatched", "priority": "critical"}, headers=oph)
    assert r.status_code == 200
    assert r.json()["status"] == "acknowledged"
    assert r.json()["rescue_notes"] == "Team dispatched"
    assert r.json()["acknowledged_by_user"]["full_name"] == "Rescue Op"

    r = client.patch(f"/api/v1/admin/sos/{aid2}/status",
        json={"status": "resolved", "resolved_note": "Safe"}, headers=oph)
    assert r.status_code == 200 and r.json()["resolved_by_user"]["full_name"] == "Rescue Op"


def test_operator_dashboard():
    oph = _login(OP_PHONE)
    fh  = _login(FISH_PHONE)

    r = client.get("/api/v1/admin/stats", headers=oph)
    assert r.status_code == 200 and "active_sos_count" in r.json()

    r = client.get("/api/v1/admin/fishermen", headers=oph)
    assert r.status_code == 200 and "items" in r.json()

    r = client.get("/api/v1/admin/sos", headers=oph)
    assert r.status_code == 200 and "items" in r.json()

    assert client.get("/api/v1/admin/stats", headers=fh).status_code == 403


def test_boats_and_trips():
    fh = _login(FISH_PHONE)

    r = client.post("/api/v1/boats/", json={
        "name": "Sea Warrior", "registration_number": "TN-NAG-2024-001",
        "engine_type": "Yamaha 40HP", "engine_horsepower": 40, "fuel_capacity_liters": 60.0,
        "safety_equipment": ["Life jackets x4", "Fire extinguisher"]}, headers=fh)
    assert r.status_code == 201, r.text
    boat_id = r.json()["id"]

    r = client.post("/api/v1/trips/start", json={
        "boat_id": boat_id, "start_latitude": 10.766, "start_longitude": 79.844,
        "destination": "Fishing grounds", "estimated_return_at":
        (datetime.now(timezone.utc) + timedelta(hours=12)).isoformat()}, headers=fh)
    assert r.status_code == 201 and r.json()["status"] == "active"

    assert client.post("/api/v1/trips/start", json={"boat_id": boat_id}, headers=fh).status_code == 409

    r = client.get("/api/v1/trips/active", headers=fh)
    assert r.status_code == 200

    r = client.post("/api/v1/trips/end", json={"notes": "Good catch"}, headers=fh)
    assert r.status_code == 200 and r.json()["status"] == "completed"


def test_risk_engine():
    fh = _login(FISH_PHONE)
    r = client.get("/api/v1/risk/score?lat=11.05&lon=79.85", headers=fh)
    assert r.status_code == 200
    assert r.json()["score"] >= 2
    assert r.json()["color"] in ("yellow", "red")

    r = client.get("/api/v1/risk/score?lat=0.0&lon=0.0", headers=fh)
    assert r.json()["score"] == 0
