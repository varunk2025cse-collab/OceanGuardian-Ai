from app.event_bus import EventBus
from app.services.event_processor import EventProcessor
from app.models.user import User
from app.models.family_link import FamilyLink
from app.models.notification_models import NotificationEventStream, NotificationQueueItem, NotificationLifecycleEvent


def test_event_processor_processes_family_notification(db):
    fisherman = User(
        phone_number="+919900000001",
        password_hash="hashed-password",
        full_name="Fisherman One",
        role="fisherman",
    )
    family_user = User(
        phone_number="+919900000002",
        password_hash="hashed-password",
        full_name="Family Member",
        role="family",
    )
    db.add_all([fisherman, family_user])
    db.commit()
    db.refresh(fisherman)
    db.refresh(family_user)

    link = FamilyLink(fisherman_id=fisherman.id, family_user_id=family_user.id, relation="Spouse")
    db.add(link)
    db.commit()

    payload = {
        "fisherman_id": fisherman.id,
        "message": "Emergency! Please respond.",
        "related_event_id": 123,
        "notification_type": "push",
    }
    event_id, correlation_id = EventBus.publish(db, event_type="family.notification.request", payload=payload, metadata={"priority": "HIGH"}, source_module="family_portal")

    created = EventProcessor.process_events(db, limit=10)

    event = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
    assert event is not None
    assert event.status == "COMPLETED"
    assert event.correlation_id == correlation_id
    assert created == 1

    queue_items = db.query(NotificationQueueItem).filter(NotificationQueueItem.event_id == event_id).all()
    assert len(queue_items) == 1
    assert queue_items[0].status == "QUEUED"
    assert queue_items[0].payload_json.get("body") == "Emergency! Please respond."

    lifecycle_events = db.query(NotificationLifecycleEvent).filter(NotificationLifecycleEvent.notification_item_id == queue_items[0].id).all()
    assert len(lifecycle_events) == 1
    assert lifecycle_events[0].state == "QUEUED"
