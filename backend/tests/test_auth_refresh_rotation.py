from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_refresh_token_rotation():
    # Register a user
    payload = {
        "phone_number": "+911234567890",
        "password": "StrongPass123!",
        "full_name": "Test Fisherman",
        "role": "fisherman",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert "refresh_token" in data

    refresh_token = data["refresh_token"]

    # First refresh should succeed and return a new refresh token
    r1 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r1.status_code == 200
    data1 = r1.json()
    assert "refresh_token" in data1

    # Re-using the original refresh token must fail (rotation)
    r2 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 401

    # Using the newly-issued refresh token should succeed
    new_refresh = data1["refresh_token"]
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": new_refresh})
    assert r3.status_code == 200
