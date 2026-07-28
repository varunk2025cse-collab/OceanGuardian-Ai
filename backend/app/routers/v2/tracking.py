"""Tracking API — v2. Fleet-level and per-fisherman location views.

/api/v1/locations/* (ingestion, self-history) is unchanged; this router is
additive and covers the operator/family-facing consumption side that didn't
exist before (docs/V2_CORE_IMPLEMENTATION_PLAN.md, Step 7).
"""
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator, get_current_user
from app.database import get_db
from app.models.user import User
from app.schemas.location import LocationOut
from app.services.tracking_service import (
    FleetVessel,
    LocationFreshness,
    TrackingService,
    compute_freshness,
)

router = APIRouter(prefix="/api/v2/tracking", tags=["tracking"])


class TrackingHistoryResponse(BaseModel):
    fisherman_id: int
    freshness: LocationFreshness
    latest_recorded_at: datetime | None
    points: list[LocationOut]


@router.get("/fleet", response_model=list[FleetVessel])
def get_fleet(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=100, ge=1, le=500),
    _: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Latest position + freshness for every fisherman with an in-progress
    trip. Powers the rescue dashboard fleet map."""
    return TrackingService.get_fleet(db, skip=skip, limit=limit)


@router.get("/{fisherman_id}/history", response_model=TrackingHistoryResponse)
def get_history(
    fisherman_id: int,
    limit: int = Query(default=200, ge=1, le=1000),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Authorized via TrackingService.get_history: self, operator, or a
    family member explicitly linked to this fisherman — never anyone else."""
    points = TrackingService.get_history(db, current_user, fisherman_id, limit=limit)
    latest = points[0].recorded_at if points else None
    return TrackingHistoryResponse(
        fisherman_id=fisherman_id,
        freshness=compute_freshness(latest),
        latest_recorded_at=latest,
        points=points,
    )
