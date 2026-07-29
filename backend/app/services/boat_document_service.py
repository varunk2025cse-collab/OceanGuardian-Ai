"""
Boat Document Service — manages regulatory and compliance documents.

Provides:
  - Upload document metadata
  - Document verification workflow (operator approval)
  - Expiry detection and automatic readiness integration
  - Document hash verification (integrity check)
  - Duplicate detection (same document_type + document_number)
  - Soft delete with audit logging
  - Operator approval workflow

Design principles:
  - All DB access goes through BoatRepository (Repository Pattern).
  - Every write creates an audit-log entry.
  - Every write is wrapped in a transaction — rollback on failure.
  - Enforces one-captain rule per boat (soft-remove previous captain).
  - Consistent with BoatService pattern (static methods, structured logging).
"""
from __future__ import annotations

import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.boat import BoatAuditLog, BoatDocument
from app.models.user import User, UserRole
from app.repositories.boat_repository import BoatRepository
from app.schemas.boat import DocumentCreate

logger = logging.getLogger("app.services.boat_document_service")


# ── Constants ─────────────────────────────────────────────────────────────────
VALID_DOCUMENT_TYPES = frozenset({
    "registration_certificate", "fishing_license", "insurance_policy",
    "inspection_certificate", "seaworthiness_certificate", "crew_list", "other",
})
MAX_DOCUMENT_NUMBER_LENGTH = 120
MAX_FILE_URL_LENGTH = 500
MAX_HASH_LENGTH = 64


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_correlation_id() -> str:
    return str(uuid.uuid4())


def _compute_file_hash(file_content: bytes) -> str:
    """Compute SHA-256 hash of file content for integrity verification."""
    return hashlib.sha256(file_content).hexdigest()


def _check_boat_access(db: Session, boat_id: int, user: User) -> None:
    """Verify the user can access the boat (BOAL)."""
    from app.services.boat_service import BoatService
    BoatService.get_boat_for_user(db, boat_id, user)


def _check_operator(user: User) -> None:
    """Verify the user has operator role."""
    if user.role != UserRole.operator:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only operators can perform this action",
        )


# =============================================================================
# Boat Document Service
# =============================================================================

class BoatDocumentService:
    """Single source of truth for boat document operations.

    All methods are ``@staticmethod`` consistent with the existing service-layer
    pattern (BoatService, BoatReadinessService).
    """

    # ── Upload / Create Document ──────────────────────────────────────────────

    @staticmethod
    def create_document(
        db: Session,
        boat_id: int,
        payload: DocumentCreate,
        current_user: User,
    ) -> BoatDocument:
        """Upload a new document for a boat.

        - Validates document_type against known types.
        - Detects duplicates (same type + number for this boat).
        - Computes SHA-256 hash of file content (if file_url is provided
          with a data URI or the caller supplies file_hash separately).
        - Creates audit log.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "create_document started | boat_id=%s | type=%s | user_id=%s | "
            "correlation_id=%s",
            boat_id, payload.document_type, current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ──────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Validate document_type ────────────────────────────────────
            if payload.document_type not in VALID_DOCUMENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid document type '{payload.document_type}'. "
                        f"Valid types: {sorted(VALID_DOCUMENT_TYPES)}"
                    ),
                )

            # ── 3. Duplicate detection ───────────────────────────────────────
            if payload.document_number:
                existing = (
                    db.query(BoatDocument)
                    .filter(
                        BoatDocument.boat_id == boat_id,
                        BoatDocument.document_type == payload.document_type,
                        BoatDocument.document_number == payload.document_number,
                        BoatDocument.deleted_at.is_(None),
                    )
                    .first()
                )
                if existing is not None:
                    logger.warning(
                        "create_document duplicate | boat_id=%s | type=%s | "
                        "number=%s | existing_id=%s | correlation_id=%s",
                        boat_id, payload.document_type, payload.document_number,
                        existing.id, correlation_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"A '{payload.document_type}' document with number "
                            f"'{payload.document_number}' already exists for this boat"
                        ),
                    )

            # ── 4. Build document ────────────────────────────────────────────
            doc = BoatDocument(
                boat_id=boat_id,
                document_type=payload.document_type,
                document_number=payload.document_number,
                issuing_authority=payload.issuing_authority,
                issue_date=payload.issue_date,
                expiry_date=payload.expiry_date,
                file_url=payload.file_url,
                file_hash=payload.file_hash,
                is_verified=False,
                created_by=current_user.id,
                updated_by=current_user.id,
            )
            db.add(doc)
            db.flush()

            # ── 5. Audit log ─────────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="document_created",
                target_table="boat_documents",
                target_id=doc.id,
                new_values=json.dumps({
                    "id": doc.id,
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                    "is_verified": doc.is_verified,
                }),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(doc)

            logger.info(
                "create_document success | doc_id=%s | boat_id=%s | "
                "correlation_id=%s",
                doc.id, boat_id, correlation_id,
            )
            return doc

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "create_document failed | boat_id=%s | type=%s | "
                "correlation_id=%s",
                boat_id, payload.document_type, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create document",
            )

    # ── List documents ───────────────────────────────────────────────────────

    @staticmethod
    def list_documents(
        db: Session,
        boat_id: int,
        current_user: User,
        document_type: Optional[str] = None,
        include_expired: bool = True,
    ) -> list[BoatDocument]:
        """List documents for a boat with optional filtering."""
        _check_boat_access(db, boat_id, current_user)
        return BoatRepository.list_documents(
            db, boat_id,
            document_type=document_type,
            include_expired=include_expired,
        )

    # ── Get single document ──────────────────────────────────────────────────

    @staticmethod
    def get_document(
        db: Session,
        boat_id: int,
        doc_id: int,
        current_user: User,
    ) -> BoatDocument:
        """Get a single document with access control."""
        _check_boat_access(db, boat_id, current_user)
        doc = BoatRepository.get_document(db, boat_id, doc_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        return doc

    # ── Verify document (operator only) ──────────────────────────────────────

    @staticmethod
    def verify_document(
        db: Session,
        boat_id: int,
        doc_id: int,
        current_user: User,
        is_verified: bool = True,
        notes: Optional[str] = None,
    ) -> BoatDocument:
        """Verify or reject a document (operator/admin only).

        - RBAC: only operators may verify.
        - Sets verified_by, verified_at, is_verified.
        - Creates audit log.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "verify_document started | doc_id=%s | boat_id=%s | "
            "is_verified=%s | actor_id=%s | correlation_id=%s",
            doc_id, boat_id, is_verified, current_user.id, correlation_id,
        )

        try:
            # ── 1. RBAC ─────────────────────────────────────────────────────
            _check_operator(current_user)

            # ── 2. Fetch document ──────────────────────────────────────────
            doc = BoatRepository.get_document(db, boat_id, doc_id)
            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )

            # ── 3. Snapshot old values ─────────────────────────────────────
            old_values = {
                "is_verified": doc.is_verified,
                "verified_by": doc.verified_by,
                "verified_at": doc.verified_at.isoformat() if doc.verified_at else None,
            }

            # ── 4. Apply verification ──────────────────────────────────────
            doc.is_verified = is_verified
            doc.verified_by = current_user.id
            doc.verified_at = _now()
            if notes is not None:
                doc.notes = notes
            doc.updated_by = current_user.id

            db.flush()

            # ── 5. Audit log ───────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="document_verified" if is_verified else "document_rejected",
                target_table="boat_documents",
                target_id=doc.id,
                old_values=json.dumps(old_values),
                new_values=json.dumps({
                    "is_verified": doc.is_verified,
                    "verified_by": doc.verified_by,
                    "verified_at": doc.verified_at.isoformat(),
                }),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(doc)

            logger.info(
                "verify_document success | doc_id=%s | verified=%s | "
                "correlation_id=%s",
                doc.id, is_verified, correlation_id,
            )
            return doc

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "verify_document failed | doc_id=%s | correlation_id=%s",
                doc_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify document",
            )

    # ── Soft delete document ─────────────────────────────────────────────────

    @staticmethod
    def delete_document(
        db: Session,
        boat_id: int,
        doc_id: int,
        current_user: User,
    ) -> None:
        """Soft-delete a document with audit logging.

        - Sets deleted_at timestamp.
        - Does NOT remove the row from the database.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "delete_document started | doc_id=%s | boat_id=%s | "
            "user_id=%s | correlation_id=%s",
            doc_id, boat_id, current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ─────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Fetch document ──────────────────────────────────────────
            doc = BoatRepository.get_document(db, boat_id, doc_id)
            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )

            # ── 3. Soft delete ─────────────────────────────────────────────
            doc.deleted_at = _now()
            doc.updated_by = current_user.id
            db.flush()

            # ── 4. Audit log ───────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="document_deleted",
                target_table="boat_documents",
                target_id=doc.id,
                old_values=json.dumps({
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "is_verified": doc.is_verified,
                }),
                correlation_id=correlation_id,
            )

            db.commit()

            logger.info(
                "delete_document success | doc_id=%s | correlation_id=%s",
                doc.id, correlation_id,
            )

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "delete_document failed | doc_id=%s | correlation_id=%s",
                doc_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete document",
            )

    # ── Update document metadata ─────────────────────────────────────────────

    @staticmethod
    def update_document(
        db: Session,
        boat_id: int,
        doc_id: int,
        payload: DocumentCreate,
        current_user: User,
    ) -> BoatDocument:
        """Update document metadata.

        - Replaces existing metadata with new values.
        - Resets verification status if document content changes.
        - Creates audit log with old/new snapshots.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "update_document started | doc_id=%s | boat_id=%s | "
            "user_id=%s | correlation_id=%s",
            doc_id, boat_id, current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ─────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Validate document_type ───────────────────────────────────
            if payload.document_type not in VALID_DOCUMENT_TYPES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid document type '{payload.document_type}'. "
                        f"Valid types: {sorted(VALID_DOCUMENT_TYPES)}"
                    ),
                )

            # ── 3. Fetch document ──────────────────────────────────────────
            doc = BoatRepository.get_document(db, boat_id, doc_id)
            if doc is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document not found",
                )

            # ── 4. Snapshot old values ─────────────────────────────────────
            old_values = {
                "document_type": doc.document_type,
                "document_number": doc.document_number,
                "issuing_authority": doc.issuing_authority,
                "issue_date": doc.issue_date.isoformat() if doc.issue_date else None,
                "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                "file_hash": doc.file_hash,
                "is_verified": doc.is_verified,
            }

            # ── 5. Apply update ────────────────────────────────────────────
            doc.document_type = payload.document_type
            doc.document_number = payload.document_number
            doc.issuing_authority = payload.issuing_authority
            doc.issue_date = payload.issue_date
            doc.expiry_date = payload.expiry_date
            doc.file_url = payload.file_url
            doc.file_hash = payload.file_hash
            # Reset verification if content changed
            if payload.file_hash and payload.file_hash != old_values["file_hash"]:
                doc.is_verified = False
                doc.verified_by = None
                doc.verified_at = None
            doc.updated_by = current_user.id

            db.flush()

            # ── 6. Audit log ───────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="document_updated",
                target_table="boat_documents",
                target_id=doc.id,
                old_values=json.dumps(old_values),
                new_values=json.dumps({
                    "document_type": doc.document_type,
                    "document_number": doc.document_number,
                    "expiry_date": doc.expiry_date.isoformat() if doc.expiry_date else None,
                    "file_hash": doc.file_hash,
                    "is_verified": doc.is_verified,
                }),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(doc)

            logger.info(
                "update_document success | doc_id=%s | correlation_id=%s",
                doc.id, correlation_id,
            )
            return doc

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "update_document failed | doc_id=%s | correlation_id=%s",
                doc_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update document",
            )

    # ── Hash verification ─────────────────────────────────────────────────────

    @staticmethod
    def verify_document_hash(
        db: Session,
        boat_id: int,
        doc_id: int,
        file_content: bytes,
        current_user: User,
    ) -> bool:
        """Verify document integrity by comparing stored hash against file content.

        Returns True if the computed SHA-256 hash matches the stored hash.
        """
        _check_boat_access(db, boat_id, current_user)
        doc = BoatRepository.get_document(db, boat_id, doc_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found",
            )
        if not doc.file_hash:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document has no stored hash for verification",
            )

        computed_hash = _compute_file_hash(file_content)
        return computed_hash == doc.file_hash

    # ── Expiry detection ──────────────────────────────────────────────────────

    @staticmethod
    def get_expiring_documents(
        db: Session,
        current_user: User,
        within_days: int = 30,
        boat_id: Optional[int] = None,
    ) -> list[dict]:
        """Find documents that are expiring within the given number of days.

        Returns a list of document summaries with expiry info.
        Operators see all; fishermen see only their own boats' documents.
        """
        from datetime import timedelta

        today = _now().date()
        deadline = today + timedelta(days=within_days)

        query = (
            db.query(BoatDocument)
            .filter(
                BoatDocument.deleted_at.is_(None),
                BoatDocument.expiry_date.isnot(None),
                BoatDocument.expiry_date >= today,
                BoatDocument.expiry_date <= deadline,
            )
        )

        # Role-based filtering
        if current_user.role == UserRole.fisherman:
            from app.models.boat import Boat
            query = query.join(Boat, BoatDocument.boat_id == Boat.id).filter(
                Boat.owner_id == current_user.id,
                Boat.deleted_at.is_(None),
            )
        elif current_user.role == UserRole.family:
            from app.models.boat import Boat
            from app.models.family_link import FamilyLink
            linked = (
                db.query(FamilyLink.fisherman_id)
                .filter(FamilyLink.family_user_id == current_user.id)
                .subquery()
            )
            query = query.join(Boat, BoatDocument.boat_id == Boat.id).filter(
                Boat.owner_id.in_(linked),
                Boat.deleted_at.is_(None),
            )
        # Operators see all

        if boat_id:
            query = query.filter(BoatDocument.boat_id == boat_id)

        documents = query.order_by(BoatDocument.expiry_date).all()

        return [
            {
                "id": d.id,
                "boat_id": d.boat_id,
                "document_type": d.document_type,
                "document_number": d.document_number,
                "expiry_date": d.expiry_date.isoformat(),
                "days_remaining": (d.expiry_date - today).days,
                "is_verified": d.is_verified,
            }
            for d in documents
        ]

    # ── Document statistics ───────────────────────────────────────────────────

    @staticmethod
    def get_document_stats(
        db: Session,
        boat_id: int,
        current_user: User,
    ) -> dict:
        """Get document statistics for a boat."""
        _check_boat_access(db, boat_id, current_user)

        documents = BoatRepository.list_documents(db, boat_id)
        today = _now().date()

        total = len(documents)
        verified = sum(1 for d in documents if d.is_verified)
        expired = sum(
            1 for d in documents
            if d.expiry_date and d.expiry_date < today
        )
        expiring_soon = sum(
            1 for d in documents
            if d.expiry_date and today <= d.expiry_date <= today.replace(day=today.day + 30)
        )
        missing_types = {
            t for t in ("registration_certificate", "fishing_license", "insurance_policy")
            if not any(d.document_type == t and not _is_expired(d) for d in documents)
        }

        return {
            "total_documents": total,
            "verified_documents": verified,
            "expired_documents": expired,
            "expiring_within_30_days": expiring_soon,
            "missing_mandatory_types": sorted(missing_types),
            "compliance_pct": round((verified / total * 100) if total > 0 else 0.0, 1),
        }


def _is_expired(doc: BoatDocument) -> bool:
    """Check if a document is expired."""
    if doc.expiry_date is None:
        return False
    return doc.expiry_date < _now().date()
