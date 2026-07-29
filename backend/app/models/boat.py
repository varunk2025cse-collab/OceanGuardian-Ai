"""
Boat model — extended for Boat Management Enterprise (migration 009).

Phase 2 introduced the core Boat entity.  Migration 009 adds:
  - 7-state status lifecycle with soft delete and optimistic locking
  - Vessel classification, hull, and extended engine metadata
  - Verification workflow and QR code token
  - 7 new related tables: documents, crew, inspections, equipment,
    status history (append-only), audit log (append-only), ownership transfers

safety_equipment (TEXT) is kept for backward compatibility; new code
should use boat_equipment_items instead.
"""
from sqlalchemy import Column, Integer, Float, String, Boolean, Text, DateTime, Date, ForeignKey, func
from sqlalchemy.orm import relationship

from app.database import Base


class Boat(Base):
    __tablename__ = "boats"

    # ── Phase 2 original columns — DO NOT CHANGE ──────────────────────────────
    id = Column(Integer, primary_key=True, index=True)
    owner_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(120), nullable=False)
    registration_number = Column(String(60), unique=True, nullable=True, index=True)
    color = Column(String(60), nullable=True)
    length_meters = Column(Float, nullable=True)
    engine_type = Column(String(80), nullable=True)
    engine_horsepower = Column(Integer, nullable=True)
    fuel_capacity_liters = Column(Float, nullable=True)
    # Deprecated: use boat_equipment_items. Kept for backward compat.
    safety_equipment = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # ── Migration 009 additions ───────────────────────────────────────────────
    # Status: registered → active → inactive/maintenance/emergency/lost/damaged/decommissioned
    status = Column(String(30), nullable=False, server_default="active", index=True)

    # Vessel classification
    vessel_class = Column(String(50), nullable=True)
    hull_material = Column(String(50), nullable=True)
    beam_meters = Column(Float, nullable=True)
    draft_meters = Column(Float, nullable=True)
    year_built = Column(Integer, nullable=True)

    # Extended engine metadata
    engine_make = Column(String(80), nullable=True)
    engine_model = Column(String(80), nullable=True)
    engine_serial_number = Column(String(80), nullable=True)
    engine_year = Column(Integer, nullable=True)

    # Home harbor FK
    home_harbor_id = Column(Integer, ForeignKey("harbors.id", ondelete="SET NULL"), nullable=True, index=True)

    # Verification workflow
    verification_status = Column(String(30), nullable=False, server_default="unverified", index=True)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)

    # QR code and photos
    qr_code_token = Column(String(255), unique=True, nullable=True)
    photo_urls = Column(Text, nullable=True)   # JSON array of URLs

    # Soft delete and optimistic locking
    deleted_at = Column(DateTime, nullable=True, index=True)
    version = Column(Integer, nullable=False, server_default="1")

    # Audit who created/last updated
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    # ── Relationships ─────────────────────────────────────────────────────────
    owner = relationship("User", back_populates="boats", foreign_keys="[Boat.owner_id]")
    trips = relationship("Trip", back_populates="boat")
    documents = relationship("BoatDocument", back_populates="boat", cascade="all, delete-orphan")
    crew_members = relationship("BoatCrewMember", back_populates="boat", cascade="all, delete-orphan")
    inspections = relationship("BoatInspection", back_populates="boat", cascade="all, delete-orphan")
    equipment_items = relationship("BoatEquipmentItem", back_populates="boat", cascade="all, delete-orphan")
    status_history = relationship("BoatStatusHistory", back_populates="boat", cascade="all, delete-orphan",
                                  order_by="BoatStatusHistory.created_at")
    audit_logs = relationship("BoatAuditLog", back_populates="boat", cascade="all, delete-orphan",
                              order_by="BoatAuditLog.created_at")
    ownership_transfers = relationship("BoatOwnershipTransfer", back_populates="boat",
                                       foreign_keys="BoatOwnershipTransfer.boat_id",
                                       cascade="all, delete-orphan")

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


# =============================================================================
# Migration 009 — new tables
# =============================================================================

class BoatDocument(Base):
    """Regulatory and compliance documents attached to a boat."""
    __tablename__ = "boat_documents"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    document_type = Column(String(50), nullable=False, index=True)
    document_number = Column(String(120), nullable=True)
    issuing_authority = Column(String(120), nullable=True)
    issue_date = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True, index=True)
    file_url = Column(String(500), nullable=True)
    file_hash = Column(String(64), nullable=True)   # SHA-256 for integrity
    is_verified = Column(Boolean, nullable=False, default=False)
    verified_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    verified_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    boat = relationship("Boat", back_populates="documents")


class BoatCrewMember(Base):
    """Crew assigned to a boat — may or may not be a registered User."""
    __tablename__ = "boat_crew_members"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    full_name = Column(String(120), nullable=False)
    phone_number = Column(String(20), nullable=True)
    aadhaar_last4 = Column(String(4), nullable=True)   # last 4 digits only — never full number
    role = Column(String(50), nullable=False)
    is_primary_contact = Column(Boolean, nullable=False, default=False)
    is_active = Column(Boolean, nullable=False, default=True)
    assigned_at = Column(DateTime, nullable=False, server_default=func.now())
    removed_at = Column(DateTime, nullable=True)
    removal_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    boat = relationship("Boat", back_populates="crew_members")


class BoatInspection(Base):
    """Safety and regulatory inspections with pass/fail/conditional results."""
    __tablename__ = "boat_inspections"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    inspection_type = Column(String(50), nullable=False)
    inspector_name = Column(String(120), nullable=True)
    inspector_authority = Column(String(120), nullable=True)
    inspection_date = Column(Date, nullable=False, index=True)
    next_due_date = Column(Date, nullable=True)
    result = Column(String(20), nullable=False, index=True)
    findings = Column(Text, nullable=True)
    corrective_actions = Column(Text, nullable=True)
    certificate_number = Column(String(80), nullable=True)
    certificate_url = Column(String(500), nullable=True)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    boat = relationship("Boat", back_populates="inspections")


class BoatEquipmentItem(Base):
    """Normalized safety and operational equipment inventory per boat.
    Replaces the free-text safety_equipment JSON column."""
    __tablename__ = "boat_equipment_items"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    item_name = Column(String(120), nullable=False)
    quantity = Column(Integer, nullable=False, default=1)
    condition = Column(String(20), nullable=False, default="good", index=True)
    last_checked_at = Column(Date, nullable=True)
    expiry_date = Column(Date, nullable=True)
    notes = Column(Text, nullable=True)
    is_mandatory = Column(Boolean, nullable=False, default=False)
    deleted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    boat = relationship("Boat", back_populates="equipment_items")


class BoatStatusHistory(Base):
    """Immutable record of every boat status transition — append-only."""
    __tablename__ = "boat_status_history"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    previous_status = Column(String(30), nullable=True)
    new_status = Column(String(30), nullable=False)
    reason = Column(Text, nullable=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    source = Column(String(30), nullable=False, server_default="manual")
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    # NO updated_at — this table is append-only

    boat = relationship("Boat", back_populates="status_history")
    actor = relationship("User", foreign_keys=[actor_id])


class BoatAuditLog(Base):
    """Immutable audit trail for all boat-related changes — append-only.
    Rows are never updated or deleted once written."""
    __tablename__ = "boat_audit_logs"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    action = Column(String(50), nullable=False, index=True)
    target_table = Column(String(60), nullable=True)
    target_id = Column(Integer, nullable=True)
    old_values = Column(Text, nullable=True)    # JSON snapshot before change
    new_values = Column(Text, nullable=True)    # JSON snapshot after change
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(255), nullable=True)
    correlation_id = Column(String(64), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now(), index=True)
    # NEVER updated or deleted

    boat = relationship("Boat", back_populates="audit_logs")
    actor = relationship("User", foreign_keys=[actor_id])


class BoatOwnershipTransfer(Base):
    """Ownership transfer requests with approval workflow."""
    __tablename__ = "boat_ownership_transfers"

    id = Column(Integer, primary_key=True)
    boat_id = Column(Integer, ForeignKey("boats.id", ondelete="CASCADE"), nullable=False, index=True)
    from_owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    to_owner_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    transfer_date = Column(Date, nullable=False)
    transfer_reason = Column(String(50), nullable=True)
    document_url = Column(String(500), nullable=True)
    document_hash = Column(String(64), nullable=True)
    status = Column(String(20), nullable=False, server_default="pending", index=True)
    approved_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(DateTime, nullable=False, server_default=func.now(), onupdate=func.now())

    boat = relationship("Boat", back_populates="ownership_transfers", foreign_keys=[boat_id])
    from_owner = relationship("User", foreign_keys=[from_owner_id])
    to_owner = relationship("User", foreign_keys=[to_owner_id])
    approved_by_user = relationship("User", foreign_keys=[approved_by])
