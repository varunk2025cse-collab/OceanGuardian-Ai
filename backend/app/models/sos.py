"""
SOS / distress alerts — extended for Phase 2.

New columns (all nullable — backward-compatible with existing rows):
  priority        : triage level set by the operator (low/medium/high/critical)
  rescue_notes    : free-text field for operator to log actions taken
  acknowledged_by : FK to the operator who acknowledged this alert
  resolved_by     : FK to the operator who resolved this alert

The security hole noted in Phase 1 analysis is fixed in the router
(app/routers/sos.py), not in this model. The model is data-only.
"""
import enum
import uuid

from sqlalchemy import Column, Integer, Float, String, DateTime, ForeignKey, Enum, func, Text
from sqlalchemy.orm import relationship

from app.database import Base


class SOSStatus(str, enum.Enum):
    active = "active"
    acknowledged = "acknowledged"
    resolved = "resolved"
    false_alarm = "false_alarm"


class SOSPriority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class SOSAlert(Base):
    __tablename__ = "sos_alerts"

    id = Column(Integer, primary_key=True, index=True)
    client_uuid = Column(String(36), unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    trip_id = Column(Integer, ForeignKey("trips.id"), nullable=True, index=True)
    alert_type = Column(String(100), nullable=True)

    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    accuracy_meters = Column(Float, nullable=True)
    battery_level_percent = Column(Integer, nullable=True)
    network_type = Column(String(20), nullable=True)  # V2 core build — device state at trigger
    message = Column(Text, nullable=True)

    status = Column(Enum(SOSStatus), nullable=False, default=SOSStatus.active, index=True)

    # --- Phase 2 additions (nullable for backward compatibility) ---
    priority = Column(String(20), nullable=True)          # SOSPriority value, stored as string
    rescue_notes = Column(Text, nullable=True)
    acknowledged_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    acknowledged_at = Column(DateTime(timezone=True), nullable=True)
    resolved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    # --------------------------------------------------------------

    triggered_at = Column(DateTime(timezone=True), nullable=False)
    received_at = Column(DateTime(timezone=True), server_default=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    resolved_note = Column(Text, nullable=True)

    # Relationships — explicit foreign_keys because multiple FKs point at users
    user = relationship("User", back_populates="sos_alerts", foreign_keys=[user_id])
    trip = relationship("Trip", foreign_keys=[trip_id])
    acknowledged_by_user = relationship("User", foreign_keys=[acknowledged_by])
    resolved_by_user = relationship("User", foreign_keys=[resolved_by])

    def __init__(self, *args, **kwargs):
        if "fisherman_id" in kwargs and "user_id" not in kwargs:
            kwargs["user_id"] = kwargs.pop("fisherman_id")
        if "created_at" in kwargs and "triggered_at" not in kwargs:
            kwargs["triggered_at"] = kwargs.pop("created_at")
        if "timestamp" in kwargs and "triggered_at" not in kwargs:
            kwargs["triggered_at"] = kwargs.pop("timestamp")
        if "client_uuid" not in kwargs:
            kwargs["client_uuid"] = str(uuid.uuid4())
        super().__init__(*args, **kwargs)
