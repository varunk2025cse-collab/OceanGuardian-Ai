"""
User model — extended for Phase 2.

Changes from MVP:
  - UserRole gains `operator` value (for rescue/coast-guard dashboard accounts).
  - Relationships extended: boats, trips, operated_sos.
  - No columns removed; all additions are nullable or have defaults.
"""
import enum

from sqlalchemy import Column, Integer, String, Boolean, DateTime, Enum, func
from sqlalchemy.orm import relationship

from app.database import Base


class UserRole(str, enum.Enum):
    fisherman = "fisherman"
    family = "family"
    operator = "operator"          # rescue coordinator / coast-guard dashboard user


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    phone_number = Column(String(20), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.fisherman)

    # Fisherman-specific (nullable for family / operator accounts)
    boat_name = Column(String(120), nullable=True)
    boat_registration_number = Column(String(60), nullable=True)
    home_harbor = Column(String(120), nullable=True)

    preferred_language = Column(String(10), nullable=False, default="ta")
    emergency_contact_name = Column(String(120), nullable=True)
    emergency_contact_phone = Column(String(20), nullable=True)

    last_sync_at = Column(DateTime(timezone=True), nullable=True)  # Track last location sync

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    locations = relationship("LocationPing", back_populates="user", cascade="all, delete-orphan",
                             foreign_keys="LocationPing.user_id")
    sos_alerts = relationship("SOSAlert", back_populates="user", cascade="all, delete-orphan",
                               foreign_keys="SOSAlert.user_id")
    boats = relationship("Boat", back_populates="owner", cascade="all, delete-orphan",
                          foreign_keys="[Boat.owner_id]")
    trips = relationship("Trip", back_populates="user", cascade="all, delete-orphan",
                          foreign_keys="Trip.user_id")

    def __init__(self, *args, **kwargs):
        if "name" in kwargs and "full_name" not in kwargs:
            kwargs["full_name"] = kwargs.pop("name")
        if "fisherman_id" in kwargs and "id" not in kwargs:
            kwargs["id"] = kwargs.pop("fisherman_id")
        if "hashed_password" in kwargs and "password_hash" not in kwargs:
            kwargs["password_hash"] = kwargs.pop("hashed_password")
        if "role" in kwargs and isinstance(kwargs["role"], str):
            try:
                kwargs["role"] = UserRole(kwargs["role"])
            except ValueError:
                pass
        super().__init__(*args, **kwargs)


class TokenBlocklist(Base):
    """Stores revoked JWT tokens until they naturally expire."""
    __tablename__ = "token_blocklist"
    
    id = Column(Integer, primary_key=True, index=True)
    jti = Column(String(255), unique=True, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

