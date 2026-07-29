"""
Trip lifecycle — state machine for the V2 core build
(docs/V2_CORE_IMPLEMENTATION_PLAN.md, Step 6).

Trip.status is the stored, authoritative lifecycle state. It is
deliberately independent of two other, separately-modeled states:
  - connectivity/sync state (ONLINE/OFFLINE/SYNCING/SYNC_ERROR) — mobile-
    local, never stored server-side.
  - location freshness (LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN) — computed
    server-side in tracking_service.py from ping recency.
A trip stays ACTIVE whether or not the phone currently has signal; the UI
layers freshness/connectivity on top rather than encoding it into the trip
status itself.

`status` values are kept as the same plain strings already used by v1/v2
(not a native DB enum, matching Trip.status's existing column type) so
existing rows and other services that filter on "active"/"completed"/
"cancelled"/"emergency" strings keep working unchanged.
"""
import logging
from datetime import datetime, timezone

from fastapi import HTTPException, status as http_status
from sqlalchemy.orm import Session

from app.models.boat import Boat
from app.models.trip import Trip

logger = logging.getLogger("app.services.trip_service")


class TripStatus:
    PLANNED = "planned"
    ACTIVE = "active"
    RETURNING = "returning"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    EMERGENCY = "emergency"

    ALL = {PLANNED, ACTIVE, RETURNING, COMPLETED, CANCELLED, EMERGENCY}
    TERMINAL = {COMPLETED, CANCELLED}
    # States in which a trip counts as the fisherman's "current" voyage —
    # occupies the one-active-trip-per-fisherman / one-active-trip-per-boat
    # slot, and is what /trips/active and the dashboard's "active" views
    # should surface.
    IN_PROGRESS = {ACTIVE, RETURNING, EMERGENCY}


LEGAL_TRANSITIONS: dict[str, set[str]] = {
    TripStatus.PLANNED: {TripStatus.ACTIVE, TripStatus.CANCELLED},
    TripStatus.ACTIVE: {TripStatus.RETURNING, TripStatus.COMPLETED, TripStatus.CANCELLED, TripStatus.EMERGENCY},
    TripStatus.RETURNING: {TripStatus.ACTIVE, TripStatus.COMPLETED, TripStatus.EMERGENCY},
    TripStatus.EMERGENCY: {TripStatus.RETURNING, TripStatus.COMPLETED},
    TripStatus.COMPLETED: set(),
    TripStatus.CANCELLED: set(),
}


class TripService:
    """Owns trip lifecycle transitions and the "one active trip" invariant."""

    @staticmethod
    def get_active_trip(db: Session, user_id: int) -> Trip | None:
        return (
            db.query(Trip)
            .filter(Trip.user_id == user_id, Trip.status.in_(TripStatus.IN_PROGRESS))
            .first()
        )

    @staticmethod
    def start_trip(
        db: Session,
        user_id: int,
        boat_id: int | None,
        start_latitude: float | None,
        start_longitude: float | None,
        destination: str | None,
        estimated_return_at,
        notes: str | None,
    ) -> Trip:
        if TripService.get_active_trip(db, user_id):
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail="A trip is already active. End it before starting a new one.",
            )

        if boat_id:
            boat = db.query(Boat).filter(Boat.id == boat_id, Boat.owner_id == user_id).first()
            if not boat:
                raise HTTPException(
                    status_code=http_status.HTTP_404_NOT_FOUND,
                    detail="Boat not found or does not belong to you",
                )
            boat_in_use = (
                db.query(Trip)
                .filter(
                    Trip.boat_id == boat_id,
                    Trip.status.in_(TripStatus.IN_PROGRESS),
                    Trip.user_id != user_id,
                )
                .first()
            )
            if boat_in_use:
                raise HTTPException(
                    status_code=http_status.HTTP_409_CONFLICT,
                    detail="Boat is already in use by another active trip",
                )

            # ── Trip Readiness Advisory (non-blocking) ────────────────────────
            # The Readiness Service evaluates boat status, crew, documents,
            # equipment, and maintenance. A structured safety evaluation is
            # available at GET /boats/{id}/readiness for operators to inspect.
            #
            # This advisory does NOT block trip start — fail-open is the safer
            # default for a humanitarian safety platform. Blocking a legitimate
            # trip due to a data-entry gap (e.g. missing crew record) could
            # delay a fishing departure and harm the very people we protect.
            #
            # Emergency SOS is never blocked by any check.
            try:
                from app.services.boat_readiness_service import BoatReadinessService
                readiness = BoatReadinessService.evaluate_boat_readiness(db, boat_id)
                if not readiness.trip_allowed:
                    logger.warning(
                        "Trip started on non-ready boat | boat_id=%s | "
                        "readiness_score=%s | blocking_issues=%s",
                        boat_id, readiness.safety_score, readiness.blocking_issues,
                    )
            except Exception:
                logger.exception(
                    "BoatReadinessService advisory failed — allowing trip start | "
                    "boat_id=%s", boat_id,
                )

        trip = Trip(
            user_id=user_id,
            boat_id=boat_id,
            status=TripStatus.ACTIVE,
            start_latitude=start_latitude,
            start_longitude=start_longitude,
            destination=destination,
            estimated_return_at=estimated_return_at,
            notes=notes,
        )
        db.add(trip)
        db.commit()
        db.refresh(trip)
        return trip

    @staticmethod
    def transition(db: Session, trip: Trip, new_status: str, note: str | None = None) -> Trip:
        if new_status not in TripStatus.ALL:
            raise HTTPException(
                status_code=http_status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown trip status '{new_status}'",
            )
        legal = LEGAL_TRANSITIONS.get(trip.status, set())
        if new_status not in legal:
            raise HTTPException(
                status_code=http_status.HTTP_409_CONFLICT,
                detail=f"Cannot transition trip from '{trip.status}' to '{new_status}'",
            )
        trip.status = new_status
        if note:
            trip.notes = f"{trip.notes}\n{note}" if trip.notes else note
        if new_status in TripStatus.TERMINAL:
            trip.end_time = datetime.now(timezone.utc)
        db.commit()
        db.refresh(trip)
        return trip

    @staticmethod
    def end_trip(db: Session, user_id: int, note: str | None = None) -> Trip:
        trip = (
            db.query(Trip)
            .filter(Trip.user_id == user_id, Trip.status.in_({TripStatus.ACTIVE, TripStatus.RETURNING}))
            .first()
        )
        if not trip:
            raise HTTPException(status_code=http_status.HTTP_404_NOT_FOUND, detail="No active trip found")
        return TripService.transition(db, trip, TripStatus.COMPLETED, note)
