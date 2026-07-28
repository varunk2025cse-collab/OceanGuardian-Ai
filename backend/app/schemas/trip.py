from datetime import datetime
from pydantic import BaseModel, Field


class TripStart(BaseModel):
    boat_id: int | None = None
    start_latitude: float | None = Field(default=None, ge=-90, le=90)
    start_longitude: float | None = Field(default=None, ge=-180, le=180)
    destination: str | None = None
    estimated_return_at: datetime | None = None
    notes: str | None = None


class TripEnd(BaseModel):
    notes: str | None = None


class TripTransition(BaseModel):
    status: str = Field(..., pattern="^(planned|active|returning|completed|cancelled|emergency)$")
    notes: str | None = None


class TripOut(BaseModel):
    id: int
    user_id: int
    boat_id: int | None
    status: str
    start_time: datetime
    end_time: datetime | None
    estimated_return_at: datetime | None
    start_latitude: float | None
    start_longitude: float | None
    destination: str | None
    notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
