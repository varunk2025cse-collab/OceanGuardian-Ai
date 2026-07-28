"""
Trip model — Phase 2 new table.

A trip groups GPS pings into a meaningful voyage: start point, end point,
estimated return time, and status. This makes the family dashboard and
operator view dramatically more useful — instead of a stream of raw pings,
they see "Murugan left Nagapattinam at 05:30, expected back by 18:00,
currently 23km offshore, trip ACTIVE".

Status values (stored as String, not native PG enum, for SQLite compat):
  active    - trip in progress
  completed - fisherman returned
  emergency - SOS triggered during this trip
  cancelled - trip abandoned before departure
"""
from sqlalchemy import Column, Integer, Float, String, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class Trip(Base):
    __tablename__ = "trips"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    boat_id = Column(Integer, ForeignKey("boats.id"), nullable=True, index=True)

    status = Column(String(20), nullable=False, default="active", index=True)

    start_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    end_time = Column(DateTime(timezone=True), nullable=True)
    estimated_return_at = Column(DateTime(timezone=True), nullable=True)

    start_latitude = Column(Float, nullable=True)
    start_longitude = Column(Float, nullable=True)
    destination = Column(String(120), nullable=True)
    notes = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    user = relationship("User", back_populates="trips", foreign_keys=[user_id])
    boat = relationship("Boat", back_populates="trips")
    location_pings = relationship("LocationPing", back_populates="trip")

    def __init__(self, *args, **kwargs):
        if "fisherman_id" in kwargs and "user_id" not in kwargs:
            kwargs["user_id"] = kwargs.pop("fisherman_id")
        if "departure_harbor_id" in kwargs:
            kwargs.pop("departure_harbor_id")
        super().__init__(*args, **kwargs)
