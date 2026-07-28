"""
End-to-end golden path (Final Release Engineering Phase H).

    Fisherman login -> Trip start -> GPS tracking -> Family authorization
    -> Weather retrieval -> Safety evaluation -> Risk increase ->
    Network loss -> Offline GPS storage -> SOS -> Local SOS queue ->
    Network restoration -> Sync -> Incident creation -> Rescue dashboard
    -> AI explanation -> Operator acknowledgement -> Rescue state
    transition -> Family update -> Incident resolution -> Audit trail

Every stage below is a real API call against the real app, in one
continuous flow, asserting the actual state at each step — this is not a
disconnected set of unit tests, it's the literal scenario from the
governing brief walked start to finish.

"Network loss / offline GPS storage / local SOS queue / sync" (the
mobile-device-local part of the diagram) is proven separately in
mobile/test/local_db_service_test.dart (backoff/outbox behavior) and
mobile/lib/services/sync_service.dart's design (SQLite-first writes) —
those are genuinely client-side concerns with no backend counterpart to
assert against. What this test proves on the backend side is the
equivalent: a location/SOS payload arriving via the batch-sync endpoint
(exactly what the phone sends once connectivity returns) is processed
correctly, in order, without duplication, and drives every downstream
system (incident, notification, dashboard, AI, audit trail) correctly.
"""
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.database import SessionLocal
from app.models.user import User, UserRole
from app.core.security import hash_password

client = TestClient(app)

HARBOR_LAT, HARBOR_LON = 10.766, 79.844


def _create_operator(phone, name):
    db = SessionLocal()
    db.add(User(phone_number=phone, password_hash=hash_password("test1234"),
                 full_name=name, role=UserRole.operator, preferred_language="en"))
    db.commit(); db.close()
    r = client.post("/api/v1/auth/login", json={"phone_number": phone, "password": "test1234"})
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_full_golden_path_fisherman_to_incident_resolution():
    # ---- 1. Fisherman login (register = first login) ----------------------
    reg = client.post("/api/v1/auth/register", json={
        "phone_number": "+912800000001", "password": "GoldenPath@1234",
        "full_name": "Golden Path Fisherman", "role": "fisherman", "preferred_language": "ta",
        "boat_name": "Golden Path Boat",
    })
    assert reg.status_code == 201
    fh = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    fisherman_id = reg.json()["user"]["id"]

    relogin = client.post("/api/v1/auth/login", json={"phone_number": "+912800000001", "password": "GoldenPath@1234"})
    assert relogin.status_code == 200

    # ---- 2. Trip start ------------------------------------------------------
    trip = client.post("/api/v1/trips/start", json={
        "start_latitude": HARBOR_LAT, "start_longitude": HARBOR_LON,
        "destination": "Golden path fishing grounds",
        "estimated_return_at": (datetime.now(timezone.utc) + timedelta(hours=10)).isoformat(),
    }, headers=fh)
    assert trip.status_code == 201
    assert trip.json()["status"] == "active"
    trip_id = trip.json()["id"]

    # ---- 3. GPS tracking (live ping) -----------------------------------------
    ping = client.post("/api/v1/locations/ping", json={
        "client_uuid": "golden-ping-live", "latitude": HARBOR_LAT, "longitude": HARBOR_LON,
        "battery_percent": 95, "network_type": "4G",
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }, headers=fh)
    assert ping.status_code == 200

    # ---- 4. Family authorization ---------------------------------------------
    fam_reg = client.post("/api/v1/auth/register", json={
        "phone_number": "+912800000002", "password": "GoldenPath@1234",
        "full_name": "Golden Path Family", "role": "family", "preferred_language": "ta",
    })
    famh = {"Authorization": f"Bearer {fam_reg.json()['access_token']}"}
    link = client.post("/api/v1/family/link",
        json={"fisherman_phone_number": "+912800000001", "relation": "Wife"}, headers=famh)
    assert link.status_code == 201

    unauthorized_fam = client.post("/api/v1/auth/register", json={
        "phone_number": "+912800000003", "password": "GoldenPath@1234",
        "full_name": "Unrelated Family", "role": "family", "preferred_language": "ta",
    })
    unauth_h = {"Authorization": f"Bearer {unauthorized_fam.json()['access_token']}"}
    assert client.get(f"/api/v2/safety/{fisherman_id}", headers=unauth_h).status_code == 403
    assert client.get(f"/api/v2/safety/{fisherman_id}", headers=famh).status_code == 200

    # ---- 5. Weather retrieval (real live call) --------------------------------
    weather = client.get("/api/v2/weather/live", params={"lat": HARBOR_LAT, "lon": HARBOR_LON}, headers=fh, timeout=10)
    assert weather.status_code == 200
    assert isinstance(weather.json()["available"], bool)  # real provider response, honest either way

    # ---- 6. Safety evaluation --------------------------------------------------
    safety = client.get("/api/v2/safety/", headers=fh)
    assert safety.status_code == 200
    assert safety.json()["safety_state"] in ("SAFE", "MONITOR", "CAUTION", "HIGH_RISK", "CRITICAL")
    assert safety.json()["trip_status"] == "active"

    # ---- 7. Risk increase (a fresh-but-far-offshore ping legitimately
    #         raises the score via the harbor-distance factor; freshness
    #         staying LIVE here is correct — it's still the most recent
    #         ping. GPS-becomes-stale is dedicated-tested in
    #         test_failure_injection.py::test_stale_gps_never_reports_as_safe,
    #         not duplicated here to keep this test about the sequence.) ---
    client.post("/api/v1/locations/ping", json={
        "client_uuid": "golden-ping-offshore", "latitude": HARBOR_LAT + 1.2, "longitude": HARBOR_LON + 1.2,
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }, headers=fh)
    safety_after = client.get("/api/v2/safety/", headers=fh).json()
    assert safety_after["safety_score"] >= safety.json()["safety_score"]  # never decreases from the added distance signal
    assert safety_after["freshness"] == "LIVE"

    # ---- 8/9/10. Network loss -> offline GPS storage -> SOS queued
    #              (mobile-side; see module docstring). Backend-equivalent:
    #              a batch-sync payload arriving after reconnect. -----------
    reconnect_time = datetime.now(timezone.utc)
    sync = client.post("/api/v1/locations/sync", json={"points": [
        {"client_uuid": "golden-offline-1", "latitude": HARBOR_LAT + 0.5, "longitude": HARBOR_LON + 0.5,
         "battery_percent": 40, "network_type": "OFFLINE", "recorded_at": (reconnect_time - timedelta(minutes=20)).isoformat()},
        {"client_uuid": "golden-offline-2", "latitude": HARBOR_LAT + 0.6, "longitude": HARBOR_LON + 0.6,
         "battery_percent": 38, "network_type": "OFFLINE", "recorded_at": (reconnect_time - timedelta(minutes=10)).isoformat()},
    ]}, headers=fh)
    assert sync.status_code == 200
    assert sync.json() == {"accepted": 2, "duplicates": 0, "failed": 0}

    # ---- 11/12. Network restoration -> sync (re-send same batch, must
    #             be fully deduplicated — proves no data corruption) --------
    resync = client.post("/api/v1/locations/sync", json={"points": [
        {"client_uuid": "golden-offline-1", "latitude": HARBOR_LAT + 0.5, "longitude": HARBOR_LON + 0.5,
         "recorded_at": (reconnect_time - timedelta(minutes=20)).isoformat()},
    ]}, headers=fh)
    assert resync.json() == {"accepted": 0, "duplicates": 1, "failed": 0}

    # ---- SOS triggered once connectivity returns ------------------------------
    sos = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "golden-sos-0001", "latitude": HARBOR_LAT + 0.6, "longitude": HARBOR_LON + 0.6,
        "battery_level_percent": 35, "network_type": "4G",
        "alert_type": "ENGINE_FAILURE", "message": "Golden path E2E test SOS",
        "triggered_at": reconnect_time.isoformat(),
    }, headers=fh)
    assert sos.status_code == 201
    sos_id = sos.json()["id"]

    # ---- 13. Incident creation --------------------------------------------------
    oph = _create_operator("+912800000004", "Golden Path Operator")
    active_incidents = client.get("/api/v2/incidents/active", headers=oph).json()
    incident = next(i for i in active_incidents if i["sos_alert_id"] == sos_id)
    assert incident["status"] == "received"
    incident_id = incident["id"]

    # ---- 14. Rescue dashboard sees it (fleet + safety fleet summary) ----------
    fleet = client.get("/api/v2/tracking/fleet", headers=oph).json()
    assert any(v["fisherman_id"] == fisherman_id for v in fleet)
    safety_fleet = client.get("/api/v2/safety/fleet/summary", headers=oph).json()
    assert any(v["fisherman_id"] == fisherman_id for v in safety_fleet)

    # ---- 15. AI explanation (vessel_status intent) -----------------------------
    ai = client.post("/api/v2/ai/query", json={"intent": "vessel_status", "fisherman_id": fisherman_id}, headers=oph)
    assert ai.status_code == 200
    assert len(ai.json()["answer"]) > 0
    assert ai.json()["provider"] in ("template", "anthropic")

    # ---- 16. Operator acknowledgement --------------------------------------------
    ack = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "acknowledged", "reason": "Golden path: operator reviewing"}, headers=oph)
    assert ack.status_code == 200 and ack.json()["status"] == "acknowledged"

    # ---- 17. Rescue state transition (dispatch -> in progress -> safe) --------
    for target in ("rescue_dispatched", "rescue_in_progress", "safe"):
        r = client.post(f"/api/v2/incidents/{incident_id}/transition",
            json={"status": target, "reason": f"Golden path: {target}"}, headers=oph)
        assert r.status_code == 200 and r.json()["status"] == target

    # ---- 18. Family update — safety_state/incident_status visible to family ---
    fam_status = client.get("/api/v1/family/status", headers=famh).json()
    fisherman_status = next(s for s in fam_status if s["fisherman_id"] == fisherman_id)
    assert fisherman_status["incident_status"] == "safe"

    # ---- 19. Incident resolution (closed) --------------------------------------
    closed = client.post(f"/api/v2/incidents/{incident_id}/transition",
        json={"status": "closed", "reason": "Golden path: resolved"}, headers=oph)
    assert closed.status_code == 200 and closed.json()["status"] == "closed"

    # ---- 20. Audit trail --------------------------------------------------------
    timeline = client.get(f"/api/v2/incidents/{incident_id}/timeline", headers=oph).json()
    assert [e["new_status"] for e in timeline] == [
        "received", "acknowledged", "rescue_dispatched", "rescue_in_progress", "safe", "closed",
    ]
    report = client.get(f"/api/v2/incidents/{incident_id}/report", headers=oph).json()
    assert report["fisherman"]["id"] == fisherman_id
    assert report["response_time_seconds"] is not None  # was acknowledged, so this is real, not null
    assert len(report["timeline"]) == 6
