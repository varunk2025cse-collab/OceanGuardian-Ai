"""
Lightweight EventBus placed at app/event_bus.py to avoid adding new packages directories in this sprint.
Provides publish/fetch helpers built on SQLAlchemy models defined in app.models.notification_models.
"""
from datetime import datetime, timezone
import uuid
from typing import Any, Dict, Tuple

from sqlalchemy.orm import Session

from app.models.notification_models import NotificationEventStream


class EventBus:
    @staticmethod
    def _new_correlation_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def publish(db: Session, *, event_type: str, payload: Dict[str, Any], metadata: Dict[str, Any] | None = None, correlation_id: str | None = None, priority: str = "NORMAL", source_module: str | None = None) -> Tuple[int, str]:
        if correlation_id is None:
            correlation_id = EventBus._new_correlation_id()
        row = NotificationEventStream(
            event_type=event_type,
            payload_json=payload,
            metadata_json=metadata or {},
            correlation_id=correlation_id,
            priority=priority,
            source_module=source_module,
            status="CREATED",
            created_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id, correlation_id

    @staticmethod
    def fetch_unprocessed(db: Session, limit: int = 100):
        return (
            db.query(NotificationEventStream)
            .filter(NotificationEventStream.status == "CREATED")
            .order_by(NotificationEventStream.created_at)
            .limit(limit)
            .all()
        )

    @staticmethod
    def mark_processing(db: Session, event_id: int):
        row = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
        if not row:
            return False
        row.status = "PROCESSING"
        row.processed_at = datetime.now(timezone.utc)
        db.commit()
        return True

    @staticmethod
    def mark_completed(db: Session, event_id: int):
        row = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
        if not row:
            return False
        row.status = "COMPLETED"
        row.processed_at = datetime.now(timezone.utc)
        db.commit()
        return True
