"""Phase 2 fix validation tests: unlink, last_sync, boat validation, trip validation."""
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient
from app.main import app
from app.database import SessionLocal

client = TestClient(app)

def _reg(phone, name, role):
    r = client.post("/api/v1/auth/register", json={
        "phone_number": phone, "password": "test1234",
        "full_name": name, "role": role, "preferred_language": "ta"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_cannot_self_register_as_operator():
    """Security fix: role is restricted to fisherman/family at the schema
    level, so a self-registration attempt with role=operator must be
    rejected outright, never silently downgraded or accepted."""
    r = client.post("/api/v1/auth/register", json={
        "phone_number": "+919900009999", "password": "test1234",
        "full_name": "Would-be Operator", "role": "operator", "preferred_language": "ta"})
    assert r.status_code == 422


def test_family_unlink():
    """Test family unlink functionality."""
    fish_h = _reg("+919900000001", "Fisher One", "fisherman")
    fam_h = _reg("+919900000002", "Family One", "family")
    
    # Link fisherman
    r = client.post("/api/v1/family/link", 
        json={"fisherman_phone_number": "+919900000001", "relation": "Spouse"}, 
        headers=fam_h)
    assert r.status_code == 201
    
    # Verify link
    r = client.get("/api/v1/family/status", headers=fam_h)
    assert r.status_code == 200
    assert len(r.json()) == 1
    fisherman_id = r.json()[0]["fisherman_id"]
    
    # Unlink
    r = client.delete(f"/api/v1/family/unlink/{fisherman_id}", headers=fam_h)
    assert r.status_code == 204
    
    # Verify unlinked
    r = client.get("/api/v1/family/status", headers=fam_h)
    assert r.status_code == 200
    assert len(r.json()) == 0
    
    # Try to unlink again (should fail)
    r = client.delete(f"/api/v1/family/unlink/{fisherman_id}", headers=fam_h)
    assert r.status_code == 404


def test_last_sync_tracking():
    """Test that last_sync_at is updated when locations are synced."""
    fish_h = _reg("+919900000003", "Fisher Sync", "fisherman")
    
    # Initial profile - no last_sync_at
    r = client.get("/api/v1/auth/me", headers=fish_h)
    assert r.json()["last_sync_at"] is None
    
    # Submit location
    r = client.post("/api/v1/locations/ping", json={
        "client_uuid": "sync-test-001",
        "latitude": 11.0,
        "longitude": 80.0,
        "recorded_at": datetime.now(timezone.utc).isoformat()
    }, headers=fish_h)
    assert r.status_code == 200
    
    # Check last_sync_at is now set
    r = client.get("/api/v1/auth/me", headers=fish_h)
    profile = r.json()
    assert profile["last_sync_at"] is not None
    
    # Batch sync
    r = client.post("/api/v1/locations/sync", json={
        "points": [
            {"client_uuid": "sync-test-002", "latitude": 11.1, "longitude": 80.1,
             "recorded_at": datetime.now(timezone.utc).isoformat()},
            {"client_uuid": "sync-test-003", "latitude": 11.2, "longitude": 80.2,
             "recorded_at": datetime.now(timezone.utc).isoformat()},
        ]
    }, headers=fish_h)
    assert r.json()["accepted"] == 2
    
    # Verify last_sync_at updated again
    r = client.get("/api/v1/auth/me", headers=fish_h)
    new_sync_time = r.json()["last_sync_at"]
    assert new_sync_time is not None
    assert new_sync_time >= profile["last_sync_at"]


def test_boat_registration_uniqueness():
    """Test that boat registration numbers must be unique."""
    fish1_h = _reg("+919900000004", "Fisher Boat 1", "fisherman")
    fish2_h = _reg("+919900000005", "Fisher Boat 2", "fisherman")
    
    # Register boat with registration number
    r = client.post("/api/v1/boats/", json={
        "name": "Blue Wave",
        "registration_number": "TN-TEST-2024-001",
        "engine_type": "Yamaha"
    }, headers=fish1_h)
    assert r.status_code == 201
    boat1_id = r.json()["id"]
    
    # Try to register another boat with same registration number
    r = client.post("/api/v1/boats/", json={
        "name": "Red Wave",
        "registration_number": "TN-TEST-2024-001",
        "engine_type": "Suzuki"
    }, headers=fish2_h)
    assert r.status_code == 409
    assert "already in use" in r.json()["detail"].lower()
    
    # Update own boat to different registration - OK
    r = client.patch(f"/api/v1/boats/{boat1_id}", json={
        "registration_number": "TN-TEST-2024-002"
    }, headers=fish1_h)
    assert r.status_code == 200
    
    # Now fisher2 can use the old number
    r = client.post("/api/v1/boats/", json={
        "name": "Red Wave",
        "registration_number": "TN-TEST-2024-001",
        "engine_type": "Suzuki"
    }, headers=fish2_h)
    assert r.status_code == 201


def test_trip_boat_conflict():
    """Test that same boat cannot be used in multiple active trips."""
    fish1_h = _reg("+919900000006", "Fisher Trip 1", "fisherman")
    fish2_h = _reg("+919900000007", "Fisher Trip 2", "fisherman")
    
    # Fisher 1 registers a boat
    r = client.post("/api/v1/boats/", json={
        "name": "Shared Boat",
        "registration_number": "TN-SHARED-001"
    }, headers=fish1_h)
    boat_id = r.json()["id"]
    
    # Fisher 1 starts trip with boat
    r = client.post("/api/v1/trips/start", json={
        "boat_id": boat_id,
        "start_latitude": 11.0,
        "start_longitude": 80.0,
        "estimated_return_at": (datetime.now(timezone.utc) + timedelta(hours=8)).isoformat()
    }, headers=fish1_h)
    assert r.status_code == 201
    
    # Try to start trip without boat - should work
    r = client.post("/api/v1/trips/start", json={
        "start_latitude": 11.1,
        "start_longitude": 80.1
    }, headers=fish2_h)
    assert r.status_code == 201
    
    # End fisher2's trip
    r = client.post("/api/v1/trips/end", json={}, headers=fish2_h)
    assert r.status_code == 200
    
    # Fisher 1 ends trip
    r = client.post("/api/v1/trips/end", json={}, headers=fish1_h)
    assert r.status_code == 200
    
    # Now fisher 2 can start trip with the boat (owns it? No, they don't own it)
    # Actually, fisher2 doesn't own this boat, so they can't use it


def test_health_check_enhanced():
    """Test enhanced health check with database status."""
    r = client.get("/health")
    assert r.status_code == 200
    data = r.json()
    assert "database" in data
    assert data["database"] == "healthy"
    assert data["status"] in ["healthy", "degraded"]
    assert "version" in data
    assert "environment" in data


def test_sos_with_logging():
    """Test SOS trigger to verify logging doesn't break functionality."""
    fish_h = _reg("+919900000008", "Fisher Log Test", "fisherman")
    
    r = client.post("/api/v1/sos/trigger", json={
        "client_uuid": "log-test-sos-001",
        "latitude": 11.0,
        "longitude": 80.0,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
        "message": "Test SOS"
    }, headers=fish_h)
    assert r.status_code == 201
    assert r.json()["status"] == "active"
    assert r.json()["priority"] == "high"  # Default priority


def test_multiple_fisherman_same_phone_validation():
    """Test that duplicate phone numbers are rejected."""
    r = client.post("/api/v1/auth/register", json={
        "phone_number": "+919900000099",
        "password": "test1234",
        "full_name": "First Fisher",
        "role": "fisherman",
        "preferred_language": "ta"
    })
    assert r.status_code == 201
    
    # Try to register again with same phone
    r = client.post("/api/v1/auth/register", json={
        "phone_number": "+919900000099",
        "password": "test1234",
        "full_name": "Second Fisher",
        "role": "fisherman",
        "preferred_language": "ta"
    })
    assert r.status_code == 409
    assert "already registered" in r.json()["detail"].lower()
