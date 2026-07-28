"""Smart Check-In System — Monitor fisherman safety during trips.

Week 3 enhancements:
  - CheckInSchedule management (create/activate/deactivate)
  - CheckInRequest instances for individual check-in events
  - MissedCheckIn tracking with escalation
  - Operator awareness escalation
  - Offline sync support
  - Family notification integration
"""
import json
import uuid
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, or_, text as sa_text
from app.models.phase5 import (
    CheckinLog, CheckinAlert, CheckinStatus,
    CheckInSchedule, CheckInRequest, MissedCheckIn, SafetyEscalation,
)
from app.models.trip import Trip
from app.models.user import User
from app.models.location import LocationPing
from app.schemas.checkin import (
    CheckInStatusResponse,
    MissedCheckInDetail,
    CheckInResponse,
    CheckInScheduleCreate,
    CheckInRespondRequest,
    CheckInRespondResponse,
)
from app.schemas.escalation import EscalationDetail


class CheckInService:
    """Smart Check-In System."""

    STALE_GPS_THRESHOLD_MINUTES = 30
    OFFLINE_THRESHOLD_MINUTES = 45
    MISSED_CHECKIN_THRESHOLD = 3
    DEFAULT_INTERVAL_MINUTES = 30

    # ── Schedule Management ──────────────────────────────────────────────

    @staticmethod
    def create_schedule(
        fisherman_id: int, data: CheckInScheduleCreate, db: Session
    ) -> CheckInSchedule:
        """Create a new check-in schedule for a trip."""
        trip = db.query(Trip).filter(Trip.id == data.trip_id).first()
        if not trip:
            raise ValueError("Trip not found")
        if trip.user_id != fisherman_id:
            raise ValueError("Unauthorized — this trip does not belong to you")
        if trip.end_time is not None:
            raise ValueError("Trip already ended")

        # Deactivate any existing active schedules for this trip
        existing = (
            db.query(CheckInSchedule)
            .filter(
                and_(
                    CheckInSchedule.trip_id == data.trip_id,
                    CheckInSchedule.is_active == True,
                )
            )
            .all()
        )
        for s in existing:
            s.is_active = False

        now = datetime.utcnow()
        schedule = CheckInSchedule(
            trip_id=data.trip_id,
            fisherman_id=fisherman_id,
            interval_minutes=data.interval_minutes or CheckInService.DEFAULT_INTERVAL_MINUTES,
            next_checkin_at=now + timedelta(minutes=data.interval_minutes or CheckInService.DEFAULT_INTERVAL_MINUTES),
            is_active=True,
        )
        db.add(schedule)
        db.commit()
        db.refresh(schedule)

        # Also create first overdue check-in request so the background worker can process it immediately.
        CheckInService._create_checkin_request(
            schedule,
            db,
            requested_at=now - timedelta(minutes=schedule.interval_minutes),
            update_schedule=False,
        )

        return schedule

    @staticmethod
    def _create_checkin_request(
        schedule: CheckInSchedule,
        db: Session,
        requested_at: datetime | None = None,
        update_schedule: bool = True,
    ) -> CheckInRequest:
        """Create a check-in request instance from a schedule."""
        # Mark any pending requests as missed before creating a new one.
        pending = (
            db.query(CheckInRequest)
            .filter(
                and_(
                    CheckInRequest.schedule_id == schedule.id,
                    CheckInRequest.status == "pending",
                )
            )
            .all()
        )
        for req in pending:
            req.status = "missed"

        now = datetime.utcnow()
        if requested_at is None:
            existing_count = (
                db.query(CheckInRequest)
                .filter(CheckInRequest.schedule_id == schedule.id)
                .count()
            )
            if existing_count == 0:
                requested_at = now - timedelta(minutes=schedule.interval_minutes)
            else:
                requested_at = now

        if update_schedule:
            schedule.next_checkin_at = requested_at + timedelta(minutes=schedule.interval_minutes)
        db.flush()

        request = CheckInRequest(
            schedule_id=schedule.id,
            trip_id=schedule.trip_id,
            fisherman_id=schedule.fisherman_id,
            status="pending",
            requested_at=requested_at,
        )
        db.add(request)
        db.commit()
        db.refresh(request)
        return request

    @staticmethod
    def respond_checkin_scheduled(
        fisherman_id: int, data: CheckInRespondRequest, db: Session
    ) -> CheckInRespondResponse:
        """Respond to a scheduled check-in request."""
        request = (
            db.query(CheckInRequest)
            .filter(CheckInRequest.id == data.schedule_id)
            .first()
        )
        if not request:
            raise ValueError("Check-in request not found")
        if request.fisherman_id != fisherman_id:
            raise ValueError("Unauthorized — this request is not for you")
        if request.status == "responded":
            raise ValueError("Already responded to this check-in")

        now = datetime.utcnow()
        request.status = "responded"
        request.responded_at = now
        request.response_status = data.status if data.status in ("safe", "help_needed", "busy") else "safe"
        request.response_lat = data.location_lat
        request.response_lng = data.location_lng
        request.response_notes = data.notes
        request.synced = data.synced

        # Update schedule's next check-in
        schedule = (
            db.query(CheckInSchedule)
            .filter(CheckInSchedule.id == request.schedule_id)
            .first()
        )
        if schedule and schedule.is_active:
            schedule.next_checkin_at = now + timedelta(minutes=schedule.interval_minutes)

        # Also update CheckinLog for continuity
        log = CheckinLog(
            trip_id=request.trip_id,
            fisherman_id=fisherman_id,
            last_update_time=now,
            time_since_last_update_minutes=0,
            movement_detected=True,
            offline_duration_minutes=0,
            status=CheckinStatus.ACTIVE.value,
            check_status=data.status,
        )
        db.add(log)

        # Clear any active alerts for this trip
        active_alerts = (
            db.query(CheckinAlert)
            .filter(
                and_(
                    CheckinAlert.trip_id == request.trip_id,
                    CheckinAlert.dismissed == False,
                )
            )
            .all()
        )
        for alert in active_alerts:
            alert.dismissed = True
            alert.resolved_at = now
            alert.resolution_notes = f"Check-in received: {data.status}"

        db.commit()

        next_due = (
            schedule.next_checkin_at if schedule else now + timedelta(minutes=CheckInService.DEFAULT_INTERVAL_MINUTES)
        )

        return CheckInRespondResponse(
            id=request.id,
            schedule_id=request.schedule_id,
            trip_id=request.trip_id,
            status=request.response_status,
            responded_at=now,
            next_checkin_due=next_due,
        )

    # ── Original / Legacy API Methods ────────────────────────────────────

    @staticmethod
    def get_my_checkin_status(fisherman_id: int, db: Session) -> Optional[CheckInStatusResponse]:
        """Get fisherman's current check-in status."""
        active_trip = (
            db.query(Trip)
            .filter(and_(Trip.user_id == fisherman_id, Trip.end_time.is_(None)))
            .first()
        )
        if not active_trip:
            return None

        latest_log = (
            db.query(CheckinLog)
            .filter(CheckinLog.trip_id == active_trip.id)
            .order_by(desc(CheckinLog.created_at))
            .first()
        )

        if not latest_log:
            latest_log = CheckinLog(
                trip_id=active_trip.id,
                fisherman_id=fisherman_id,
                last_update_time=datetime.utcnow(),
                time_since_last_update_minutes=0,
                status=CheckinStatus.ACTIVE.value,
                check_status="ok",
            )
            db.add(latest_log)
            db.commit()

        next_due = latest_log.last_update_time + timedelta(minutes=30)

        # Get active schedule
        schedule = (
            db.query(CheckInSchedule)
            .filter(
                and_(
                    CheckInSchedule.trip_id == active_trip.id,
                    CheckInSchedule.is_active == True,
                )
            )
            .first()
        )

        return CheckInStatusResponse(
            trip_id=active_trip.id,
            fisherman_id=fisherman_id,
            last_checkin=latest_log.last_update_time,
            next_checkin_due=next_due,
            status=latest_log.status,
            missed_count=latest_log.offline_duration_minutes // 30,
            schedule_id=schedule.id if schedule else None,
            interval_minutes=schedule.interval_minutes if schedule else None,
        )

    @staticmethod
    def respond_checkin(
        fisherman_id: int, response: CheckInResponse, db: Session
    ) -> dict:
        """Record fisherman check-in response (legacy API)."""
        trip = db.query(Trip).filter(Trip.id == response.trip_id).first()
        if not trip or trip.user_id != fisherman_id:
            raise ValueError("Invalid trip or unauthorized")
        if trip.end_time is not None:
            raise ValueError("Trip already ended")

        if response.location_lat and response.location_lng:
            location = LocationPing(
                client_uuid=str(uuid.uuid4()),
                user_id=fisherman_id,
                trip_id=response.trip_id,
                latitude=response.location_lat,
                longitude=response.location_lng,
                recorded_at=datetime.utcnow(),
            )
            db.add(location)

        log = CheckinLog(
            trip_id=response.trip_id,
            fisherman_id=fisherman_id,
            last_update_time=datetime.utcnow(),
            time_since_last_update_minutes=0,
            movement_detected=True,
            offline_duration_minutes=0,
            status=CheckinStatus.ACTIVE.value,
            check_status=response.status,
        )
        db.add(log)

        active_alerts = (
            db.query(CheckinAlert)
            .filter(
                and_(
                    CheckinAlert.trip_id == response.trip_id,
                    CheckinAlert.dismissed == False,
                )
            )
            .all()
        )
        for alert in active_alerts:
            alert.dismissed = True
            alert.resolved_at = datetime.utcnow()
            alert.resolution_notes = f"Check-in received: {response.status}"

        db.commit()

        return {
            "status": "success",
            "message": "Check-in recorded",
            "next_checkin_due": datetime.utcnow() + timedelta(minutes=30),
        }

    @staticmethod
    def get_missed_checkins(db: Session, limit: int = 50) -> List[MissedCheckInDetail]:
        """Get list of missed check-ins (operator view)."""
        threshold_time = datetime.utcnow() - timedelta(
            minutes=CheckInService.STALE_GPS_THRESHOLD_MINUTES
        )
        active_trips = db.query(Trip).filter(Trip.end_time.is_(None)).all()

        # First, get persisted missed records
        missed_records = (
            db.query(MissedCheckIn)
            .filter(MissedCheckIn.resolved_at.is_(None))
            .order_by(MissedCheckIn.created_at.desc())
            .limit(limit)
            .all()
        )

        # Compute missed count for each trip from CheckInRequest
        missed_list = []
        seen_trip_ids = set()

        for record in missed_records:
            if record.trip_id in seen_trip_ids:
                continue
            seen_trip_ids.add(record.trip_id)

            fisherman = db.query(User).filter(User.id == record.fisherman_id).first()
            last_request = (
                db.query(CheckInRequest)
                .filter(
                    and_(
                        CheckInRequest.trip_id == record.trip_id,
                        CheckInRequest.status == "responded",
                    )
                )
                .order_by(desc(CheckInRequest.responded_at))
                .first()
            )

            # Count total pending/missed requests
            missed_request_count = (
                db.query(CheckInRequest)
                .filter(
                    and_(
                        CheckInRequest.trip_id == record.trip_id,
                        CheckInRequest.status.in_(["pending", "missed"]),
                    )
                )
                .count()
            )

            missed_list.append(
                MissedCheckInDetail(
                    id=record.id,
                    trip_id=record.trip_id,
                    fisherman_id=record.fisherman_id,
                    fisherman_name=fisherman.full_name if fisherman else "Unknown",
                    last_seen=last_request.responded_at if last_request else None,
                    missed_count=missed_request_count,
                    consecutive_missed=record.consecutive_missed,
                    status="alert" if record.escalated else "warning",
                    escalated=record.escalated,
                    created_at=record.created_at,
                )
            )

        # Also include stalled trips without missed records yet
        for trip in active_trips:
            if trip.id in seen_trip_ids:
                continue

            latest_log = (
                db.query(CheckinLog)
                .filter(CheckinLog.trip_id == trip.id)
                .order_by(desc(CheckinLog.created_at))
                .first()
            )

            if not latest_log or latest_log.last_update_time < threshold_time:
                fisherman = db.query(User).filter(User.id == trip.user_id).first()
                elapsed = 0
                if latest_log:
                    elapsed = int(
                        (datetime.utcnow() - latest_log.last_update_time).total_seconds() / 60
                    )
                missed_count = elapsed // 30 if elapsed else 1

                missed_list.append(
                    MissedCheckInDetail(
                        id=0,
                        trip_id=trip.id,
                        fisherman_id=trip.user_id,
                        fisherman_name=fisherman.full_name if fisherman else "Unknown",
                        last_seen=latest_log.last_update_time if latest_log else trip.start_time,
                        missed_count=missed_count,
                        consecutive_missed=missed_count,
                        status="warning",
                        escalated=False,
                        created_at=trip.start_time,
                    )
                )

        return sorted(missed_list, key=lambda x: x.missed_count, reverse=True)[:limit]

    @staticmethod
    def create_alert(
        trip_id: int,
        fisherman_id: int,
        alert_type: str,
        threshold_value: str,
        description: str,
        db: Session,
    ) -> CheckinAlert:
        """Create check-in alert."""
        alert = CheckinAlert(
            trip_id=trip_id,
            fisherman_id=fisherman_id,
            alert_type=alert_type,
            threshold_value=threshold_value,
            alert_description=description,
            family_notified=False,
            rescue_operator_notified=False,
            dismissed=False,
        )
        db.add(alert)
        db.commit()
        db.refresh(alert)
        return alert

    # ── Missed Check-in Escalation ────────────────────────────────────────

    @staticmethod
    def process_missed_checkins(db: Session) -> dict:
        """Background task: Check for missed check-ins and escalate."""
        now = datetime.utcnow()
        threshold_time = now - timedelta(minutes=CheckInService.STALE_GPS_THRESHOLD_MINUTES)
        offline_threshold = now - timedelta(minutes=CheckInService.OFFLINE_THRESHOLD_MINUTES)

        active_schedules = (
            db.query(CheckInSchedule)
            .filter(CheckInSchedule.is_active == True)
            .all()
        )

        missed_count = 0
        escalated_count = 0

        for schedule in active_schedules:
            # Find the latest pending request for this schedule.
            latest_request = (
                db.query(CheckInRequest)
                .filter(
                    and_(
                        CheckInRequest.schedule_id == schedule.id,
                        CheckInRequest.status == "pending",
                    )
                )
                .order_by(desc(CheckInRequest.requested_at))
                .first()
            )

            if not latest_request:
                latest_request = CheckInService._create_checkin_request(schedule, db)

            # If pending past deadline, mark as missed.
            time_since_request = (now - latest_request.requested_at).total_seconds() / 60
            is_overdue = latest_request.status == "pending" and time_since_request >= schedule.interval_minutes

            if is_overdue:
                latest_request.status = "missed"
                db.flush()

                last_missed = (
                    db.query(MissedCheckIn)
                    .filter(
                        and_(
                            MissedCheckIn.trip_id == schedule.trip_id,
                            MissedCheckIn.resolved_at.is_(None),
                        )
                    )
                    .order_by(desc(MissedCheckIn.created_at))
                    .first()
                )

                consecutive = (last_missed.consecutive_missed + 1) if last_missed else 1

                missed = MissedCheckIn(
                    schedule_id=schedule.id,
                    request_id=latest_request.id,
                    trip_id=schedule.trip_id,
                    fisherman_id=schedule.fisherman_id,
                    consecutive_missed=consecutive,
                )
                db.add(missed)
                db.flush()
                missed_count += 1

                if consecutive >= CheckInService.MISSED_CHECKIN_THRESHOLD and not missed.escalated:
                    CheckInService._escalate_missed_checkin(missed, schedule, db)
                    missed.escalated = True
                    escalated_count += 1

                # Create next overdue check-in request so repeated background runs can continue to escalate.
                next_request_time = now - timedelta(minutes=schedule.interval_minutes)
                CheckInService._create_checkin_request(
                    schedule,
                    db,
                    requested_at=next_request_time,
                )

        db.commit()
        # Also check stale GPS + bad weather for escalation
        stale_checkin_alerts = CheckInService._check_stale_gps_escalations(db)

        return {
            "status": "completed",
            "schedules_processed": len(active_schedules),
            "missed_recorded": missed_count,
            "escalations_created": escalated_count + stale_checkin_alerts,
        }

    @staticmethod
    def _escalate_missed_checkin(
        missed: MissedCheckIn, schedule: CheckInSchedule, db: Session
    ):
        """Create SafetyEscalation for a missed check-in."""
        consecutive = missed.consecutive_missed

        # Determine level: 1-4 based on consecutive misses
        if consecutive >= 6:
            level = 4
            priority = "critical"
        elif consecutive >= 4:
            level = 3
            priority = "high"
        elif consecutive >= 3:
            level = 2
            priority = "high"
        else:
            level = 1
            priority = "normal"

        # Family notified at level 1
        family_notified = level >= 1
        # Operator notified at level 2
        operator_notified = level >= 2

        missed.family_notified = family_notified
        missed.operator_notified = operator_notified
        if level >= 3:
            missed.risk_level_increased = True

        escalation = SafetyEscalation(
            escalation_type="missed_checkin",
            level=level,
            fisherman_id=schedule.fisherman_id,
            trip_id=schedule.trip_id,
            missed_checkin_id=missed.id,
            description=(
                f"Fisherman missed {consecutive} consecutive check-ins "
                f"(interval: {schedule.interval_minutes} min). "
                f"Level {level} escalation — {priority} priority."
            ),
            priority=priority,
            status="active",
            family_notified=family_notified,
            operator_notified=operator_notified,
            timeline_json=json.dumps([
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "event": "Missed Check-in Escalation",
                    "details": f"Consecutive misses: {consecutive}, Level: {level}",
                }
            ]),
        )
        db.add(escalation)
        db.flush()

        missed.escalation_id = escalation.id
        db.flush()

    @staticmethod
    def _check_stale_gps_escalations(db: Session) -> int:
        """Check for stale GPS + bad weather escalation (Level 3+ trigger)."""
        now = datetime.utcnow()
        threshold = now - timedelta(minutes=CheckInService.STALE_GPS_THRESHOLD_MINUTES * 2)

        active_trips = (
            db.query(Trip)
            .filter(Trip.end_time.is_(None))
            .all()
        )

        created = 0
        for trip in active_trips:
            latest_gps = (
                db.query(LocationPing)
                .filter(LocationPing.trip_id == trip.id)
                .order_by(desc(LocationPing.recorded_at))
                .first()
            )

            if not latest_gps or latest_gps.recorded_at > threshold:
                continue

            # Check if already has an active stale_gps_weather escalation
            existing = (
                db.query(SafetyEscalation)
                .filter(
                    and_(
                        SafetyEscalation.trip_id == trip.id,
                        SafetyEscalation.escalation_type == "stale_gps_bad_weather",
                        SafetyEscalation.status == "active",
                    )
                )
                .first()
            )
            if existing:
                continue

            minutes_stale = int((now - latest_gps.recorded_at).total_seconds() / 60)

            escalation = SafetyEscalation(
                escalation_type="stale_gps_bad_weather",
                level=3,
                fisherman_id=trip.user_id,
                trip_id=trip.id,
                description=(
                    f"Stale GPS for {minutes_stale} minutes. "
                    f"Location: {latest_gps.latitude},{latest_gps.longitude}. "
                    "Possible bad weather or equipment failure."
                ),
                priority="high",
                status="active",
                family_notified=True,
                operator_notified=True,
                timeline_json=json.dumps([
                    {
                        "timestamp": now.isoformat(),
                        "event": "Stale GPS Escalation",
                        "details": f"GPS stale for {minutes_stale} minutes — auto-escalated",
                    }
                ]),
            )
            db.add(escalation)
            created += 1

        if created:
            db.commit()

        return created

    @staticmethod
    def get_active_schedules_for_trip(trip_id: int, db: Session) -> List[CheckInSchedule]:
        """Get all active schedules for a trip."""
        return (
            db.query(CheckInSchedule)
            .filter(
                and_(
                    CheckInSchedule.trip_id == trip_id,
                    CheckInSchedule.is_active == True,
                )
            )
            .all()
        )

    # ── Legacy monitoring ─────────────────────────────────────────────────

    @staticmethod
    def monitor_active_trips(db: Session) -> dict:
        """Background task: Monitor active trips for missed check-ins (legacy)."""
        threshold_time = datetime.utcnow() - timedelta(
            minutes=CheckInService.STALE_GPS_THRESHOLD_MINUTES
        )
        offline_threshold = datetime.utcnow() - timedelta(
            minutes=CheckInService.OFFLINE_THRESHOLD_MINUTES
        )

        active_trips = db.query(Trip).filter(Trip.end_time.is_(None)).all()

        alerts_created = 0
        for trip in active_trips:
            latest_gps = (
                db.query(LocationPing)
                .filter(LocationPing.trip_id == trip.id)
                .order_by(desc(LocationPing.recorded_at))
                .first()
            )

            if latest_gps and latest_gps.recorded_at < threshold_time:
                existing_alert = (
                    db.query(CheckinAlert)
                    .filter(
                        and_(
                            CheckinAlert.trip_id == trip.id,
                            CheckinAlert.alert_type == "no_gps_updates",
                            CheckinAlert.dismissed == False,
                        )
                    )
                    .first()
                )

                if not existing_alert:
                    CheckInService.create_alert(
                        trip_id=trip.id,
                        fisherman_id=trip.user_id,
                        alert_type="no_gps_updates",
                        threshold_value="30 minutes",
                        description=f"No GPS updates for {int((datetime.utcnow() - latest_gps.recorded_at).total_seconds() / 60)} minutes",
                        db=db,
                    )
                    alerts_created += 1

            if latest_gps and latest_gps.recorded_at < offline_threshold:
                existing_alert = (
                    db.query(CheckinAlert)
                    .filter(
                        and_(
                            CheckinAlert.trip_id == trip.id,
                            CheckinAlert.alert_type == "offline_too_long",
                            CheckinAlert.dismissed == False,
                        )
                    )
                    .first()
                )

                if not existing_alert:
                    CheckInService.create_alert(
                        trip_id=trip.id,
                        fisherman_id=trip.user_id,
                        alert_type="offline_too_long",
                        threshold_value="45 minutes",
                        description=f"Fisherman offline for {int((datetime.utcnow() - latest_gps.recorded_at).total_seconds() / 60)} minutes",
                        db=db,
                    )
                    alerts_created += 1

        return {"status": "completed", "alerts_created": alerts_created}
