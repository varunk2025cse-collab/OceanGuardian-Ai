"""
Navigation AI (docs/NAVIGATION_AI.md) — straight-line bearing/compass
direction guidance to the nearest known safe harbor. Built on top of the
existing, already-tested nearest-harbor distance/ETA logic
(app/services/harbor.py) — these tests cover the new bearing math and its
integration into the Safety Engine, /api/v2/harbor endpoints, and the AI
tool/dispatcher layer.
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.phase5 import Harbor
from app.models.user import User, UserRole
from app.core.security import hash_password
from app.services.geo import bearing_degrees, compass_direction

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


def _create_harbor(name, lat, lon):
    db = SessionLocal()
    h = Harbor(name=name, latitude=lat, longitude=lon, region="Test", harbor_type="major", is_active=True)
    db.add(h); db.commit(); db.refresh(h)
    db.close()
    return h.id


# --------------------------------------------------------- pure math -----

def test_bearing_due_north_is_zero_degrees():
    # From (0,0) to a point directly north (higher latitude, same longitude).
    bearing = bearing_degrees(0.0, 0.0, 1.0, 0.0)
    assert abs(bearing - 0.0) < 1.0


def test_bearing_due_east_is_90_degrees():
    bearing = bearing_degrees(0.0, 0.0, 0.0, 1.0)
    assert abs(bearing - 90.0) < 1.0


def test_compass_direction_maps_degrees_to_8_point_labels():
    assert compass_direction(0) == "N"
    assert compass_direction(45) == "NE"
    assert compass_direction(90) == "E"
    assert compass_direction(135) == "SE"
    assert compass_direction(180) == "S"
    assert compass_direction(225) == "SW"
    assert compass_direction(270) == "W"
    assert compass_direction(315) == "NW"
    assert compass_direction(359) == "N"  # wraps correctly


# ------------------------------------------------------- harbor API ------

def test_nearest_harbor_endpoint_includes_bearing_and_direction():
    fh = _reg("+912900000001", "Nav Fisher", "fisherman")
    _create_harbor("Due North Harbor", 11.2, 80.0)  # ~22km north of the query point, within default 50km radius

    r = client.post("/api/v2/harbor/nearest", params={"latitude": 11.0, "longitude": 80.0}, headers=fh)
    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    top = body[0]
    assert "bearing_degrees" in top
    assert "compass_direction" in top
    assert top["compass_direction"] in ("N", "NE", "NW")  # roughly northward


# --------------------------------------------------- safety engine -------

def test_safety_state_includes_nearest_harbor_navigation_fields():
    fh = _reg("+912900000002", "Nav Safety Fisher", "fisherman")
    _create_harbor("Nav Test Harbor", 9.0, 77.0)
    client.post("/api/v1/trips/start", json={"start_latitude": 9.5, "start_longitude": 77.5}, headers=fh)
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "nav-safety-ping-0001", "latitude": 9.5, "longitude": 77.5,
        "recorded_at": datetime.now(timezone.utc).isoformat()}, headers=fh)

    r = client.get("/api/v2/safety/", headers=fh)
    assert r.status_code == 200
    body = r.json()
    assert body["nearest_harbor_name"] is not None
    assert body["nearest_harbor_km"] is not None
    assert body["nearest_harbor_direction"] in ("N", "NE", "E", "SE", "S", "SW", "W", "NW")
    assert body["nearest_harbor_eta_minutes"] is not None and body["nearest_harbor_eta_minutes"] > 0


def test_safety_state_navigation_fields_null_without_location():
    fh = _reg("+912900000003", "Nav No Location Fisher", "fisherman")
    r = client.get("/api/v2/safety/", headers=fh)
    assert r.status_code == 200
    body = r.json()
    assert body["nearest_harbor_name"] is None  # UNKNOWN state — never a fabricated fallback
    assert body["nearest_harbor_km"] is None
    assert body["nearest_harbor_eta_minutes"] is None


# -------------------------------------------------------- AI tool/intent -

def test_ai_navigation_guidance_intent():
    fh = _reg("+912900000004", "Nav AI Fisher", "fisherman")
    oph = _create_operator("+912900000005", "Nav AI Operator")
    fisherman_id = client.get("/api/v1/auth/me", headers=fh).json()["id"]

    _create_harbor("AI Nav Harbor", 8.0, 76.0)
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "nav-ai-ping-0001", "latitude": 8.5, "longitude": 76.5,
        "recorded_at": datetime.now(timezone.utc).isoformat()}, headers=fh)

    r = client.post("/api/v2/ai/query",
        json={"intent": "navigation_guidance", "fisherman_id": fisherman_id}, headers=oph)
    assert r.status_code == 200
    body = r.json()
    assert "Nearest safe harbor" in body["answer"]
    assert body["data"]["harbor_found"] is True


def test_ai_navigation_guidance_requires_authorization():
    fh = _reg("+912900000006", "Nav Auth Fisher", "fisherman")
    unrelated_fh = _reg("+912900000007", "Nav Auth Unrelated Fisher", "fisherman")
    fisherman_id = client.get("/api/v1/auth/me", headers=fh).json()["id"]

    r = client.post("/api/v2/ai/query",
        json={"intent": "navigation_guidance", "fisherman_id": fisherman_id}, headers=unrelated_fh)
    assert r.status_code == 403
