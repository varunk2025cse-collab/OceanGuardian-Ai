from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey, Boolean, Float, BigInteger, func
from sqlalchemy.orm import relationship
from app.database import Base


class NotificationEventStream(Base):
    __tablename__ = "notification_event_stream"

    id = Column(Integer, primary_key=True)
    event_type = Column(String(200), nullable=False)
    payload_json = Column(JSON, nullable=False)
    metadata_json = Column(JSON)
    correlation_id = Column(String(64), nullable=False, index=True)
    priority = Column(String(50), nullable=False, server_default="NORMAL")
    source_module = Column(String(100))
    status = Column(String(50), nullable=False, server_default="CREATED")
    processed_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class NotificationQueueItem(Base):
    __tablename__ = "notification_queue_items"

    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("notification_event_stream.id", ondelete="CASCADE"))
    recipient_user_id = Column(Integer, nullable=True)
    recipient_group_json = Column(JSON, nullable=True)
    channel = Column(String(50), nullable=False)
    provider_name = Column(String(100), nullable=True)
    payload_json = Column(JSON, nullable=False)
    priority = Column(String(50), nullable=False, server_default="NORMAL")
    status = Column(String(50), nullable=False, server_default="QUEUED")
    attempt_count = Column(Integer, nullable=False, default=0, server_default="0")
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    timeout_at = Column(DateTime(timezone=True), nullable=True)
    retry_deadline = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    correlation_id = Column(String(64), nullable=False, index=True)
    locked_by = Column(String(200), nullable=True)
    locked_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    event = relationship("NotificationEventStream", foreign_keys=[event_id])


class NotificationLifecycleEvent(Base):
    __tablename__ = "notification_lifecycle_events"

    id = Column(Integer, primary_key=True)
    notification_item_id = Column(Integer, ForeignKey("notification_queue_items.id", ondelete="CASCADE"))
    state = Column(String(50), nullable=False)
    detail = Column(Text, nullable=True)
    actor = Column(String(200), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    correlation_id = Column(String(64), nullable=False, index=True)


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id = Column(Integer, primary_key=True)
    name = Column(String(200), nullable=False)
    language = Column(String(10), nullable=False, server_default="en")
    version = Column(Integer, nullable=False, default=1)
    channel = Column(String(50), nullable=False)
    subject = Column(String(400), nullable=True)
    body = Column(Text, nullable=False)
    placeholders_json = Column(JSON, nullable=True)
    is_active = Column(Boolean, default=True)
    created_by = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NotificationPreference(Base):
    __tablename__ = "notification_preferences"

    user_id = Column(Integer, primary_key=True)
    preferred_language = Column(String(10), nullable=True)
    preferred_channels = Column(JSON, nullable=True)
    quiet_hours = Column(JSON, nullable=True)
    emergency_override = Column(Boolean, default=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class NotificationProviderHealth(Base):
    __tablename__ = "notification_provider_health"

    provider_name = Column(String(200), primary_key=True)
    channel_type = Column(String(50), nullable=True)
    success_count = Column(BigInteger, default=0)
    failure_count = Column(BigInteger, default=0)
    avg_latency_ms = Column(Float, nullable=True)
    avg_retry_count = Column(Float, nullable=True)
    last_failure_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    availability_score = Column(Float, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
