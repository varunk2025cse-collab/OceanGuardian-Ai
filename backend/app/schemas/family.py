from datetime import datetime
from pydantic import BaseModel


class FamilyLinkCreate(BaseModel):
    fisherman_phone_number: str
    relation: str | None = None


class FishermanStatusOut(BaseModel):
    """What a family member sees for one linked fisherman."""
    fisherman_id: int
    full_name: str
    boat_name: str | None
    last_latitude: float | None
    last_longitude: float | None
    last_seen_at: datetime | None
    active_sos: bool
    # LIVE/RECENT/LAST_KNOWN/STALE/UNKNOWN — computed server-side
    # (app.services.tracking_service.compute_freshness) so the app never
    # has to guess, and never shows a stale point as if it were live.
    freshness: str
    # SAFE/MONITOR/CAUTION/HIGH_RISK/CRITICAL/UNKNOWN — computed server-side
    # (app.services.safety_engine.SafetyEngine). UNKNOWN when no trip is
    # in progress — never inferred as "safe" from silence.
    safety_state: str
    incident_status: str | None = None  # open incident's status, if any

