from fastapi.testclient import TestClient
from app.main import app
from app.core.security import create_access_token
from app.database import get_db
from app.models.user import User, UserRole
from app.models.notification_models import NotificationEventStream

client = TestClient(app)


def _override_get_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass
    return _get_db


def _create_operator(db, phone, name):
    u = User(phone_number=phone, password_hash="h", full_name=name, role=UserRole.operator)
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def test_list_providers_and_publish_event(db):
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        op = _create_operator(db, "+919990000100", "Notif Op")
        token = create_access_token(subject=str(op.id))
        headers = {"Authorization": f"Bearer {token}"}

        # list providers
        r = client.get("/api/v1/admin/notifications/providers", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("providers"), list)

        # publish an event
        payload = {"event_type": "test.event", "payload_json": {"foo": "bar"}}
        r2 = client.post("/api/v1/admin/notifications/events", json=payload, headers=headers)
        assert r2.status_code == 201
        d2 = r2.json()
        assert d2["event_type"] == "test.event"

        # list events
        r3 = client.get("/api/v1/admin/notifications/events", headers=headers)
        assert r3.status_code == 200
        dj = r3.json()
        assert dj["total"] >= 1

        # replay the event
        ev_id = d2["id"]
        r4 = client.post(f"/api/v1/admin/notifications/events/{ev_id}/replay", headers=headers)
        assert r4.status_code == 200
        assert r4.json().get("ok") is True

        # cancel the event
        r5 = client.post(f"/api/v1/admin/notifications/events/{ev_id}/cancel", headers=headers)
        assert r5.status_code == 200
        assert r5.json().get("ok") is True

    finally:
        app.dependency_overrides.clear()
