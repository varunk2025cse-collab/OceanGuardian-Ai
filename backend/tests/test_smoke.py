"""MVP end-to-end smoke test. DB setup is handled by conftest.py."""
from datetime import datetime, timezone, timedelta, date
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal
from app.models.weather_alert import WeatherAlert, HazardSeverity, HazardType
from app.models.market_price import MarketPrice
from app.models.govt_scheme import GovtScheme
from app.models.harbor import Harbor

client = TestClient(app)


def test_full_mvp_flow():
    db = SessionLocal()
    now = datetime.now(timezone.utc)
    db.add(WeatherAlert(title="Smoke Wave Warning", description="test",
        hazard_type=HazardType.high_waves, severity=HazardSeverity.warning,
        center_latitude=11.0, center_longitude=80.0, radius_km=100,
        valid_from=now, valid_until=now + timedelta(days=1), source="TEST"))
    db.add(MarketPrice(species="Pomfret", market_name="Test Market",
        harbor_region="Nagapattinam", price_per_kg=500, price_date=date.today()))
    db.add(GovtScheme(title="Smoke Scheme", category="subsidy", region="National",
        description="d", eligibility="e", how_to_apply="a"))
    db.add(Harbor(name="Smoke Harbor", region="Nagapattinam", state="Tamil Nadu",
        latitude=10.766, longitude=79.844))
    db.commit(); db.close()

    r = client.post("/api/v1/auth/register", json={
        "phone_number": "+911100000001", "password": "secret123",
        "full_name": "Murugan Smoke", "role": "fisherman", "preferred_language": "ta",
        "boat_name": "Sea Eagle", "home_harbor": "Nagapattinam",
        "emergency_contact_name": "Kalai", "emergency_contact_phone": "+911100000099",
    })
    assert r.status_code == 201, r.text
    fh = {"Authorization": f"Bearer {r.json()['access_token']}"}

    r = client.post("/api/v1/auth/login", json={"phone_number": "+911100000001", "password": "secret123"})
    assert r.status_code == 200

    r = client.get("/api/v1/auth/me", headers=fh)
    assert r.json()["full_name"] == "Murugan Smoke"

    points = [
        {"client_uuid": "smoke-loc-0001", "latitude": 11.05, "longitude": 79.85,
         "recorded_at": datetime.now(timezone.utc).isoformat()},
        {"client_uuid": "smoke-loc-0002", "latitude": 11.06, "longitude": 79.86,
         "recorded_at": datetime.now(timezone.utc).isoformat()},
    ]
    r = client.post("/api/v1/locations/sync", json={"points": points}, headers=fh)
    assert r.json() == {"accepted": 2, "duplicates": 0, "failed": 0}
    r = client.post("/api/v1/locations/sync", json={"points": points}, headers=fh)
    assert r.json() == {"accepted": 0, "duplicates": 2, "failed": 0}

    sos_payload = {"client_uuid": "smoke-sos-00001", "latitude": 11.05, "longitude": 79.85,
                   "battery_level_percent": 18, "triggered_at": datetime.now(timezone.utc).isoformat()}
    r = client.post("/api/v1/sos/trigger", json=sos_payload, headers=fh)
    assert r.status_code == 201
    alert_id = r.json()["id"]
    r = client.post("/api/v1/sos/trigger", json=sos_payload, headers=fh)
    assert r.json()["id"] == alert_id  # idempotent

    r = client.patch(f"/api/v1/sos/{alert_id}/status", json={"status": "false_alarm"}, headers=fh)
    assert r.json()["status"] == "false_alarm"

    r = client.get("/api/v1/weather/active?lat=11.02&lon=79.99", headers=fh)
    assert len(r.json()) >= 1

    r = client.get("/api/v1/risk/score?lat=11.02&lon=79.99", headers=fh)
    assert r.json()["score"] in (0, 1, 2)

    r = client.get("/api/v1/market/prices", headers=fh)
    assert r.status_code == 200

    r = client.get("/api/v1/schemes/", headers=fh)
    assert r.status_code == 200

    r = client.get("/api/v1/harbors/nearest?lat=11.0&lon=79.8", headers=fh)
    assert "distance_km" in r.json()

    r = client.post("/api/v1/auth/register", json={
        "phone_number": "+911100000002", "password": "secret123",
        "full_name": "Kalai Smoke", "role": "family", "preferred_language": "ta"})
    fam_h = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+911100000001", "relation": "Wife"}, headers=fam_h)
    r = client.get("/api/v1/family/status", headers=fam_h)
    assert r.json()[0]["full_name"] == "Murugan Smoke"
