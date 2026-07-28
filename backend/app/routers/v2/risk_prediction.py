"""Advanced Risk Prediction API routes."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.services.risk_prediction import RiskPredictionService
from app.schemas.risk_prediction import (
    RiskPredictionResponse,
    TripRiskResponse,
    HighRiskBoat,
    RiskRecalculateRequest,
)

router = APIRouter(prefix="/api/v2/risk", tags=["risk-prediction"])


@router.get("/current/{fisherman_id}", response_model=RiskPredictionResponse)
async def get_current_risk(
    fisherman_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get current risk for fisherman."""
    # Fishermen can only view their own risk, operators can view anyone's
    if current_user.role == "fisherman" and current_user.id != fisherman_id:
        raise HTTPException(status_code=403, detail="Can only view your own risk")

    # Find active trip
    from app.models.trip import Trip
    active_trip = (
        db.query(Trip)
        .filter(Trip.user_id == fisherman_id, Trip.end_time.is_(None))
        .first()
    )

    if not active_trip:
        raise HTTPException(status_code=404, detail="No active trip found")

    risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
    if not risk:
        raise HTTPException(status_code=500, detail="Failed to calculate risk")

    return risk


@router.get("/trip/{trip_id}", response_model=TripRiskResponse)
async def get_trip_risk(
    trip_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get risk assessment for a specific trip."""
    from app.models.trip import Trip
    trip = db.query(Trip).filter(Trip.id == trip_id).first()
    if not trip:
        raise HTTPException(status_code=404, detail="Trip not found")

    # Fishermen can only view their own trip risk
    if current_user.role == "fisherman" and current_user.id != trip.user_id:
        raise HTTPException(status_code=403, detail="Can only view your own trip risk")

    risk = RiskPredictionService.get_trip_risk(trip_id, db)
    if not risk:
        raise HTTPException(status_code=500, detail="Failed to get trip risk")

    return risk


@router.get("/boats/high-risk", response_model=List[HighRiskBoat])
async def get_high_risk_boats(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get list of high-risk boats (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can view high-risk boats")

    boats = RiskPredictionService.get_high_risk_boats(db, limit=limit)
    return boats


@router.post("/recalculate")
async def recalculate_risk(
    request: RiskRecalculateRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Manually recalculate risk (operator only)."""
    if current_user.role != "operator":
        raise HTTPException(status_code=403, detail="Only operators can recalculate risk")

    if request.trip_id:
        risk = RiskPredictionService.calculate_risk_score(request.trip_id, db)
        if not risk:
            raise HTTPException(status_code=404, detail="Trip not found")
        return {"status": "success", "trip_id": request.trip_id, "risk": risk}

    elif request.fisherman_id:
        from app.models.trip import Trip
        active_trip = (
            db.query(Trip)
            .filter(Trip.user_id == request.fisherman_id, Trip.end_time.is_(None))
            .first()
        )
        if not active_trip:
            raise HTTPException(status_code=404, detail="No active trip found")

        risk = RiskPredictionService.calculate_risk_score(active_trip.id, db)
        return {"status": "success", "fisherman_id": request.fisherman_id, "risk": risk}

    else:
        raise HTTPException(status_code=400, detail="Must provide trip_id or fisherman_id")
