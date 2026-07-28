"""
Tracking — fleet-level and per-fisherman location views for the V2 core
build (docs/V2_CORE_IMPLEMENTATION_PLAN.md, Step 7).

Owns one thing other services/frontends should not each reimplement:
location FRESHNESS. Mobile, family, and the rescue dashboard all need to
answer "how current is this position?" without ever presenting a stale
point as live (docs/V1_AUDIT.md's safety-first framing). Freshness is
computed here, once, server-side, from configurable thresholds
(app.config.settings) — see also app.services.trip_service for why this is
kept separate from trip lifecycle and mobile-local connectivity state.
"""
from datetime import datetime, timezone
from enum import Enum

from fastapi import HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.models.family_link import FamilyLink
from app.models.location import LocationPing
from app.models.trip import Trip
from app.models.user import User, UserRole
from app.services.trip_service import TripStatus


class LocationFreshness(str, Enum):
    LIVE = "LIVE"
    RECENT = "RECENT"
    LAST_KNOWN = "LAST_KNOWN"
    STALE = "STALE"
    UNKNOWN = "UNKNOWN"


def compute_freshness(recorded_at: datetime | None, *, now: datetime | None = None) -> LocationFreshness:
    """Pure function: age of the last ping -> a freshness bucket. No ping at
    all is UNKNOWN, never "offline" or anything implying data once existed.
    """
    if recorded_at is None:
        return LocationFreshness.UNKNOWN
    now = now or datetime.now(timezone.utc)
    if recorded_at.tzinfo is None:
        recorded_at = recorded_at.replace(tzinfo=timezone.utc)
    age_minutes = (now - recorded_at).total_seconds() / 60
    if age_minutes < 0:
        age_minutes = 0
    if age_minutes <= settings.freshness_live_minutes:
        return LocationFreshness.LIVE
    if age_minutes <= settings.freshness_recent_minutes:
        return LocationFreshness.RECENT
    if age_minutes <= settings.freshness_last_known_minutes:
        return LocationFreshness.LAST_KNOWN
    return LocationFreshness.STALE


class FleetVessel(BaseModel):
    fisherman_id: int
    fisherman_name: str
    boat_name: str | None
    trip_id: int | None
    trip_status: str | None
    latitude: float | None
    longitude: float | None
    recorded_at: datetime | None
    freshness: LocationFreshness

    model_config = {"from_attributes": True}


class TrackingService:
    @staticmethod
    def _latest_ping(db: Session, user_id: int) -> LocationPing | None:
        return (
            db.query(LocationPing)
            .filter(LocationPing.user_id == user_id)
            .order_by(LocationPing.recorded_at.desc())
            .first()
        )

    @staticmethod
    def get_fleet(db: Session, skip: int = 0, limit: int = 100) -> list[FleetVessel]:
        """Latest position + freshness for every fisherman with an in-progress
        trip. Operator-only (enforced by the router)."""
        trips = (
            db.query(Trip)
            .filter(Trip.status.in_(TripStatus.IN_PROGRESS))
            .order_by(Trip.start_time.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
        vessels: list[FleetVessel] = []
        for trip in trips:
            fisherman = db.query(User).filter(User.id == trip.user_id).first()
            if not fisherman:
                continue
            ping = TrackingService._latest_ping(db, trip.user_id)
            vessels.append(
                FleetVessel(
                    fisherman_id=fisherman.id,
                    fisherman_name=fisherman.full_name,
                    boat_name=fisherman.boat_name,
                    trip_id=trip.id,
                    trip_status=trip.status,
                    latitude=ping.latitude if ping else None,
                    longitude=ping.longitude if ping else None,
                    recorded_at=ping.recorded_at if ping else None,
                    freshness=compute_freshness(ping.recorded_at if ping else None),
                )
            )
        return vessels

    @staticmethod
    def get_history(
        db: Session,
        requesting_user: User,
        fisherman_id: int,
        limit: int = 200,
    ) -> list[LocationPing]:
        """Authorization: a fisherman may view their own history; an operator
        may view anyone's; a family member only a linked fisherman's."""
        if requesting_user.role == UserRole.operator:
            pass
        elif requesting_user.id == fisherman_id:
            pass
        elif requesting_user.role == UserRole.family:
            linked = (
                db.query(FamilyLink)
                .filter(
                    FamilyLink.family_user_id == requesting_user.id,
                    FamilyLink.fisherman_id == fisherman_id,
                )
                .first()
            )
            if not linked:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You are not authorized to view this fisherman's location",
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not authorized to view this fisherman's location",
            )

        return (
            db.query(LocationPing)
            .filter(LocationPing.user_id == fisherman_id)
            .order_by(LocationPing.recorded_at.desc())
            .limit(min(limit, 1000))
            .all()
        )
