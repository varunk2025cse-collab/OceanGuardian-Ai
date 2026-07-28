"""Emergency Escalation Engine — Smart SOS workflow and escalation management.

Week 3 enhancements:
  - SafetyEscalation model for persisted escalation records
  - OperatorActionLog for audit trail
  - Escalate stale GPS + bad weather
  - Escalate missed check-ins via Schedule
  - Auto priority upgrade
  - Comprehensive escalation timeline
"""
import json
from datetime import datetime, timedelta
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, desc, or_
from app.models.sos import SOSAlert, SOSStatus
from app.models.user import User
from app.models.trip import Trip
from app.models.phase5 import (
    CheckinAlert, SafetyEscalation, MissedCheckIn, OperatorActionLog,
)
from app.schemas.escalation import (
    EscalationDetail, EscalationListItem, EscalationTimelineEvent,
    OperatorActionLogResponse,
)


class EscalationEngine:
    """Emergency Escalation Engine."""

    # Escalation thresholds (minutes)
    LEVEL_1_THRESHOLD = 15   # Family notified
    LEVEL_2_THRESHOLD = 30   # Rescue operator notified
    LEVEL_3_THRESHOLD = 60   # High-priority escalation
    LEVEL_4_THRESHOLD = 120  # Critical unresolved alert

    # ── SafetyEscalation-based API ─────────────────────────────────────────

    @staticmethod
    def get_active_safety_escalations(db: Session, limit: int = 50) -> List[EscalationListItem]:
        """Get active SafetyEscalation records."""
        escalations = (
            db.query(SafetyEscalation)
            .filter(SafetyEscalation.status == "active")
            .order_by(
                SafetyEscalation.priority.desc(),
                SafetyEscalation.created_at.desc(),
            )
            .limit(limit)
            .all()
        )

        result = []
        for es in escalations:
            fisherman = db.query(User).filter(User.id == es.fisherman_id).first()
            elapsed = (datetime.utcnow() - es.created_at).total_seconds() / 60

            result.append(
                EscalationListItem(
                    id=es.id,
                    escalation_type=es.escalation_type,
                    level=es.level,
                    fisherman_name=fisherman.full_name if fisherman else "Unknown",
                    priority=es.priority,
                    status=es.status,
                    created_at=es.created_at,
                    time_elapsed_minutes=int(elapsed),
                )
            )

        return result

    @staticmethod
    def get_safety_escalation_detail(
        escalation_id: int, db: Session
    ) -> Optional[EscalationDetail]:
        """Get detailed SafetyEscalation info."""
        es = db.query(SafetyEscalation).filter(SafetyEscalation.id == escalation_id).first()
        if not es:
            return None

        fisherman = db.query(User).filter(User.id == es.fisherman_id).first()
        timeline_data = json.loads(es.timeline_json or "[]")

        timeline = [
            EscalationTimelineEvent(
                timestamp=item.get("timestamp", es.created_at.isoformat()),
                event=item.get("event", "Event"),
                details=item.get("details", ""),
            )
            for item in timeline_data
        ]

        # If no timeline, build from scratch
        if not timeline:
            timeline = EscalationEngine._build_default_timeline(es)

        return EscalationDetail(
            id=es.id,
            escalation_type=es.escalation_type,
            level=es.level,
            fisherman_id=es.fisherman_id,
            fisherman_name=fisherman.full_name if fisherman else "Unknown",
            trip_id=es.trip_id,
            sos_alert_id=es.sos_alert_id,
            missed_checkin_id=es.missed_checkin_id,
            description=es.description,
            priority=es.priority,
            status=es.status,
            acknowledged_by_id=es.acknowledged_by_id,
            acknowledged_at=es.acknowledged_at,
            resolved_by_id=es.resolved_by_id,
            resolved_at=es.resolved_at,
            family_notified=es.family_notified,
            operator_notified=es.operator_notified,
            resolution=es.resolution,
            outcome=es.outcome,
            created_at=es.created_at,
            timeline=timeline,
        )

    @staticmethod
    def _build_default_timeline(es: SafetyEscalation) -> List[EscalationTimelineEvent]:
        """Build default timeline from escalation state."""
        events = []

        events.append(EscalationTimelineEvent(
            timestamp=es.created_at.isoformat(),
            event=f"Escalation Created — Level {es.level}",
            details=es.description[:100] if es.description else f"{es.escalation_type} escalation",
        ))

        if es.acknowledged_at:
            events.append(EscalationTimelineEvent(
                timestamp=es.acknowledged_at.isoformat(),
                event="Acknowledged by Operator",
                details=f"Operator ID: {es.acknowledged_by_id}",
            ))

        if es.resolved_at:
            events.append(EscalationTimelineEvent(
                timestamp=es.resolved_at.isoformat(),
                event="Resolved",
                details=f"Outcome: {es.outcome or 'Unknown'} — {es.resolution or 'No details'}",
            ))

        if es.family_notified:
            events.append(EscalationTimelineEvent(
                timestamp=es.created_at.isoformat(),
                event="Family Notified",
                details="Safety notification sent to family members",
            ))

        if es.operator_notified:
            events.append(EscalationTimelineEvent(
                timestamp=es.acknowledged_at.isoformat() if es.acknowledged_at else es.created_at.isoformat(),
                event="Operator Notified",
                details="Rescue operator has been alerted",
            ))

        return events

    @staticmethod
    def acknowledge_safety_escalation(
        escalation_id: int, operator_id: int, notes: Optional[str], db: Session
    ) -> dict:
        """Acknowledge a SafetyEscalation."""
        es = db.query(SafetyEscalation).filter(SafetyEscalation.id == escalation_id).first()
        if not es:
            return {"status": "error", "message": "Escalation not found"}

        if es.status != "active":
            return {"status": "error", "message": f"Escalation is already {es.status}"}

        now = datetime.utcnow()
        es.status = "acknowledged"
        es.acknowledged_by_id = operator_id
        es.acknowledged_at = now

        # Add to timeline
        timeline = json.loads(es.timeline_json or "[]")
        timeline.append({
            "timestamp": now.isoformat(),
            "event": "Acknowledged by Operator",
            "details": f"Operator ID: {operator_id}. Notes: {notes or 'None'}",
        })
        es.timeline_json = json.dumps(timeline)

        # Log operator action
        EscalationEngine._log_operator_action(
            db, operator_id, "acknowledged", escalation_id,
            f"Acknowledged {es.escalation_type} escalation (Level {es.level})"
        )

        db.commit()
        return {"status": "success", "message": "Escalation acknowledged"}

    @staticmethod
    def resolve_safety_escalation(
        escalation_id: int,
        operator_id: int,
        resolution: str,
        outcome: str,
        db: Session,
    ) -> dict:
        """Resolve a SafetyEscalation."""
        es = db.query(SafetyEscalation).filter(SafetyEscalation.id == escalation_id).first()
        if not es:
            return {"status": "error", "message": "Escalation not found"}

        if es.status == "resolved":
            return {"status": "error", "message": "Escalation already resolved"}

        now = datetime.utcnow()
        es.status = "resolved"
        es.resolved_by_id = operator_id
        es.resolved_at = now
        es.resolution = resolution
        es.outcome = outcome

        # Add to timeline
        timeline = json.loads(es.timeline_json or "[]")
        timeline.append({
            "timestamp": now.isoformat(),
            "event": "Resolved",
            "details": f"Outcome: {outcome}. Resolution: {resolution}",
        })
        es.timeline_json = json.dumps(timeline)

        # Also resolve linked MissedCheckIn if any
        if es.missed_checkin_id:
            missed = db.query(MissedCheckIn).filter(MissedCheckIn.id == es.missed_checkin_id).first()
            if missed and not missed.resolved_at:
                missed.resolved_at = now

        # Log operator action
        EscalationEngine._log_operator_action(
            db, operator_id, "resolved", escalation_id,
            f"Resolved {es.escalation_type} escalation. Outcome: {outcome}."
        )

        db.commit()
        return {"status": "success", "message": "Escalation resolved"}

    @staticmethod
    def _log_operator_action(
        db: Session, operator_id: int, action_type: str,
        escalation_id: int, description: str,
    ):
        """Log an operator action."""
        log = OperatorActionLog(
            operator_id=operator_id,
            action_type=action_type,
            escalation_id=escalation_id,
            description=description,
        )
        db.add(log)
        db.flush()

    @staticmethod
    def get_operator_action_log(
        escalation_id: int, db: Session, limit: int = 50
    ) -> List[OperatorActionLogResponse]:
        """Get operator action log for an escalation."""
        logs = (
            db.query(OperatorActionLog)
            .filter(OperatorActionLog.escalation_id == escalation_id)
            .order_by(OperatorActionLog.created_at.desc())
            .limit(limit)
            .all()
        )

        result = []
        for log in logs:
            operator = db.query(User).filter(User.id == log.operator_id).first()
            result.append(OperatorActionLogResponse(
                id=log.id,
                operator_id=log.operator_id,
                operator_name=operator.full_name if operator else None,
                action_type=log.action_type,
                description=log.description,
                created_at=log.created_at,
            ))

        return result

    # ── Legacy Escalation API (uses CheckinAlert / SOSAlert) ───────────────

    @staticmethod
    def get_active_escalations(db: Session, limit: int = 50) -> List[EscalationListItem]:
        """Get list of active escalations (combines SOS + SafetyEscalation)."""
        # First, get SafetyEscalation records
        safety_results = EscalationEngine.get_active_safety_escalations(db, limit)

        # Also get unacknowledged SOS alerts
        threshold_time = datetime.utcnow() - timedelta(
            minutes=EscalationEngine.LEVEL_2_THRESHOLD
        )
        unack_sos = (
            db.query(SOSAlert)
            .filter(
                and_(
                    SOSAlert.status == SOSStatus.active,
                    SOSAlert.triggered_at < threshold_time,
                )
            )
            .order_by(desc(SOSAlert.triggered_at))
            .all()
        )

        for sos in unack_sos:
            elapsed = (datetime.utcnow() - sos.created_at).total_seconds() / 60
            level = EscalationEngine._calculate_escalation_level(elapsed)
            priority = EscalationEngine._calculate_priority(level, "sos_unacknowledged")

            # Check if there's already a SafetyEscalation for this SOS
            existing = (
                db.query(SafetyEscalation)
                .filter(
                    and_(
                        SafetyEscalation.sos_alert_id == sos.id,
                        SafetyEscalation.status == "active",
                    )
                )
                .first()
            )
            if existing:
                continue

            fisherman = db.query(User).filter(User.id == sos.user_id).first()
            safety_results.append(
                EscalationListItem(
                    id=sos.id,
                    escalation_type="sos_unacknowledged",
                    level=level,
                    fisherman_name=fisherman.full_name if fisherman else "Unknown",
                    priority=priority,
                    status="active",
                    created_at=sos.created_at,
                    time_elapsed_minutes=int(elapsed),
                )
            )

        # Sort by priority then elapsed time
        priority_order = {"critical": 0, "high": 1, "normal": 2}
        safety_results.sort(
            key=lambda x: (priority_order.get(x.priority, 3), -x.time_elapsed_minutes)
        )

        return safety_results[:limit]

    @staticmethod
    def get_escalation_detail(escalation_id: int, db: Session) -> Optional[EscalationDetail]:
        """Get detailed escalation information (checks SafetyEscalation first, then SOS)."""
        # Try SafetyEscalation first
        detail = EscalationEngine.get_safety_escalation_detail(escalation_id, db)
        if detail:
            return detail

        # Try SOS alert
        sos = db.query(SOSAlert).filter(SOSAlert.id == escalation_id).first()
        if sos:
            return EscalationEngine._build_sos_escalation_detail(sos, db)

        return None

    @staticmethod
    def _build_sos_escalation_detail(sos: SOSAlert, db: Session) -> EscalationDetail:
        """Build escalation detail from SOS alert."""
        fisherman = db.query(User).filter(User.id == sos.user_id).first()
        elapsed = (datetime.utcnow() - sos.triggered_at).total_seconds() / 60
        level = EscalationEngine._calculate_escalation_level(elapsed)
        priority = EscalationEngine._calculate_priority(level, "sos_unacknowledged")

        timeline = [
            EscalationTimelineEvent(
                timestamp=sos.triggered_at.isoformat(),
                event="SOS Alert Triggered",
                details=sos.message or "Emergency alert",
            )
        ]

        if sos.acknowledged_at:
            timeline.append(
                EscalationTimelineEvent(
                    timestamp=sos.acknowledged_at.isoformat(),
                    event="Acknowledged by Operator",
                    details=f"ID: {sos.acknowledged_by}",
                )
            )

        if sos.resolved_at:
            timeline.append(
                EscalationTimelineEvent(
                    timestamp=sos.resolved_at.isoformat(),
                    event="Resolved",
                    details=f"By: {sos.resolved_by}",
                )
            )

        status = "resolved" if sos.resolved_at else (
            "acknowledged" if sos.acknowledged_at else "active"
        )

        return EscalationDetail(
            id=sos.id,
            escalation_type="sos_unacknowledged",
            level=level,
            fisherman_id=sos.user_id,
            fisherman_name=fisherman.full_name if fisherman else "Unknown",
            trip_id=sos.trip_id,
            sos_alert_id=sos.id,
            missed_checkin_id=None,
            description=f"SOS Alert: {sos.message or 'Unknown'}",
            priority=priority,
            status=status,
            acknowledged_by_id=sos.acknowledged_by,
            acknowledged_at=sos.acknowledged_at,
            resolved_by_id=sos.resolved_by,
            resolved_at=sos.resolved_at,
            family_notified=False,
            operator_notified=bool(sos.acknowledged_at),
            resolution=None,
            outcome=None,
            created_at=sos.triggered_at,
            timeline=timeline,
        )

    # ── Legacy methods (CheckinAlert-based) ───────────────────────────────

    @staticmethod
    def acknowledge_escalation(
        escalation_id: int, operator_id: int, notes: Optional[str], db: Session
    ) -> dict:
        """Acknowledge an escalation (routes to correct handler)."""
        # Try SafetyEscalation first
        result = EscalationEngine.acknowledge_safety_escalation(
            escalation_id, operator_id, notes, db
        )
        if result["status"] == "success":
            return result

        # Try SOS alert
        sos = db.query(SOSAlert).filter(SOSAlert.id == escalation_id).first()
        if sos:
            if not sos.acknowledged_at:
                sos.acknowledged_at = datetime.utcnow()
                sos.acknowledged_by = operator_id
                if notes:
                    sos.rescue_notes = (sos.rescue_notes or "") + f"\n{notes}"
                db.commit()
            return {"status": "success", "message": "SOS alert acknowledged"}

        # Try check-in alert
        alert_id = escalation_id - 10000
        alert = db.query(CheckinAlert).filter(CheckinAlert.id == alert_id).first()
        if alert:
            alert.rescue_operator_notified = True
            if notes:
                alert.resolution_notes = notes
            db.commit()
            return {"status": "success", "message": "Check-in alert acknowledged"}

        return {"status": "error", "message": "Escalation not found"}

    @staticmethod
    def resolve_escalation(
        escalation_id: int,
        operator_id: int,
        resolution: str,
        outcome: str,
        db: Session,
    ) -> dict:
        """Resolve an escalation (routes to correct handler)."""
        # Try SafetyEscalation first
        result = EscalationEngine.resolve_safety_escalation(
            escalation_id, operator_id, resolution, outcome, db
        )
        if result["status"] == "success":
            return result

        # Try SOS alert
        sos = db.query(SOSAlert).filter(SOSAlert.id == escalation_id).first()
        if sos:
            if not sos.resolved_at:
                sos.resolved_at = datetime.utcnow()
                sos.resolved_by = operator_id
                sos.rescue_notes = (sos.rescue_notes or "") + f"\nResolution: {resolution}"
                db.commit()
            return {"status": "success", "message": "SOS alert resolved"}

        # Try check-in alert
        alert_id = escalation_id - 10000
        alert = db.query(CheckinAlert).filter(CheckinAlert.id == alert_id).first()
        if alert:
            alert.dismissed = True
            alert.resolved_at = datetime.utcnow()
            alert.resolution_notes = f"{resolution} | Outcome: {outcome}"
            db.commit()
            return {"status": "success", "message": "Check-in alert resolved"}

        return {"status": "error", "message": "Escalation not found"}

    @staticmethod
    def _calculate_escalation_level(elapsed_minutes: float) -> int:
        """Calculate escalation level based on elapsed time."""
        if elapsed_minutes >= EscalationEngine.LEVEL_4_THRESHOLD:
            return 4
        elif elapsed_minutes >= EscalationEngine.LEVEL_3_THRESHOLD:
            return 3
        elif elapsed_minutes >= EscalationEngine.LEVEL_2_THRESHOLD:
            return 2
        else:
            return 1

    @staticmethod
    def _calculate_priority(level: int, escalation_type: str) -> str:
        """Calculate priority based on level and type."""
        if level >= 4:
            return "critical"
        elif level >= 3:
            return "high"
        elif level >= 2 and escalation_type == "sos_unacknowledged":
            return "high"
        else:
            return "normal"

    # ── Background tasks ───────────────────────────────────────────────────

    @staticmethod
    def auto_escalate_unacknowledged_sos(db: Session) -> dict:
        """Background task: Auto-escalate unacknowledged SOS alerts via SafetyEscalation."""
        threshold_time = datetime.utcnow() - timedelta(
            minutes=EscalationEngine.LEVEL_2_THRESHOLD
        )

        unack_sos = (
            db.query(SOSAlert)
            .filter(
                and_(
                    SOSAlert.acknowledged_at.is_(None),
                    SOSAlert.resolved_at.is_(None),
                    SOSAlert.triggered_at < threshold_time,
                )
            )
            .all()
        )

        escalated_count = 0
        for sos in unack_sos:
            # Check if already has a SafetyEscalation
            existing = (
                db.query(SafetyEscalation)
                .filter(
                    and_(
                        SafetyEscalation.sos_alert_id == sos.id,
                        SafetyEscalation.status.in_(["active", "acknowledged"]),
                    )
                )
                .first()
            )
            if existing:
                continue

            elapsed = (datetime.utcnow() - sos.triggered_at).total_seconds() / 60
            level = EscalationEngine._calculate_escalation_level(elapsed)
            priority = EscalationEngine._calculate_priority(level, "sos_unacknowledged")

            escalation = SafetyEscalation(
                escalation_type="sos_unacknowledged",
                level=level,
                fisherman_id=sos.user_id,
                trip_id=sos.trip_id,
                sos_alert_id=sos.id,
                description=f"Unacknowledged SOS: {sos.message or 'Emergency'} (escalated after {int(elapsed)} min)",
                priority=priority,
                status="active",
                family_notified=True,
                operator_notified=True,
                timeline_json=json.dumps([
                    {
                        "timestamp": datetime.utcnow().isoformat(),
                        "event": "Auto-Escalation",
                        "details": f"SOS unacknowledged for {int(elapsed)} min — Level {level} escalation",
                    }
                ]),
            )
            db.add(escalation)
            escalated_count += 1

        if escalated_count:
            db.commit()

        return {"status": "completed", "escalated_count": escalated_count}

    @staticmethod
    def auto_upgrade_priorities(db: Session) -> dict:
        """Background task: Auto-upgrade escalation priorities based on age."""
        now = datetime.utcnow()
        upgraded = 0

        active_escalations = (
            db.query(SafetyEscalation)
            .filter(SafetyEscalation.status == "active")
            .all()
        )

        for es in active_escalations:
            elapsed = (now - es.created_at).total_seconds() / 60
            new_level = EscalationEngine._calculate_escalation_level(elapsed)
            new_priority = EscalationEngine._calculate_priority(new_level, es.escalation_type)

            if new_level != es.level or new_priority != es.priority:
                es.level = new_level
                es.priority = new_priority
                upgraded += 1

                timeline = json.loads(es.timeline_json or "[]")
                timeline.append({
                    "timestamp": now.isoformat(),
                    "event": "Priority Upgraded",
                    "details": f"Auto-upgraded to Level {new_level} ({new_priority} priority)",
                })
                es.timeline_json = json.dumps(timeline)

        if upgraded:
            db.commit()

        return {"status": "completed", "upgraded_count": upgraded}
