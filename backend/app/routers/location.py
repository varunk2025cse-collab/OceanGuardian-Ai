"""
GPS location: live ping + offline batch sync.

The phone always writes GPS fixes to its local SQLite queue first (see the
Flutter LocalDbService / LocationService). When connectivity returns, it
POSTs the whole backlog here in one batch. `client_uuid` makes this endpoint
idempotent: re-sending a batch that partially succeeded earlier (e.g. the
connection dropped after the server committed but before the phone got the
response) never creates duplicate points.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from datetime import datetime, timezone

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.location import LocationPing
from app.schemas.location import (
    LocationPingIn,
    LocationBatchSync,
    LocationOut,
    LocationSyncResult,
)

router = APIRouter(prefix="/api/v1/locations", tags=["locations"])


@router.post("/ping", response_model=LocationOut)
def submit_single_ping(
    payload: LocationPingIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Used when the phone has live connectivity and sends fixes one at a time."""
    existing = db.query(LocationPing).filter(LocationPing.client_uuid == payload.client_uuid).first()
    if existing:
        return existing

    ping = LocationPing(user_id=current_user.id, **payload.model_dump())
    db.add(ping)
    
    # Update last sync time
    current_user.last_sync_at = datetime.now(timezone.utc)
    
    db.commit()
    db.refresh(ping)
    return ping


@router.post("/sync", response_model=LocationSyncResult)
def sync_offline_batch(
    payload: LocationBatchSync,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Bulk-accepts the offline queue built up while the boat had no signal."""
    accepted, duplicates, failed = 0, 0, 0

    existing_uuids = {
        row[0]
        for row in db.query(LocationPing.client_uuid)
        .filter(LocationPing.client_uuid.in_([p.client_uuid for p in payload.points]))
        .all()
    }

    for point in payload.points:
        if point.client_uuid in existing_uuids:
            duplicates += 1
            continue
        try:
            db.add(LocationPing(user_id=current_user.id, **point.model_dump()))
            db.flush()
            accepted += 1
        except IntegrityError:
            db.rollback()
            failed += 1

    db.commit()
    
    # Update last sync time
    current_user.last_sync_at = datetime.now(timezone.utc)
    db.commit()
    
    return LocationSyncResult(accepted=accepted, duplicates=duplicates, failed=failed)


@router.get("/me/latest", response_model=LocationOut | None)
def my_latest_location(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return (
        db.query(LocationPing)
        .filter(LocationPing.user_id == current_user.id)
        .order_by(LocationPing.recorded_at.desc())
        .first()
    )


@router.get("/me/history", response_model=list[LocationOut])
def my_location_history(
    limit: int = 200,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Recent track for the in-app 'where have I been today' trail on the map."""
    return (
        db.query(LocationPing)
        .filter(LocationPing.user_id == current_user.id)
        .order_by(LocationPing.recorded_at.desc())
        .limit(min(limit, 1000))
        .all()
    )
