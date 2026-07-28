"""Escalation schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class EscalationTimelineEvent(BaseModel):
    """Timeline event in escalation."""
    timestamp: str
    event: str
    details: str


class EscalationDetail(BaseModel):
    """Escalation detail."""
    id: int
    escalation_type: str  # sos_unacknowledged, missed_checkin, stale_gps_bad_weather
    level: int  # 1-4
    fisherman_id: int
    fisherman_name: str
    trip_id: Optional[int]
    sos_alert_id: Optional[int]
    missed_checkin_id: Optional[int]
    description: str
    priority: str  # normal, high, critical
    status: str  # active, acknowledged, resolved
    acknowledged_by_id: Optional[int]
    acknowledged_at: Optional[datetime]
    resolved_by_id: Optional[int]
    resolved_at: Optional[datetime]
    family_notified: bool = False
    operator_notified: bool = False
    resolution: Optional[str] = None
    outcome: Optional[str] = None
    created_at: datetime
    timeline: List[EscalationTimelineEvent]


class EscalationAcknowledge(BaseModel):
    """Acknowledge escalation."""
    notes: Optional[str] = None


class EscalationResolve(BaseModel):
    """Resolve escalation."""
    resolution: str
    outcome: str  # resolved_safe, resolved_assisted, false_alarm


class EscalationListItem(BaseModel):
    """Escalation list item."""
    id: int
    escalation_type: str
    level: int
    fisherman_name: str
    priority: str
    status: str
    created_at: datetime
    time_elapsed_minutes: int


class OperatorActionLogResponse(BaseModel):
    """Operator action log entry."""
    id: int
    operator_id: int
    operator_name: Optional[str] = None
    action_type: str
    description: Optional[str]
    created_at: datetime
