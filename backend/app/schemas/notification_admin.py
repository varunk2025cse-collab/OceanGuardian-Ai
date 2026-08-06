from datetime import datetime
from pydantic import BaseModel
from typing import Any, Dict


class NotificationEventOut(BaseModel):
    id: int
    event_type: str
    payload_json: Dict[str, Any]
    metadata_json: Dict[str, Any] | None = None
    correlation_id: str
    priority: str | None = None
    source_module: str | None = None
    status: str
    processed_at: datetime | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PublishEventIn(BaseModel):
    event_type: str
    payload_json: Dict[str, Any]
    metadata_json: Dict[str, Any] | None = None
    correlation_id: str | None = None
    priority: str | None = "NORMAL"
    source_module: str | None = None


class PaginatedEvents(BaseModel):
    items: list[NotificationEventOut]
    total: int
    skip: int
    limit: int
