"""Boat management — fishermen register and manage their boats."""
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_fisherman
from app.models.boat import Boat
from app.models.user import User
from app.schemas.boat import BoatCreate, BoatUpdate, BoatOut

router = APIRouter(prefix="/api/v1/boats", tags=["boats"])


@router.post("/", response_model=BoatOut, status_code=status.HTTP_201_CREATED)
def register_boat(
    payload: BoatCreate,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    if payload.registration_number:
        existing = db.query(Boat).filter(
            Boat.registration_number == payload.registration_number).first()
        if existing:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Registration number already in use")
    data = payload.model_dump()
    safety = data.pop("safety_equipment", None)
    boat = Boat(
        owner_id=current_user.id,
        safety_equipment=json.dumps(safety) if safety else None,
        **data,
    )
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@router.get("/", response_model=list[BoatOut])
def list_my_boats(
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    return db.query(Boat).filter(Boat.owner_id == current_user.id, Boat.is_active.is_(True)).all()


@router.get("/{boat_id}", response_model=BoatOut)
def get_boat(
    boat_id: int,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    boat = db.query(Boat).filter(Boat.id == boat_id, Boat.owner_id == current_user.id).first()
    if not boat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    return boat


@router.patch("/{boat_id}", response_model=BoatOut)
def update_boat(
    boat_id: int,
    payload: BoatUpdate,
    current_user: User = Depends(get_current_fisherman),
    db: Session = Depends(get_db),
):
    boat = db.query(Boat).filter(Boat.id == boat_id, Boat.owner_id == current_user.id).first()
    if not boat:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Boat not found")
    
    data = payload.model_dump(exclude_unset=True)
    
    # Check registration number uniqueness if being updated
    if "registration_number" in data and data["registration_number"]:
        existing = db.query(Boat).filter(
            Boat.registration_number == data["registration_number"],
            Boat.id != boat_id
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Registration number already in use by another boat"
            )
    
    if "safety_equipment" in data:
        data["safety_equipment"] = json.dumps(data["safety_equipment"]) if data["safety_equipment"] else None
    
    for key, val in data.items():
        setattr(boat, key, val)
    
    db.commit()
    db.refresh(boat)
    return boat
