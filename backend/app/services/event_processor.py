"""
Event Processor: converts events from notification_event_stream into notification_queue_items.
Scope: handle "family.notification.request" events for Sprint-1.

Behavior:
- fetch unprocessed events
- for family.notification.request, resolve family links to recipients
- create NotificationQueueItem rows (one per family member, channel from payload/metadata)
- record initial lifecycle event
- mark event COMPLETED when queued
"""
from datetime import datetime
from typing import List

from sqlalchemy.orm import Session

from app.models.notification_models import (
    NotificationEventStream,
    NotificationQueueItem,
    NotificationLifecycleEvent,
)
from app.models.family_link import FamilyLink
from app.models.user import User


class EventProcessor:
    @staticmethod
    def process_events(db: Session, limit: int = 100) -> int:
        """Process up to `limit` events. Returns number of queue items created."""
        events: List[NotificationEventStream] = (
            db.query(NotificationEventStream)
            .filter(NotificationEventStream.status == "CREATED")
            .order_by(NotificationEventStream.created_at)
            .limit(limit)
            .all()
        )
        total_created = 0
        for ev in events:
            try:
                ev.status = "PROCESSING"
                ev.processed_at = datetime.utcnow()
                db.commit()

                if ev.event_type == "family.notification.request":
                    payload = ev.payload_json or {}
                    fisherman_id = payload.get("fisherman_id")
                    message = payload.get("message")
                    related_event_id = payload.get("related_event_id")
                    notification_type = payload.get("notification_type", "push")

                    links = db.query(FamilyLink).filter(FamilyLink.fisherman_id == fisherman_id).all()
                    for link in links:
                        # Resolve recipient user existence
                        recipient = db.query(User).filter(User.id == link.family_user_id).first()
                        if not recipient:
                            continue
                        # Deduplication: ensure no existing queue item for same event+recipient
                        exists = (
                            db.query(NotificationQueueItem)
                            .filter(
                                NotificationQueueItem.event_id == ev.id,
                                NotificationQueueItem.recipient_user_id == recipient.id,
                                NotificationQueueItem.channel == notification_type,
                            )
                            .first()
                        )
                        if exists:
                            continue

                        q = NotificationQueueItem(
                            event_id=ev.id,
                            recipient_user_id=recipient.id,
                            channel=notification_type,
                            payload_json={"body": message},
                            priority=ev.priority or "NORMAL",
                            status="QUEUED",
                            correlation_id=ev.correlation_id,
                            created_at=datetime.utcnow(),
                            updated_at=datetime.utcnow(),
                        )
                        db.add(q)
                        db.commit()
                        db.refresh(q)

                        # lifecycle: CREATED -> QUEUED
                        lle = NotificationLifecycleEvent(
                            notification_item_id=q.id,
                            state="QUEUED",
                            detail="Queued by EventProcessor",
                            actor="event_processor",
                            correlation_id=ev.correlation_id,
                            created_at=datetime.utcnow(),
                        )
                        db.add(lle)
                        db.commit()
                        total_created += 1

                # mark event completed
                ev.status = "COMPLETED"
                ev.processed_at = datetime.utcnow()
                db.commit()
            except Exception:
                db.rollback()
                # leave the event in CREATED or mark failed — for now set to CREATED for retry
        return total_created
