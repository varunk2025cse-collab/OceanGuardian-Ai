from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_logout_all_blocks_refresh():
    # Register a user and obtain tokens
    payload = {
        "phone_number": "+919999999991",
        "password": "AnotherStrong1$",
        "full_name": "Logout Test",
        "role": "fisherman",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    refresh_token = data["refresh_token"]
    access_token = data["access_token"]

    # Call logout_all with refresh token in body
    headers = {"Authorization": f"Bearer {access_token}"}
    r2 = client.post("/api/v1/auth/logout_all", json={"refresh_token": refresh_token}, headers=headers)
    assert r2.status_code == 204

    # Attempt to use the refresh token to rotate — should fail
    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r3.status_code == 401

    # Accessing a protected endpoint with the access token should also fail after logout_all
    r4 = client.get("/api/v1/auth/me", headers=headers)
    assert r4.status_code == 401
