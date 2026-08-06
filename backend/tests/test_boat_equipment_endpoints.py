from datetime import date, timedelta

from fastapi.testclient import TestClient

from app.core.deps import get_db
from app.core.security import create_access_token
from app.main import app
from app.models.boat import Boat, BoatEquipmentItem, BoatInspection
from app.models.user import User, UserRole

client = TestClient(app)


def _override_get_db(db):
    def _get_db():
        try:
            yield db
        finally:
            pass
    return _get_db


def _create_fisherman(db, phone, name):
    user = User(
        phone_number=phone,
        password_hash="h",
        full_name=name,
        role=UserRole.fisherman,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _create_boat(db, owner, name="Test Boat"):
    boat = Boat(
        owner_id=owner.id,
        name=name,
        status="registered",
        verification_status="unverified",
        qr_code_token="test-token",
        created_by=owner.id,
        updated_by=owner.id,
        is_active=True,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


def _create_equipment(db, boat, created_by):
    item = BoatEquipmentItem(
        boat_id=boat.id,
        category="life_saving",
        item_name="Life Jacket",
        quantity=4,
        condition="good",
        is_mandatory=True,
        created_by=created_by,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _create_inspection(db, boat, created_by, result='passed'):
    inspection = BoatInspection(
        boat_id=boat.id,
        inspection_type='annual_safety',
        inspector_name='Inspector Name',
        inspector_authority='Maritime Safety Authority',
        inspection_date=date.today(),
        next_due_date=date.today() + timedelta(days=365),
        result=result,
        findings='All systems normal',
        certificate_number='CERT-0001',
        created_by=created_by,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return inspection


def _auth_headers(user):
    token = create_access_token(subject=str(user.id))
    return {"Authorization": f"Bearer {token}"}

def test_list_boat_equipment_items(db):
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        fisherman = _create_fisherman(db, "+919990000010", "Fisherman Test")
        boat = _create_boat(db, fisherman)
        _create_equipment(db, boat, fisherman.id)

        headers = _auth_headers(fisherman)
        response = client.get(f"/api/v2/boats/{boat.id}/equipment", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["item_name"] == "Life Jacket"
        assert data[0]["category"] == "life_saving"
    finally:
        app.dependency_overrides.clear()


def test_add_boat_equipment_item(db):
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        fisherman = _create_fisherman(db, "+919990000011", "Fisherman Add")
        boat = _create_boat(db, fisherman)

        headers = _auth_headers(fisherman)
        payload = {
            "category": "navigation",
            "item_name": "GPS Radio",
            "quantity": 1,
            "condition": "good",
            "is_mandatory": False,
        }
        response = client.post(f"/api/v2/boats/{boat.id}/equipment", json=payload, headers=headers)

        assert response.status_code == 201
        data = response.json()
        assert data["item_name"] == "GPS Radio"
        assert data["category"] == "navigation"
        assert data["quantity"] == 1
        assert data["condition"] == "good"
        assert data["is_mandatory"] is False
    finally:
        app.dependency_overrides.clear()


def test_list_boat_inspections(db):
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        fisherman = _create_fisherman(db, "+919990000012", "Fisherman Inspect")
        boat = _create_boat(db, fisherman)
        _create_inspection(db, boat, fisherman.id)

        headers = _auth_headers(fisherman)
        response = client.get(f"/api/v2/boats/{boat.id}/inspections", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["inspection_type"] == "annual_safety"
        assert data[0]["result"] == "passed"
    finally:
        app.dependency_overrides.clear()


def test_add_boat_inspection(db):
    app.dependency_overrides[get_db] = _override_get_db(db)
    try:
        fisherman = _create_fisherman(db, "+919990000013", "Fisherman Add Inspect")
        boat = _create_boat(db, fisherman)

        headers = _auth_headers(fisherman)
        payload = {
            "inspection_type": "annual_safety",
            "inspection_date": date.today().isoformat(),
            "result": "passed",
            "inspector_name": "Inspector Name",
            "inspector_authority": "Maritime Safety Authority",
            "findings": "Looks good",
            "corrective_actions": "None",
            "certificate_number": "CERT-1001",
        }
        response = client.post(
            f"/api/v2/boats/{boat.id}/inspections",
            json=payload,
            headers=headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["inspection_type"] == "annual_safety"
        assert data["result"] == "passed"
        assert data["inspector_name"] == "Inspector Name"
    finally:
        app.dependency_overrides.clear()

