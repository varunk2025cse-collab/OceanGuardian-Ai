from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.models.user import User, UserRole

client = TestClient(app)


def _create_operator(db, phone, name):
    u = User(phone_number=phone, password_hash="h", full_name=name, role=UserRole.operator)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _create_fisherman(db, phone, name):
    u = User(phone_number=phone, password_hash="h", full_name=name, role=UserRole.fisherman)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_admin_list_and_update_user(db):
    # Create operator and a fisherman
    op = _create_operator(db, "+919990000001", "Test Operator")
    f = _create_fisherman(db, "+919990000002", "Test Fisherman")

    token = create_access_token(subject=str(op.id))
    headers = {"Authorization": f"Bearer {token}"}

    # List users filtered by role=fisherman
    r = client.get("/api/v1/admin/users/?role=fisherman", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] >= 1

    # Get user detail
    r2 = client.get(f"/api/v1/admin/users/{f.id}", headers=headers)
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["phone_number"] == "+919990000002"

    # Update user (deactivate)
    r3 = client.patch(f"/api/v1/admin/users/{f.id}", json={"is_active": False}, headers=headers)
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["id"] == f.id
    assert d3["phone_number"] == f.phone_number

    # Re-activate and change role to family
    r4 = client.patch(f"/api/v1/admin/users/{f.id}", json={"is_active": True, "role": "family"}, headers=headers)
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["id"] == f.id
    assert d4["phone_number"] == f.phone_number
    assert d4["role"] == "family"
