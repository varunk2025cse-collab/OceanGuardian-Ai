"""Boat Repository — all database access for the Boat aggregate.

Isolates every SQL query behind typed methods so the service layer
never constructs queries directly.  All methods accept an open
SQLAlchemy Session and return ORM objects or None — no HTTP concerns,
no business rules, no logging here.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.boat import (
    Boat,
    BoatAuditLog,
    BoatCrewMember,
    BoatDocument,
    BoatEquipmentItem,
    BoatInspection,
    BoatOwnershipTransfer,
    BoatStatusHistory,
)


class BoatRepository:
    """All DB access for the Boat aggregate — no business logic."""

    # ── Boat core ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_by_id(db: Session, boat_id: int) -> Optional[Boat]:
        return (
            db.query(Boat)
            .filter(Boat.id == boat_id, Boat.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def get_by_id_including_deleted(db: Session, boat_id: int) -> Optional[Boat]:
        return db.query(Boat).filter(Boat.id == boat_id).first()

    @staticmethod
    def get_by_registration(db: Session, registration_number: str) -> Optional[Boat]:
        """Case-insensitive lookup — registration numbers are unique regardless of case."""
        return (
            db.query(Boat)
            .filter(
                func.upper(Boat.registration_number) == registration_number.upper(),
                Boat.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def get_by_qr_token(db: Session, token: str) -> Optional[Boat]:
        return (
            db.query(Boat)
            .filter(Boat.qr_code_token == token, Boat.deleted_at.is_(None))
            .first()
        )

    @staticmethod
    def list_by_owner(
        db: Session,
        owner_id: int,
        include_inactive: bool = False,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Boat], int]:
        q = db.query(Boat).filter(
            Boat.owner_id == owner_id,
            Boat.deleted_at.is_(None),
        )
        if not include_inactive:
            q = q.filter(Boat.is_active.is_(True))
        total = q.count()
        boats = (
            q.order_by(Boat.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return boats, total

    @staticmethod
    def list_all(
        db: Session,
        status: Optional[str] = None,
        harbor_id: Optional[int] = None,
        owner_id: Optional[int] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Boat], int]:
        q = db.query(Boat).filter(Boat.deleted_at.is_(None))
        if status:
            q = q.filter(Boat.status == status)
        if harbor_id:
            q = q.filter(Boat.home_harbor_id == harbor_id)
        if owner_id:
            q = q.filter(Boat.owner_id == owner_id)
        if search:
            pattern = f"%{search}%"
            q = q.filter(
                Boat.name.ilike(pattern) | Boat.registration_number.ilike(pattern)
            )
        total = q.count()
        boats = (
            q.order_by(Boat.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return boats, total

    @staticmethod
    def has_active_trip(db: Session, boat_id: int) -> bool:
        from app.models.trip import Trip
        return (
            db.query(Trip)
            .filter(Trip.boat_id == boat_id, Trip.status == "active")
            .first()
        ) is not None

    @staticmethod
    def save(db: Session, boat: Boat) -> Boat:
        db.add(boat)
        db.flush()
        db.refresh(boat)
        return boat

    # ── Status history (append-only) ──────────────────────────────────────────

    @staticmethod
    def append_status_history(
        db: Session,
        boat_id: int,
        previous_status: Optional[str],
        new_status: str,
        actor_id: Optional[int],
        reason: Optional[str],
        source: str = "manual",
    ) -> BoatStatusHistory:
        entry = BoatStatusHistory(
            boat_id=boat_id,
            previous_status=previous_status,
            new_status=new_status,
            actor_id=actor_id,
            reason=reason,
            source=source,
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def get_status_history(db: Session, boat_id: int) -> list[BoatStatusHistory]:
        return (
            db.query(BoatStatusHistory)
            .filter(BoatStatusHistory.boat_id == boat_id)
            .order_by(BoatStatusHistory.created_at.desc())
            .all()
        )

    # ── Audit log (append-only) ───────────────────────────────────────────────

    @staticmethod
    def append_audit_log(
        db: Session,
        boat_id: int,
        actor_id: Optional[int],
        action: str,
        target_table: Optional[str] = None,
        target_id: Optional[int] = None,
        old_values: Optional[str] = None,
        new_values: Optional[str] = None,
        ip_address: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ) -> BoatAuditLog:
        entry = BoatAuditLog(
            boat_id=boat_id,
            actor_id=actor_id,
            action=action,
            target_table=target_table,
            target_id=target_id,
            old_values=old_values,
            new_values=new_values,
            ip_address=ip_address,
            correlation_id=correlation_id,
        )
        db.add(entry)
        db.flush()
        return entry

    @staticmethod
    def get_audit_log(
        db: Session,
        boat_id: int,
        action: Optional[str] = None,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[BoatAuditLog], int]:
        q = db.query(BoatAuditLog).filter(BoatAuditLog.boat_id == boat_id)
        if action:
            q = q.filter(BoatAuditLog.action == action)
        if from_dt:
            q = q.filter(BoatAuditLog.created_at >= from_dt)
        if to_dt:
            q = q.filter(BoatAuditLog.created_at <= to_dt)
        total = q.count()
        logs = (
            q.order_by(BoatAuditLog.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )
        return logs, total

    # ── Documents ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_document(db: Session, boat_id: int, doc_id: int) -> Optional[BoatDocument]:
        return (
            db.query(BoatDocument)
            .filter(
                BoatDocument.id == doc_id,
                BoatDocument.boat_id == boat_id,
                BoatDocument.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def list_documents(
        db: Session,
        boat_id: int,
        document_type: Optional[str] = None,
        include_expired: bool = True,
    ) -> list[BoatDocument]:
        q = db.query(BoatDocument).filter(
            BoatDocument.boat_id == boat_id,
            BoatDocument.deleted_at.is_(None),
        )
        if document_type:
            q = q.filter(BoatDocument.document_type == document_type)
        if not include_expired:
            today = datetime.utcnow().date()
            q = q.filter(
                (BoatDocument.expiry_date.is_(None)) | (BoatDocument.expiry_date >= today)
            )
        return q.order_by(BoatDocument.created_at.desc()).all()

    @staticmethod
    def save_document(db: Session, doc: BoatDocument) -> BoatDocument:
        db.add(doc)
        db.flush()
        db.refresh(doc)
        return doc

    # ── Crew ──────────────────────────────────────────────────────────────────

    @staticmethod
    def get_crew_member(db: Session, boat_id: int, crew_id: int) -> Optional[BoatCrewMember]:
        return (
            db.query(BoatCrewMember)
            .filter(
                BoatCrewMember.id == crew_id,
                BoatCrewMember.boat_id == boat_id,
                BoatCrewMember.is_active.is_(True),
            )
            .first()
        )

    @staticmethod
    def list_active_crew(db: Session, boat_id: int) -> list[BoatCrewMember]:
        return (
            db.query(BoatCrewMember)
            .filter(BoatCrewMember.boat_id == boat_id, BoatCrewMember.is_active.is_(True))
            .order_by(BoatCrewMember.assigned_at)
            .all()
        )

    @staticmethod
    def count_active_crew_by_role(db: Session, boat_id: int, role: str) -> int:
        return (
            db.query(BoatCrewMember)
            .filter(
                BoatCrewMember.boat_id == boat_id,
                BoatCrewMember.role == role,
                BoatCrewMember.is_active.is_(True),
            )
            .count()
        )

    @staticmethod
    def save_crew_member(db: Session, member: BoatCrewMember) -> BoatCrewMember:
        db.add(member)
        db.flush()
        db.refresh(member)
        return member

    # ── Inspections ───────────────────────────────────────────────────────────

    @staticmethod
    def list_inspections(db: Session, boat_id: int) -> list[BoatInspection]:
        return (
            db.query(BoatInspection)
            .filter(BoatInspection.boat_id == boat_id, BoatInspection.deleted_at.is_(None))
            .order_by(BoatInspection.inspection_date.desc())
            .all()
        )

    @staticmethod
    def save_inspection(db: Session, inspection: BoatInspection) -> BoatInspection:
        db.add(inspection)
        db.flush()
        db.refresh(inspection)
        return inspection

    # ── Equipment ─────────────────────────────────────────────────────────────

    @staticmethod
    def get_equipment_item(db: Session, boat_id: int, item_id: int) -> Optional[BoatEquipmentItem]:
        return (
            db.query(BoatEquipmentItem)
            .filter(
                BoatEquipmentItem.id == item_id,
                BoatEquipmentItem.boat_id == boat_id,
                BoatEquipmentItem.deleted_at.is_(None),
            )
            .first()
        )

    @staticmethod
    def list_equipment(
        db: Session,
        boat_id: int,
        category: Optional[str] = None,
        condition: Optional[str] = None,
    ) -> list[BoatEquipmentItem]:
        q = db.query(BoatEquipmentItem).filter(
            BoatEquipmentItem.boat_id == boat_id,
            BoatEquipmentItem.deleted_at.is_(None),
        )
        if category:
            q = q.filter(BoatEquipmentItem.category == category)
        if condition:
            q = q.filter(BoatEquipmentItem.condition == condition)
        return q.order_by(BoatEquipmentItem.category, BoatEquipmentItem.item_name).all()

    @staticmethod
    def save_equipment_item(db: Session, item: BoatEquipmentItem) -> BoatEquipmentItem:
        db.add(item)
        db.flush()
        db.refresh(item)
        return item

    # ── Ownership transfers ───────────────────────────────────────────────────

    @staticmethod
    def get_transfer(db: Session, boat_id: int, transfer_id: int) -> Optional[BoatOwnershipTransfer]:
        return (
            db.query(BoatOwnershipTransfer)
            .filter(
                BoatOwnershipTransfer.id == transfer_id,
                BoatOwnershipTransfer.boat_id == boat_id,
            )
            .first()
        )

    @staticmethod
    def get_pending_transfer(db: Session, boat_id: int) -> Optional[BoatOwnershipTransfer]:
        return (
            db.query(BoatOwnershipTransfer)
            .filter(
                BoatOwnershipTransfer.boat_id == boat_id,
                BoatOwnershipTransfer.status == "pending",
            )
            .first()
        )

    @staticmethod
    def save_transfer(db: Session, transfer: BoatOwnershipTransfer) -> BoatOwnershipTransfer:
        db.add(transfer)
        db.flush()
        db.refresh(transfer)
        return transfer

    # ── Fleet analytics ───────────────────────────────────────────────────────

    @staticmethod
    def count_by_status(db: Session) -> dict[str, int]:
        rows = (
            db.query(Boat.status, func.count(Boat.id))
            .filter(Boat.deleted_at.is_(None))
            .group_by(Boat.status)
            .all()
        )
        return {s: c for s, c in rows}

    @staticmethod
    def count_by_verification(db: Session) -> dict[str, int]:
        rows = (
            db.query(Boat.verification_status, func.count(Boat.id))
            .filter(Boat.deleted_at.is_(None))
            .group_by(Boat.verification_status)
            .all()
        )
        return {vs: c for vs, c in rows}

    @staticmethod
    def count_documents_expiring_within_days(db: Session, days: int) -> int:
        cutoff = datetime.utcnow().date()
        deadline = (datetime.utcnow() + timedelta(days=days)).date()
        return (
            db.query(BoatDocument)
            .filter(
                BoatDocument.deleted_at.is_(None),
                BoatDocument.expiry_date >= cutoff,
                BoatDocument.expiry_date <= deadline,
            )
            .count()
        )

    @staticmethod
    def count_boats_with_active_trips(db: Session) -> int:
        from app.models.trip import Trip
        return (
            db.query(Boat.id)
            .join(Trip, Trip.boat_id == Boat.id)
            .filter(Trip.status == "active", Boat.deleted_at.is_(None))
            .distinct()
            .count()
        )
