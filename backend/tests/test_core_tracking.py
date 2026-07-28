"""
V2 core build (Steps 3-8): trip state machine, tracking fleet/history
authorization, location freshness computation, and the new location
telemetry fields. See docs/V2_CORE_IMPLEMENTATION_PLAN.md.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.tracking_service import compute_freshness, LocationFreshness

client = TestClient(app)

FISH_PHONE = "+912300000001"
FISH2_PHONE = "+912300000002"
FAM_PHONE = "+912300000003"
FAM2_PHONE = "+912300000004"
OP_PHONE = "+912300000005"


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


def test_trip_state_machine_legal_and_illegal_transitions():
    fh = _reg(FISH_PHONE, "Trip Tester", "fisherman")

    r = client.post("/api/v1/trips/start", json={
        "start_latitude": 10.7, "start_longitude": 79.8, "destination": "Reef"}, headers=fh)
    assert r.status_code == 201
    trip_id = r.json()["id"]
    assert r.json()["status"] == "active"

    # ACTIVE -> RETURNING is legal
    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "returning"}, headers=fh)
    assert r.status_code == 200 and r.json()["status"] == "returning"

    # RETURNING -> ACTIVE is legal (changed their mind, heading back out)
    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "active"}, headers=fh)
    assert r.status_code == 200 and r.json()["status"] == "active"

    # ACTIVE -> COMPLETED is legal
    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "completed"}, headers=fh)
    assert r.status_code == 200 and r.json()["status"] == "completed"

    # COMPLETED is terminal — any further transition is illegal
    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "active"}, headers=fh)
    assert r.status_code == 409

    # Unknown status value is rejected at the schema layer
    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "bogus"}, headers=fh)
    assert r.status_code == 422


def test_trip_transition_requires_ownership():
    fh = _reg(FISH2_PHONE, "Other Fisherman", "fisherman")
    fh_owner = _reg("+912300000009", "Trip Owner", "fisherman")

    r = client.post("/api/v1/trips/start", json={}, headers=fh_owner)
    trip_id = r.json()["id"]

    r = client.patch(f"/api/v1/trips/{trip_id}/status", json={"status": "returning"}, headers=fh)
    assert r.status_code == 404  # not visible/owned by this caller, not leaked as 403


def test_compute_freshness_thresholds():
    now = datetime.now(timezone.utc)
    assert compute_freshness(None, now=now) == LocationFreshness.UNKNOWN
    assert compute_freshness(now - timedelta(minutes=1), now=now) == LocationFreshness.LIVE
    assert compute_freshness(now - timedelta(minutes=20), now=now) == LocationFreshness.RECENT
    assert compute_freshness(now - timedelta(hours=2), now=now) == LocationFreshness.LAST_KNOWN
    assert compute_freshness(now - timedelta(hours=5), now=now) == LocationFreshness.STALE


def test_fleet_endpoint_operator_only():
    fh = _reg("+912300000010", "Fleet Fisherman", "fisherman")
    oph = _create_operator(OP_PHONE, "Fleet Operator")

    r = client.post("/api/v1/trips/start", json={"start_latitude": 11.0, "start_longitude": 79.9}, headers=fh)
    assert r.status_code == 201

    assert client.get("/api/v2/tracking/fleet", headers=fh).status_code == 403

    r = client.get("/api/v2/tracking/fleet", headers=oph)
    assert r.status_code == 200
    assert any(v["fisherman_name"] == "Fleet Fisherman" for v in r.json())


def test_history_authorization_self_operator_and_family():
    fh = _reg("+912300000011", "History Fisherman", "fisherman")
    fam = _reg(FAM_PHONE, "Linked Family", "family")
    fam_unlinked = _reg(FAM2_PHONE, "Unlinked Family", "family")
    oph = _create_operator("+912300000012", "History Operator")

    me = client.get("/api/v1/auth/me", headers=fh).json()
    fisherman_id = me["id"]

    client.post("/api/v1/locations/ping", json={
        "client_uuid": "core-hist-0001", "latitude": 11.05, "longitude": 79.85,
        "altitude_meters": 3.2, "battery_percent": 71.5, "network_type": "4G",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }, headers=fh)

    r = client.get(f"/api/v2/tracking/{fisherman_id}/history", headers=fh)
    assert r.status_code == 200
    assert r.json()["freshness"] == "LIVE"
    assert r.json()["points"][0]["altitude_meters"] == 3.2
    assert r.json()["points"][0]["battery_percent"] == 71.5
    assert r.json()["points"][0]["network_type"] == "4G"
    assert r.json()["points"][0]["source"] == "MOBILE_GPS"

    assert client.get(f"/api/v2/tracking/{fisherman_id}/history", headers=oph).status_code == 200
    assert client.get(f"/api/v2/tracking/{fisherman_id}/history", headers=fam_unlinked).status_code == 403

    client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+912300000011", "relation": "Wife"}, headers=fam)
    assert client.get(f"/api/v2/tracking/{fisherman_id}/history", headers=fam).status_code == 200
