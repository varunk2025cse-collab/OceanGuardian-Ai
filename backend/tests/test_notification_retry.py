from datetime import datetime, timedelta

from app.core.security import hash_password
from app.models.phase5 import FamilyNotification
from app.models.user import User, UserRole
from app.services.notification_service import NotificationEngine


def test_retry_failed_notification_marks_delivered_on_success(db, monkeypatch):
    fisherman = User(phone_number='+912500000001', password_hash=hash_password('x'), full_name='Retry Fisher', role=UserRole.fisherman, preferred_language='en')
    family_member = User(phone_number='+912500000002', password_hash=hash_password('x'), full_name='Retry Family', role=UserRole.family, preferred_language='en')
    db.add_all([fisherman, family_member])
    db.commit()
    db.refresh(family_member)

    notification = FamilyNotification(
        family_member_id=family_member.id,
        notification_type='push',
        message='Test failure',
        related_event_id=123,
        delivery_status='failed',
        retry_count=0,
        created_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    class FakeProvider:
        def send(self, *, to_user_id, message, priority):
            return type('R', (), {'status': 'sent', 'detail': 'ok', 'simulated': False})()

    monkeypatch.setattr('app.services.notification_service.NotificationEngine._select_provider', staticmethod(lambda: FakeProvider()))

    count = NotificationEngine.retry_failed_notifications(db)
    db.refresh(notification)

    assert count == 1
    assert notification.delivery_status == 'delivered'
    assert notification.retry_count == 1
    assert notification.last_retry_at is not None


def test_retry_failed_notification_skips_old_or_maxed_out_rows(db, monkeypatch):
    fisherman = User(phone_number='+912500000003', password_hash=hash_password('x'), full_name='Retry Old Fisher', role=UserRole.fisherman, preferred_language='en')
    family_member = User(phone_number='+912500000004', password_hash=hash_password('x'), full_name='Retry Old Family', role=UserRole.family, preferred_language='en')
    db.add_all([fisherman, family_member])
    db.commit()
    db.refresh(family_member)

    old_notification = FamilyNotification(
        family_member_id=family_member.id,
        notification_type='push',
        message='Old failure',
        related_event_id=124,
        delivery_status='failed',
        retry_count=0,
        created_at=datetime.utcnow() - timedelta(hours=25),
    )
    maxed_notification = FamilyNotification(
        family_member_id=family_member.id,
        notification_type='push',
        message='Maxed failure',
        related_event_id=125,
        delivery_status='failed',
        retry_count=3,
        created_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db.add_all([old_notification, maxed_notification])
    db.commit()

    class FakeProvider:
        def send(self, *, to_user_id, message, priority):
            return type('R', (), {'status': 'failed', 'detail': 'still bad', 'simulated': False})()

    monkeypatch.setattr('app.services.notification_service.NotificationEngine._select_provider', staticmethod(lambda: FakeProvider()))

    count = NotificationEngine.retry_failed_notifications(db)

    assert count == 0
    db.refresh(old_notification)
    db.refresh(maxed_notification)
    assert old_notification.retry_count == 0
    assert maxed_notification.retry_count == 3


def test_retry_failed_notification_provider_crash_increments_retry_count(db, monkeypatch):
    fisherman = User(phone_number='+912500000005', password_hash=hash_password('x'), full_name='Retry Crash Fisher', role=UserRole.fisherman, preferred_language='en')
    family_member = User(phone_number='+912500000006', password_hash=hash_password('x'), full_name='Retry Crash Family', role=UserRole.family, preferred_language='en')
    db.add_all([fisherman, family_member])
    db.commit()
    db.refresh(family_member)

    notification = FamilyNotification(
        family_member_id=family_member.id,
        notification_type='push',
        message='Crash failure',
        related_event_id=126,
        delivery_status='failed',
        retry_count=1,
        created_at=datetime.utcnow() - timedelta(minutes=10),
    )
    db.add(notification)
    db.commit()
    db.refresh(notification)

    class BrokenProvider:
        def send(self, *, to_user_id, message, priority):
            raise RuntimeError('provider crash')

    monkeypatch.setattr('app.services.notification_service.NotificationEngine._select_provider', staticmethod(lambda: BrokenProvider()))

    count = NotificationEngine.retry_failed_notifications(db)
    db.refresh(notification)

    assert count == 0
    assert notification.retry_count == 2
    assert notification.last_retry_at is not None
    assert notification.delivery_status == 'failed'
