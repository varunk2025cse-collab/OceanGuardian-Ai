from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from fastapi.testclient import TestClient
from app.main import app
from app.models.user import PasswordResetToken

client = TestClient(app)


def test_user_profile_update_and_change_password():
    payload = {
        "phone_number": "+919999999990",
        "password": "StrongPass123!",
        "full_name": "Profile Update Test",
        "role": "fisherman",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    access_token = data["access_token"]

    headers = {"Authorization": f"Bearer {access_token}"}

    r2 = client.patch(
        "/api/v1/auth/me",
        json={"full_name": "Updated Fisherman", "boat_name": "Sea Guardian"},
        headers=headers,
    )
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["full_name"] == "Updated Fisherman"
    assert d2["boat_name"] == "Sea Guardian"

    r3 = client.post(
        "/api/v1/auth/change-password",
        json={"current_password": "StrongPass123!", "new_password": "NewStrongPass123!"},
        headers=headers,
    )
    assert r3.status_code == 204

    r4 = client.get("/api/v1/auth/me", headers=headers)
    assert r4.status_code == 401

    r5 = client.post(
        "/api/v1/auth/login",
        json={"phone_number": payload["phone_number"], "password": "NewStrongPass123!"},
    )
    assert r5.status_code == 200
    assert "access_token" in r5.json()


def test_password_reset_invalidates_refresh_tokens(db):
    payload = {
        "phone_number": "+919999999991",
        "password": "ResetPass123!",
        "full_name": "Reset Test",
        "role": "fisherman",
    }
    r = client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    refresh_token = data["refresh_token"]
    user_id = data["user"]["id"]

    raw_token = uuid.uuid4().hex
    token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
    prt = PasswordResetToken(user_id=user_id, token_hash=token_hash, expires_at=expires_at)
    db.add(prt)
    db.commit()

    r2 = client.post(
        "/api/v1/auth/reset",
        json={"token": raw_token, "new_password": "ResetPass456!"},
    )
    assert r2.status_code == 200

    r3 = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert r3.status_code == 401

    r4 = client.post(
        "/api/v1/auth/login",
        json={"phone_number": payload["phone_number"], "password": "ResetPass456!"},
    )
    assert r4.status_code == 200
    assert "access_token" in r4.json()


