"""Boat Health Service API routes — v2 API."""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.boat_health import (
    BoatHealthService,
    FuelLogCreate,
    FuelLogResponse,
    MaintenanceCreate,
    MaintenanceResponse,
    FuelSummaryResponse,
    HealthScoreResponse,
    MaintenanceDueResponse,
)

router = APIRouter(prefix="/api/v2/boat-health", tags=["boat-health"])


@router.post("/fuel-log", response_model=FuelLogResponse)
async def create_fuel_log(
    fuel_data: FuelLogCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create fuel log entry (boat owner only)."""
    if current_user.role != "fisherman":
        raise HTTPException(status_code=403, detail="Only fishermen can log fuel")

    from app.models.boat import Boat

    boat = db.query(Boat).filter(Boat.id == fuel_data.boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    fuel_log = BoatHealthService.create_fuel_log(db, fuel_data)
    return FuelLogResponse.from_orm(fuel_log)


@router.get("/{boat_id}/fuel-summary", response_model=FuelSummaryResponse)
async def get_fuel_summary(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get fuel summary for boat."""
    from app.models.boat import Boat

    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if current_user.role == "fisherman" and boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    summary = BoatHealthService.get_fuel_summary(db, boat_id)
    return summary


@router.post("/maintenance", response_model=MaintenanceResponse)
async def create_maintenance(
    maintenance_data: MaintenanceCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Create maintenance record (boat owner only)."""
    from app.models.boat import Boat

    if current_user.role != "fisherman":
        raise HTTPException(status_code=403, detail="Only fishermen can create maintenance records")

    boat = db.query(Boat).filter(Boat.id == maintenance_data.boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    maintenance = BoatHealthService.create_maintenance_record(db, maintenance_data)
    return MaintenanceResponse.from_orm(maintenance)


@router.get("/{boat_id}/maintenance-due", response_model=MaintenanceDueResponse)
async def get_maintenance_due(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get maintenance due for boat."""
    from app.models.boat import Boat

    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if current_user.role == "fisherman" and boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    due = BoatHealthService.get_maintenance_due(db, boat_id)
    return due


@router.get("/{boat_id}/health-score", response_model=HealthScoreResponse)
async def get_health_score(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get boat health score."""
    from app.models.boat import Boat

    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if current_user.role == "fisherman" and boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    try:
        health_score = BoatHealthService.calculate_health_score(db, boat_id)
        return health_score
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{boat_id}/update-engine-hours", response_model=dict)
async def update_engine_hours(
    boat_id: int,
    engine_hours: float,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update engine hours for boat."""
    from app.models.boat import Boat

    boat = db.query(Boat).filter(Boat.id == boat_id).first()
    if not boat:
        raise HTTPException(status_code=404, detail="Boat not found")

    if current_user.role == "fisherman" and boat.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="You don't own this boat")

    health_status = BoatHealthService.update_health_status(db, boat_id, engine_hours=engine_hours)

    return {
        "boat_id": boat_id,
        "engine_hours": health_status.engine_hours,
        "updated_at": health_status.updated_at,
    }
