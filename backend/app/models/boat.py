"""
Boat model — Phase 2 new table.

Separates the boat entity from the user entity: a fisherman can own
multiple boats (upgrade from the flat boat_name/boat_registration_number
fields that remain on users for backward compatibility), and each boat
has richer metadata (engine, fuel, safety checklist) needed by operators.

safety_equipment is stored as a JSON-encoded text string for SQLite
compatibility. PostgreSQL users could switch this to a JSONB column in
a future migration.
"""
from sqlalchemy import Column, Integer, Float, String, Boolean, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class Boat(Base):
    __tablename__ = "boats"

    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    name = Column(String(120), nullable=False)
    registration_number = Column(String(60), unique=True, nullable=True, index=True)
    color = Column(String(60), nullable=True)
    length_meters = Column(Float, nullable=True)

    engine_type = Column(String(80), nullable=True)
    engine_horsepower = Column(Integer, nullable=True)
    fuel_capacity_liters = Column(Float, nullable=True)

    # JSON-encoded list, e.g. '["Life jackets x4", "Fire extinguisher", "EPIRB"]'
    safety_equipment = Column(Text, nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    owner = relationship("User", back_populates="boats")
    trips = relationship("Trip", back_populates="boat")

    def __init__(self, *args, **kwargs):
        if "boat_name" in kwargs and "name" not in kwargs:
            kwargs["name"] = kwargs.pop("boat_name")
        if "boat_type" in kwargs and "engine_type" not in kwargs:
            kwargs["engine_type"] = kwargs.pop("boat_type")
        if "type" in kwargs and "engine_type" not in kwargs:
            kwargs["engine_type"] = kwargs.pop("type")
        if "owner" in kwargs and "owner_id" not in kwargs:
            kwargs["owner_id"] = kwargs.pop("owner")
        if "fisherman_id" in kwargs and "owner_id" not in kwargs:
            kwargs["owner_id"] = kwargs.pop("fisherman_id")
        super().__init__(*args, **kwargs)
