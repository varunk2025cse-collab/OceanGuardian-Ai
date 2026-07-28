"""
Safety semantics audit (Final Release Engineering Phase G).

Regression tests for two real conflation bugs found and fixed during this
audit:
  1. /admin/fishermen defaulted a fisherman with NO location data on
     record to risk_label="safe" (score=0) — presenting an absence of
     data as an affirmative safety claim.
  2. The rescue dashboard's RiskBadge component fell back to the "safe"
     (teal) visual style for any unrecognized label, which would have
     silently re-introduced the same false "safe" impression even after
     the backend started sending "unknown" instead of "safe".
     (Frontend fix verified by code review + `npm run build`, not by a
     Python test — see rescue-dashboard/src/pages/FishermenPagePremium.jsx.)
"""
from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password

client = TestClient(app)


def _create_operator(phone, name):
    db = SessionLocal()
    db.add(User(phone_number=phone, password_hash=hash_password("test1234"),
                 full_name=name, role=UserRole.operator, preferred_language="en"))
    db.commit(); db.close()
    r = client.post("/api/v1/auth/login", json={"phone_number": phone, "password": "test1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _reg(phone, name, role):
    r = client.post("/api/v1/auth/register", json={
        "phone_number": phone, "password": "test1234",
        "full_name": name, "role": role, "preferred_language": "ta"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_fisherman_with_no_location_is_never_labeled_safe():
    _reg("+912700000001", "No Location Fisher", "fisherman")
    oph = _create_operator("+912700000002", "Semantics Audit Operator")

    r = client.get("/api/v1/admin/fishermen", headers=oph)
    assert r.status_code == 200
    match = next(f for f in r.json()["items"] if f["phone_number"] == "+912700000001")
    assert match["risk_label"] == "unknown"
    assert match["risk_score"] < 0  # sentinel for "no data", not a real score
    assert match["safety_state"] == "UNKNOWN"  # no trip in progress either


def test_fisherman_with_location_gets_a_real_risk_label():
    fh = _reg("+912700000003", "Has Location Fisher", "fisherman")
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "semantics-audit-0001", "latitude": 11.0, "longitude": 80.0,
        "recorded_at": datetime.now(timezone.utc).isoformat()}, headers=fh)
    oph = _create_operator("+912700000004", "Semantics Audit Operator 2")

    r = client.get("/api/v1/admin/fishermen", headers=oph)
    match = next(f for f in r.json()["items"] if f["phone_number"] == "+912700000003")
    assert match["risk_label"] in ("safe", "moderate", "dangerous")
    assert match["risk_score"] >= 0
