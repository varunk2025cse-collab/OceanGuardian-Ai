"""
Simple notification worker module placed at app/worker.py for Sprint-1.
See design notes in app/workers planned location for future refactor.
"""
import time
from datetime import datetime, timedelta
import socket

from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models.notification_models import NotificationQueueItem, NotificationLifecycleEvent
from app.services.provider_registry import ProviderRegistry


WORKER_ID = socket.gethostname()
DEFAULT_BACKOFF_SECONDS = 30


class NotificationWorker:
    def __init__(self, batch_size: int = 10, poll_interval: int = 5):
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self.running = False

    def run_one_batch(self):
        db: Session = SessionLocal()
        try:
            now = datetime.utcnow()
            items = (
                db.query(NotificationQueueItem)
                .filter(NotificationQueueItem.status == "QUEUED")
                .filter((NotificationQueueItem.next_retry_at == None) | (NotificationQueueItem.next_retry_at <= now))
                .order_by(NotificationQueueItem.priority)
                .limit(self.batch_size)
                .all()
            )
            for it in items:
                # claim
                it.status = "PROCESSING"
                it.locked_by = WORKER_ID
                it.locked_at = datetime.utcnow()
                db.commit()

                provider = ProviderRegistry.get_provider(it.channel)
                try:
                    # payload_json expected to contain 'body'
                    body = it.payload_json.get("body") if it.payload_json else ""
                    # provider expects to be called in a standardized way; our Simulation provider supports send(to_user_id, message...)
                    res = provider.send(to_user_id=it.recipient_user_id, message=body, priority=it.priority)
                    # record lifecycle
                    lle = NotificationLifecycleEvent(
                        notification_item_id=it.id,
                        state="SENT" if res.status in ("sent", "simulated") else "FAILED",
                        detail=res.detail,
                        actor=WORKER_ID,
                        correlation_id=it.correlation_id,
                        created_at=datetime.utcnow(),
                    )
                    db.add(lle)

                    if res.status in ("sent", "simulated"):
                        it.status = "SENT"
                        it.attempt_count = it.attempt_count + 1 if it.attempt_count else 1
                    else:
                        # failure
                        it.attempt_count = it.attempt_count + 1 if it.attempt_count else 1
                        backoff = DEFAULT_BACKOFF_SECONDS * (2 ** (it.attempt_count - 1))
                        it.next_retry_at = datetime.utcnow() + timedelta(seconds=backoff)
                        it.status = "QUEUED"
                        it.last_error = res.detail

                    it.updated_at = datetime.utcnow()
                    db.commit()
                except Exception as e:
                    db.rollback()
                    # mark attempt and reschedule
                    it.attempt_count = (it.attempt_count or 0) + 1
                    it.next_retry_at = datetime.utcnow() + timedelta(seconds=DEFAULT_BACKOFF_SECONDS)
                    it.last_error = str(e)
                    it.status = "QUEUED"
                    it.updated_at = datetime.utcnow()
                    db.add(NotificationLifecycleEvent(notification_item_id=it.id, state="FAILED", detail=str(e), actor=WORKER_ID, correlation_id=it.correlation_id, created_at=datetime.utcnow()))
                    db.commit()
        finally:
            db.close()

    def run(self):
        self.running = True
        while self.running:
            try:
                self.run_one_batch()
            except Exception:
                # ensure worker doesn't crash; log later as needed
                pass
            time.sleep(self.poll_interval)

    def stop(self):
        self.running = False
