import pytest

from app.database import engine, Base, SessionLocal
from app.event_bus import EventBus
from app.models.notification_models import NotificationEventStream


@pytest.fixture(scope="module")
def setup_db():
    # create tables for new models in the test DB (SQLite or configured DB)
    Base.metadata.create_all(bind=engine)
    yield
    # cleanup left to test harness or manual


def test_eventbus_publish_creates_row(setup_db):
    db = SessionLocal()
    try:
        payload = {"test": "data"}
        metadata = {"source": "unit_test"}
        event_id, corr = EventBus.publish(db, event_type="unit.test", payload=payload, metadata=metadata, priority="HIGH", source_module="tests")
        row = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
        assert row is not None
        assert row.correlation_id == corr
        assert row.event_type == "unit.test"
        assert row.payload_json.get("test") == "data"
    finally:
        db.close()
