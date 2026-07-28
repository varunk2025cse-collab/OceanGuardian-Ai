"""Check-in schemas."""
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel


class CheckInScheduleCreate(BaseModel):
    """Create check-in schedule."""
    trip_id: int
    interval_minutes: int = 30  # Default 30-minute check-ins


class CheckInScheduleResponse(BaseModel):
    """Check-in schedule response."""
    id: int
    trip_id: int
    fisherman_id: int
    interval_minutes: int
    next_checkin_at: Optional[datetime]
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class CheckInResponse(BaseModel):
    """Check-in response from fisherman."""
    trip_id: int
    status: str = "safe"
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    notes: Optional[str] = None


class CheckInRespondRequest(BaseModel):
    """Check-in respond request body."""
    schedule_id: int
    status: str = "safe"  # safe, help_needed, busy
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    notes: Optional[str] = None
    synced: bool = True  # False for offline-captured response


class CheckInRespondResponse(BaseModel):
    """Check-in respond response."""
    id: int
    schedule_id: int
    trip_id: int
    status: str
    responded_at: datetime
    next_checkin_due: datetime


class MissedCheckInDetail(BaseModel):
    """Missed check-in details."""
    id: int
    trip_id: int
    fisherman_id: int
    fisherman_name: str
    last_seen: Optional[datetime]
    missed_count: int
    consecutive_missed: int
    status: str
    escalated: bool
    created_at: datetime


class CheckInStatusResponse(BaseModel):
    """Check-in status."""
    trip_id: int
    fisherman_id: int
    last_checkin: Optional[datetime]
    next_checkin_due: Optional[datetime]
    status: str  # active, warning, alert
    missed_count: int
    schedule_id: Optional[int] = None
    interval_minutes: Optional[int] = None


class EscalationRequest(BaseModel):
    """Escalation request."""
    alert_id: int
    escalation_level: int
    reason: str


class OperatorAwarenessRequest(BaseModel):
    """Operator awareness for missed check-in escalation."""
    missed_checkin_id: int
    operator_id: int
    action: str  # notify_family, notify_operator, escalate
    notes: Optional[str] = None
