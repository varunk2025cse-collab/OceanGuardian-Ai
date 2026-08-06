"""Admin notification endpoints: provider listing/health and event management.

Operator-only endpoints mounted under /api/v1/admin/notifications.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.core.deps import get_current_operator
from app.models.notification_models import NotificationEventStream
from app.notifications import provider_registry
from app.schemas.notification_admin import NotificationEventOut, PublishEventIn, PaginatedEvents
from app.models.user import User
from app.logging_config import logger
from app.observability import record_event_published, record_provider_health_check

router = APIRouter(prefix="/api/v1/admin/notifications", tags=["admin-notifications"])


@router.get("/providers")
def list_providers(current_op: User = Depends(get_current_operator)):
    logger.info("Operator %s requested provider list", current_op.id)
    return {"providers": provider_registry.list_providers()}


@router.get("/providers/health")
def providers_health(current_op: User = Depends(get_current_operator)):
    logger.info("Operator %s requested provider health", current_op.id)
    try:
        record_provider_health_check()
    except Exception:
        logger.exception("Failed to record provider health metric")
    return provider_registry.provider_health()


@router.get("/events", response_model=PaginatedEvents)
def list_events(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    event_type: Optional[str] = Query(default=None),
    current_op: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    query = db.query(NotificationEventStream)
    if event_type:
        query = query.filter(NotificationEventStream.event_type == event_type)
    total = query.count()
    items = query.order_by(NotificationEventStream.created_at.desc()).offset(skip).limit(limit).all()
    return PaginatedEvents(items=[NotificationEventOut.model_validate(i) for i in items], total=total, skip=skip, limit=limit)


@router.post("/events", response_model=NotificationEventOut, status_code=status.HTTP_201_CREATED)
def publish_event(payload: PublishEventIn, current_op: User = Depends(get_current_operator), db: Session = Depends(get_db)):
    # correlation_id default: use operator id + timestamp
    corr = payload.correlation_id or f"op-{current_op.id}-{int(datetime.utcnow().timestamp())}"
    ev = NotificationEventStream(
        event_type=payload.event_type,
        payload_json=payload.payload_json,
        metadata_json=payload.metadata_json,
        correlation_id=corr,
        priority=payload.priority or "NORMAL",
        source_module=payload.source_module,
        status="CREATED",
    )
    db.add(ev)
    db.commit()
    db.refresh(ev)
    # observability
    try:
        record_event_published()
    except Exception:
        logger.exception("Failed to record event published metric")
    logger.info("Operator %s published event %s id=%s", current_op.id, ev.event_type, ev.id)
    return NotificationEventOut.model_validate(ev)


@router.post("/events/{event_id}/replay")
def replay_event(event_id: int, current_op: User = Depends(get_current_operator), db: Session = Depends(get_db)):
    ev = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    ev.status = "CREATED"
    ev.processed_at = None
    db.commit()
    logger.info("Operator %s requested replay for event id=%s", current_op.id, ev.id)
    return {"ok": True}


@router.post("/events/{event_id}/cancel")
def cancel_event(event_id: int, current_op: User = Depends(get_current_operator), db: Session = Depends(get_db)):
    ev = db.query(NotificationEventStream).filter(NotificationEventStream.id == event_id).first()
    if not ev:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    ev.status = "CANCELLED"
    db.commit()
    logger.info("Operator %s cancelled event id=%s", current_op.id, ev.id)
    return {"ok": True}
