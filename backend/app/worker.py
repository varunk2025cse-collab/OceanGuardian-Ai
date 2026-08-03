"""
Notification worker (Sprint-1, minimal safe improvements):
- Priority ordering mapped to explicit numeric ordering
- Atomic claim attempt (best-effort without DB-specific SKIP LOCKED)
- Priority string -> NotificationPriority enum conversion with safe fallback
- Dead-letter handling when attempts exceed configured max
- Improved logging on errors

This file intentionally avoids introducing DB-specific SKIP LOCKED semantics so it remains runnable on CI (SQLite) while reducing race windows.
"""
import time
import logging
import random
from datetime import datetime, timedelta, timezone
import socket

from sqlalchemy.orm import Session
from sqlalchemy import case

from app.database import SessionLocal
from app.models.notification_models import NotificationQueueItem, NotificationLifecycleEvent
from app.services.provider_registry import ProviderRegistry
from app.config import settings
from app.services.notification_service import NotificationPriority


logger = logging.getLogger(__name__)
WORKER_ID = socket.gethostname()
DEFAULT_BACKOFF_SECONDS = 30


# simple mapping for priority ordering; lower number => higher priority
_PRIORITY_ORDER = {
    "CRITICAL": 1,
    "HIGH": 2,
    "NORMAL": 3,
    "MEDIUM": 3,
    "LOW": 4,
    "BACKGROUND": 5,
}


def _priority_order_expr(column):
    # build a SQL CASE expression to map priority strings to numeric order
    whens = [(column == k, v) for k, v in _PRIORITY_ORDER.items()]
    return case(whens, else_=99)


def _to_priority_enum(priority_str: str) -> NotificationPriority:
    if not priority_str:
        return NotificationPriority.medium
    try:
        # Try to construct from enum value (e.g., 'CRITICAL')
        return NotificationPriority(priority_str)
    except Exception:
        # Some places use 'NORMAL' in the DB — map it to MEDIUM
        if priority_str.upper() == "NORMAL":
            return NotificationPriority.medium
        # fallback to medium to avoid failures
        return NotificationPriority.medium


class NotificationWorker:
    def __init__(self, batch_size: int = 10, poll_interval: int = 5):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.running = False

    def run_one_batch(self):
        db: Session = SessionLocal()
        try:
            now = datetime.now(timezone.utc)
            # Order by explicit priority mapping to ensure CRITICAL -> LOW ordering
            items = (
                db.query(NotificationQueueItem)
                .filter(NotificationQueueItem.status == "QUEUED")
                .filter((NotificationQueueItem.next_retry_at == None) | (NotificationQueueItem.next_retry_at <= now))
                .order_by(_priority_order_expr(NotificationQueueItem.priority))
                .limit(self.batch_size)
                .all()
            )

            for it in items:
                # Attempt to atomically claim the item.
                # Use an UPDATE with WHERE status='QUEUED' so another worker that already
                # claimed it will prevent us from proceeding. synchronize_session=False
                rows_updated = (
                    db.query(NotificationQueueItem)
                    .filter(NotificationQueueItem.id == it.id, NotificationQueueItem.status == "QUEUED")
                    .update(
                        {
                            NotificationQueueItem.status: "PROCESSING",
                            NotificationQueueItem.locked_by: WORKER_ID,
                            NotificationQueueItem.locked_at: datetime.now(timezone.utc),
                        },
                        synchronize_session=False,
                    )
                )
                if not rows_updated:
                    # someone else claimed it in the window between our SELECT and UPDATE
                    continue

                db.commit()

                provider = ProviderRegistry.get_provider(it.channel)
                try:
                    # payload_json expected to contain 'body'
                    body = it.payload_json.get("body") if it.payload_json else ""

                    # Ensure we pass a NotificationPriority enum to providers
                    priority_enum = _to_priority_enum(it.priority)

                    res = provider.send(to_user_id=it.recipient_user_id, message=body, priority=priority_enum)

                    # record lifecycle
                    lle = NotificationLifecycleEvent(
                        notification_item_id=it.id,
                        state="SENT" if res.status in ("sent", "simulated") else "FAILED",
                        detail=res.detail,
                        actor=WORKER_ID,
                        correlation_id=it.correlation_id,
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(lle)

                    # increment attempt count and update status/backoff
                    it = db.query(NotificationQueueItem).get(it.id)  # refresh
                    it.attempt_count = (it.attempt_count or 0) + 1
                    now = datetime.now(timezone.utc)

                    if res.status in ("sent", "simulated"):
                        it.status = "SENT"
                        it.next_retry_at = None
                        it.locked_by = None
                        it.locked_at = None
                    else:
                        # failure: compute backoff
                        backoff = DEFAULT_BACKOFF_SECONDS * (2 ** (max(it.attempt_count - 1, 0)))
                        jitter = random.randint(0, settings.notification_retry_jitter_seconds)
                        it.next_retry_at = now + timedelta(seconds=backoff + jitter)

                        # check DLQ threshold
                        if it.attempt_count >= settings.notification_max_attempts:
                            it.status = "DEAD_LETTER"
                            it.next_retry_at = None
                            it.locked_by = None
                            it.locked_at = None
                            db.add(NotificationLifecycleEvent(notification_item_id=it.id, state="DEAD_LETTER", detail=res.detail, actor=WORKER_ID, correlation_id=it.correlation_id, created_at=now))
                        else:
                            it.status = "QUEUED"
                            it.locked_by = None
                            it.locked_at = None

                        it.last_error = res.detail

                    it.updated_at = now
                    db.commit()
                except Exception as e:
                    # provider raised unexpectedly — log and reschedule
                    logger.exception("Error sending notification item=%s: %s", it.id, e)
                    db.rollback()

                    # refresh item and increment
                    it = db.query(NotificationQueueItem).get(it.id)
                    it.attempt_count = (it.attempt_count or 0) + 1
                    now = datetime.now(timezone.utc)
                    it.next_retry_at = now + timedelta(seconds=DEFAULT_BACKOFF_SECONDS)
                    it.last_error = str(e)
                    it.locked_by = None
                    it.locked_at = None

                    if it.attempt_count >= settings.notification_max_attempts:
                        it.status = "DEAD_LETTER"
                        it.next_retry_at = None
                        db.add(NotificationLifecycleEvent(notification_item_id=it.id, state="DEAD_LETTER", detail=str(e), actor=WORKER_ID, correlation_id=it.correlation_id, created_at=now))
                    else:
                        it.status = "QUEUED"
                        db.add(NotificationLifecycleEvent(notification_item_id=it.id, state="FAILED", detail=str(e), actor=WORKER_ID, correlation_id=it.correlation_id, created_at=now))

                    it.updated_at = now
                    db.commit()
        finally:
            db.close()

    def run(self):
        self.running = True
        while self.running:
            try:
                self.run_one_batch()
            except Exception:
                # ensure worker doesn't crash; log and continue
                logger.exception("NotificationWorker encountered an error in run loop")
            time.sleep(self.poll_interval)

    def stop(self):
        self.running = False
