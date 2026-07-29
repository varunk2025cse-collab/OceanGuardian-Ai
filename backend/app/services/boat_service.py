"""
Enterprise Boat Service — single source of truth for every Boat operation.

Implements the full boat lifecycle:
  - register_boat     — duplicate detection, QR generation, audit, transactions
  - update_boat       — optimistic locking, partial update, audit
  - change_status     — 8-state FSM with legal-transition enforcement
  - decommission_boat — soft delete, active-trip guard
  - verify_boat       — operator-only verification workflow
  - get_boat_for_user — role-aware RBAC query

Design principles:
  - All DB access goes through BoatRepository (Repository Pattern).
  - Every write creates an audit-log entry and (where applicable) a
    status-history entry.
  - Every write is wrapped in a transaction — rollback on failure.
  - No business logic in the model layer; no SQL in the service layer.
  - Optimistic locking via the `version` column (migration 009).
  - Structured logging via app.logging_config.logger.

References:
  - Migration 009: backend/alembic/versions/009_boat_management_enterprise.py
  - FSM pattern: app/services/trip_service.py, app/services/incident_service.py
  - RBAC: app/core/deps.py
"""
from __future__ import annotations

import json
import logging
import secrets
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.boat import (
    Boat,
    BoatAuditLog,
    BoatStatus,
    BoatStatusHistory,
    BoatVerificationStatus,
)
from app.models.user import User, UserRole
from app.schemas.boat import BoatV2Create, BoatV2Update
from app.repositories.boat_repository import BoatRepository

logger = logging.getLogger("app.services.boat_service")

# ── Constants (no magic numbers) ──────────────────────────────────────────────
_QR_TOKEN_BYTES = 32          # 256 bits of entropy → ~43-char urlsafe token
_MAX_QR_RETRIES = 5           # retry on the astronomically unlikely collision
_DEFAULT_PAGE_SIZE = 20
_MAX_PAGE_SIZE = 100


# =============================================================================
# Finite State Machine — legal boat-status transitions
# =============================================================================
# Mirrors the TripService / IncidentService pattern.  The FSM is enforced
# here (not in the DB) so it can be unit-tested independently.
#
# Marine-safety rationale:
#   registered → active           boat passes initial registration
#   active → inactive             owner takes boat out of service temporarily
#   active → maintenance          scheduled or unscheduled repair
#   active → emergency            SOS or critical fault
#   active → damaged              collision / grounding / equipment failure
#   active → lost                 declared lost at sea
#   active → decommissioned       permanently retired
#   emergency → active            incident resolved, boat safe
#   emergency → maintenance       needs repair after emergency
#   emergency → damaged           confirmed damage from emergency
#   emergency → lost              declared lost during emergency
#   damaged → maintenance         repairs underway
#   damaged → decommissioned      beyond economical repair
#   lost → decommissioned         formal retirement after loss
#   decommissioned → (terminal)   no further transitions


LEGAL_TRANSITIONS: dict[str, set[str]] = {
    BoatStatus.REGISTERED.value: {
        BoatStatus.ACTIVE.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.ACTIVE.value: {
        BoatStatus.INACTIVE.value,
        BoatStatus.MAINTENANCE.value,
        BoatStatus.EMERGENCY.value,
        BoatStatus.DAMAGED.value,
        BoatStatus.LOST.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.INACTIVE.value: {
        BoatStatus.ACTIVE.value,
        BoatStatus.MAINTENANCE.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.MAINTENANCE.value: {
        BoatStatus.ACTIVE.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.EMERGENCY.value: {
        BoatStatus.ACTIVE.value,
        BoatStatus.MAINTENANCE.value,
        BoatStatus.DAMAGED.value,
        BoatStatus.LOST.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.DAMAGED.value: {
        BoatStatus.MAINTENANCE.value,
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.LOST.value: {
        BoatStatus.DECOMMISSIONED.value,
    },
    BoatStatus.DECOMMISSIONED.value: set(),  # terminal
}


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    """UTC-aware timestamp helper — single source for all service timestamps."""
    return datetime.now(timezone.utc)


def _boat_to_audit_dict(boat: Boat) -> dict:
    """Serialise the salient fields of a Boat for audit-log JSON snapshots.

    Only scalar, business-relevant fields are included — never relationships
    (which would cause lazy-load queries or circular serialisation).
    """
    return {
        "id": boat.id,
        "name": boat.name,
        "registration_number": boat.registration_number,
        "status": boat.status,
        "verification_status": boat.verification_status,
        "is_active": boat.is_active,
        "deleted_at": boat.deleted_at.isoformat() if boat.deleted_at else None,
        "version": boat.version,
        "owner_id": boat.owner_id,
        "home_harbor_id": boat.home_harbor_id,
        "vessel_class": boat.vessel_class,
        "hull_material": boat.hull_material,
        "year_built": boat.year_built,
        "engine_make": boat.engine_make,
        "engine_model": boat.engine_model,
        "engine_serial_number": boat.engine_serial_number,
        "engine_year": boat.engine_year,
        "qr_code_token": boat.qr_code_token,
        "verified_by": boat.verified_by,
        "verified_at": boat.verified_at.isoformat() if boat.verified_at else None,
    }


def _generate_qr_token(db: Session) -> str:
    """Generate a cryptographically-secure, unique QR token.

    Uses ``secrets.token_urlsafe`` (CSPRNG) and retries on the
    astronomically unlikely event of a collision with an existing token.
    """
    for _ in range(_MAX_QR_RETRIES):
        token = secrets.token_urlsafe(_QR_TOKEN_BYTES)
        if BoatRepository.get_by_qr_token(db, token) is None:
            return token
    # Should never happen (256-bit entropy), but fail loudly rather than
    # silently returning a non-unique token.
    raise RuntimeError("Failed to generate a unique QR token after retries")


def _check_boat_access(db: Session, boat_id: int, user: User, include_deleted: bool = False) -> Boat:
    """Fetch a boat and enforce object-level authorization (BOAL).

    - Operators see every boat (rescue-coordinator / coast-guard view).
    - Fishermen see only their own boats.
    - Family members see boats of fishermen they are linked to.

    Raises 404 if the boat doesn't exist, is soft-deleted, or the caller
    is not authorised — the same 404 is used for all three cases to avoid
    leaking information about which boats exist (data-leakage defence).
    """
    if include_deleted:
        boat = db.query(Boat).filter(Boat.id == boat_id).first()
    else:
        boat = BoatRepository.get_by_id(db, boat_id)
    if boat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Boat not found",
        )

    if user.role == UserRole.operator:
        return boat

    if user.role == UserRole.fisherman:
        if boat.owner_id != user.id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Boat not found",
            )
        return boat

    # Family role — check FamilyLink
    if user.role == UserRole.family:
        from app.models.family_link import FamilyLink
        linked = (
            db.query(FamilyLink)
            .filter(
                FamilyLink.family_user_id == user.id,
                FamilyLink.fisherman_id == boat.owner_id,
            )
            .first()
        )
        if linked is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Boat not found",
            )
        return boat

    # Should never reach here given the UserRole enum, but defend in depth.
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Not authorised to view this boat",
    )


# =============================================================================
# BoatService
# =============================================================================

class BoatService:
    """Single source of truth for every Boat operation.

    All methods are ``@staticmethod`` so they can be called without
    instantiation, consistent with the existing service-layer pattern
    (TripService, IncidentService, BoatHealthService).
    """

    # ── Registration ──────────────────────────────────────────────────────────

    @staticmethod
    def register_boat(
        db: Session,
        payload: BoatV2Create,
        current_user: User,
    ) -> Boat:
        """Register a new boat.

        - Duplicate detection: case-insensitive registration-number check
          plus name+owner uniqueness.
        - QR generation: cryptographically-secure unique token.
        - Audit logging: creates a ``created`` audit-log entry.
        - Transactions: the entire operation is atomic — rollback on failure.
        - Validation: field-level validation is handled by BoatV2Create;
          this method adds business-rule validation (harbor existence).
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "register_boat started | user_id=%s | name=%s | correlation_id=%s",
            current_user.id, payload.name, correlation_id,
        )

        try:
            # ── 1. Duplicate detection (case-insensitive) ─────────────────────
            if payload.registration_number:
                existing = BoatRepository.get_by_registration(
                    db, payload.registration_number
                )
                if existing is not None:
                    logger.warning(
                        "register_boat duplicate registration | reg=%s | "
                        "existing_boat_id=%s | user_id=%s | correlation_id=%s",
                        payload.registration_number, existing.id,
                        current_user.id, correlation_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Registration number '{payload.registration_number}' "
                            "is already in use by another boat"
                        ),
                    )

            # Name + owner uniqueness (a fisherman shouldn't register the
            # same boat twice, even with a different registration number)
            duplicate_name = (
                db.query(Boat)
                .filter(
                    Boat.owner_id == current_user.id,
                    Boat.name == payload.name,
                    Boat.deleted_at.is_(None),
                )
                .first()
            )
            if duplicate_name is not None:
                logger.warning(
                    "register_boat duplicate name | name=%s | owner_id=%s | "
                    "existing_boat_id=%s | correlation_id=%s",
                    payload.name, current_user.id,
                    duplicate_name.id, correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"You already have a boat named '{payload.name}'. "
                        "Choose a different name or update the existing boat."
                    ),
                )

            # ── 2. Validate home harbor exists (if provided) ─────────────────
            if payload.home_harbor_id is not None:
                from app.models.phase5 import Harbor
                harbor = db.query(Harbor).filter(Harbor.id == payload.home_harbor_id).first()
                if harbor is None:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Home harbor {payload.home_harbor_id} does not exist",
                    )

            # ── 3. Build the boat ────────────────────────────────────────────
            boat_data = payload.model_dump(exclude_unset=True)
            # Strip fields that are not direct columns or are handled separately
            boat_data.pop("safety_equipment", None)  # not in BoatV2Create, but be safe

            boat = Boat(
                owner_id=current_user.id,
                status=BoatStatus.REGISTERED.value,  # lifecycle start state
                verification_status=BoatVerificationStatus.UNVERIFIED.value,
                qr_code_token=_generate_qr_token(db),
                created_by=current_user.id,
                updated_by=current_user.id,
                **boat_data,
            )
            db.add(boat)
            db.flush()  # assign ID without committing

            # ── 4. Audit log ─────────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat.id,
                actor_id=current_user.id,
                action="created",
                target_table="boats",
                target_id=boat.id,
                new_values=json.dumps(_boat_to_audit_dict(boat)),
                correlation_id=correlation_id,
            )

            # ── 5. Status history (initial state) ─────────────────────────────
            BoatRepository.append_status_history(
                db,
                boat_id=boat.id,
                previous_status=None,
                new_status=BoatStatus.REGISTERED.value,
                actor_id=current_user.id,
                reason="Boat registered via BoatService",
                source="manual",
            )

            db.commit()
            db.refresh(boat)

            logger.info(
                "register_boat success | boat_id=%s | name=%s | qr_token=%s | "
                "correlation_id=%s",
                boat.id, boat.name, boat.qr_code_token, correlation_id,
            )
            return boat

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "register_boat failed | user_id=%s | name=%s | correlation_id=%s",
                current_user.id, payload.name, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to register boat",
            )

    # ── Update (partial, optimistic locking) ────────────────────────────────

    @staticmethod
    def update_boat(
        db: Session,
        boat_id: int,
        payload: BoatV2Update,
        current_user: User,
    ) -> Boat:
        """Partially update a boat with optimistic locking.

        - Version conflict detection: if the client echoes a ``version``
          that doesn't match the current DB row, a 409 is raised.
        - Partial update: only fields present in ``exclude_unset`` are applied.
        - Audit logging: old_values and new_values JSON snapshots are recorded.
        - Optimistic locking: ``version`` is incremented after every update.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "update_boat started | boat_id=%s | user_id=%s | correlation_id=%s",
            boat_id, current_user.id, correlation_id,
        )

        try:
            # ── 1. Fetch + authorize ────────────────────────────────────────
            boat = _check_boat_access(db, boat_id, current_user)

            # ── 2. Version conflict detection ───────────────────────────────
            if payload.version is not None and payload.version != boat.version:
                logger.warning(
                    "update_boat version conflict | boat_id=%s | "
                    "client_version=%s | db_version=%s | user_id=%s | correlation_id=%s",
                    boat_id, payload.version, boat.version,
                    current_user.id, correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Version conflict: boat was modified by another user. "
                        f"Current version is {boat.version}, you sent {payload.version}. "
                        "Please refresh and retry."
                    ),
                )

            # ── 3. Snapshot old values ──────────────────────────────────────
            old_values = _boat_to_audit_dict(boat)

            # ── 4. Apply partial update ─────────────────────────────────────
            update_data = payload.model_dump(exclude_unset=True)
            # Never allow the client to change these fields directly
            update_data.pop("version", None)
            update_data.pop("id", None)
            update_data.pop("owner_id", None)
            update_data.pop("created_by", None)
            update_data.pop("qr_code_token", None)
            update_data.pop("deleted_at", None)
            update_data.pop("created_at", None)

            for key, val in update_data.items():
                setattr(boat, key, val)

            # Optimistic lock: bump version
            boat.version = boat.version + 1
            boat.updated_by = current_user.id

            db.flush()

            # ── 5. Audit log ────────────────────────────────────────────────
            new_values = _boat_to_audit_dict(boat)
            BoatRepository.append_audit_log(
                db,
                boat_id=boat.id,
                actor_id=current_user.id,
                action="updated",
                target_table="boats",
                target_id=boat.id,
                old_values=json.dumps(old_values),
                new_values=json.dumps(new_values),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(boat)

            logger.info(
                "update_boat success | boat_id=%s | version=%s | correlation_id=%s",
                boat.id, boat.version, correlation_id,
            )
            return boat

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "update_boat failed | boat_id=%s | user_id=%s | correlation_id=%s",
                boat_id, current_user.id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update boat",
            )

    # ── Status change (FSM) ───────────────────────────────────────────────────

    @staticmethod
    def change_status(
        db: Session,
        boat_id: int,
        new_status: str,
        actor: User,
        reason: Optional[str] = None,
    ) -> Boat:
        """Transition a boat to a new status via the FSM.

        - Legal-transition enforcement: only transitions in
          ``LEGAL_TRANSITIONS`` are allowed; everything else raises 409.
        - Status history: an append-only row is created for every transition.
        - Audit log: an ``status_changed`` entry records old/new values.
        - Timestamp, actor, and reason are all captured.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "change_status started | boat_id=%s | new_status=%s | actor_id=%s | "
            "correlation_id=%s",
            boat_id, new_status, actor.id, correlation_id,
        )

        try:
            # ── 1. Fetch + authorize ────────────────────────────────────────
            boat = _check_boat_access(db, boat_id, actor, include_deleted=True)

            # ── 2. Validate new_status is a known BoatStatus ─────────────────
            if new_status not in BoatStatus.all():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Unknown boat status '{new_status}'. "
                        f"Valid values: {sorted(BoatStatus.all())}"
                    ),
                )

            # ── 3. Enforce legal transition ─────────────────────────────────
            current_status = boat.status
            if current_status in BoatStatus.terminal():
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Boat is in terminal status '{current_status}' "
                        "and cannot be transitioned further"
                    ),
                )

            legal_targets = LEGAL_TRANSITIONS.get(current_status, set())
            if new_status not in legal_targets:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Illegal transition: cannot move boat from "
                        f"'{current_status}' to '{new_status}'. "
                        f"Legal targets: {sorted(legal_targets) if legal_targets else 'none (terminal)'}"
                    ),
                )

            # ── 4. Apply transition ─────────────────────────────────────────
            previous_status = boat.status
            boat.status = new_status

            # If transitioning to decommissioned, also soft-delete
            if new_status == BoatStatus.DECOMMISSIONED.value:
                boat.deleted_at = _now()
                boat.is_active = False

            db.flush()

            # ── 5. Status history (append-only) ─────────────────────────────
            BoatRepository.append_status_history(
                db,
                boat_id=boat.id,
                previous_status=previous_status,
                new_status=new_status,
                actor_id=actor.id,
                reason=reason,
                source="manual",
            )

            # ── 6. Audit log ────────────────────────────────────────────────
            old_values = json.dumps({"status": previous_status})
            new_values = json.dumps({"status": new_status})
            BoatRepository.append_audit_log(
                db,
                boat_id=boat.id,
                actor_id=actor.id,
                action="status_changed",
                target_table="boats",
                target_id=boat.id,
                old_values=old_values,
                new_values=new_values,
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(boat)

            logger.info(
                "change_status success | boat_id=%s | %s→%s | actor_id=%s | "
                "correlation_id=%s",
                boat.id, previous_status, new_status, actor.id, correlation_id,
            )
            return boat

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "change_status failed | boat_id=%s | actor_id=%s | correlation_id=%s",
                boat_id, actor.id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to change boat status",
            )

    # ── Decommission (soft delete) ────────────────────────────────────────────

    @staticmethod
    def decommission_boat(
        db: Session,
        boat_id: int,
        current_user: User,
        reason: Optional[str] = None,
    ) -> Boat:
        """Soft-delete a boat via the decommission lifecycle state.

        - Soft delete: sets ``deleted_at`` and ``is_active=False``.
        - Active-trip guard: rejects if the boat has an active trip.
        - Uses change_status() internally so the FSM, status history, and
          audit log are all handled consistently.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "decommission_boat started | boat_id=%s | user_id=%s | correlation_id=%s",
            boat_id, current_user.id, correlation_id,
        )

        try:
            # ── 1. Fetch + authorize ────────────────────────────────────────
            boat = _check_boat_access(db, boat_id, current_user)

            # ── 2. Active-trip guard ────────────────────────────────────────
            if BoatRepository.has_active_trip(db, boat_id):
                logger.warning(
                    "decommission_boat rejected — active trip | boat_id=%s | "
                    "user_id=%s | correlation_id=%s",
                    boat_id, current_user.id, correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "Cannot decommission boat: it currently has an active trip. "
                        "End the trip first."
                    ),
                )

            # ── 3. Delegate to change_status (FSM + history + audit) ────────
            decommission_reason = reason or "Boat decommissioned"
            boat = BoatService.change_status(
                db=db,
                boat_id=boat_id,
                new_status=BoatStatus.DECOMMISSIONED.value,
                actor=current_user,
                reason=decommission_reason,
            )

            logger.info(
                "decommission_boat success | boat_id=%s | correlation_id=%s",
                boat.id, correlation_id,
            )
            return boat

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "decommission_boat failed | boat_id=%s | user_id=%s | correlation_id=%s",
                boat_id, current_user.id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to decommission boat",
            )

    # ── Verification (operator-only) ──────────────────────────────────────────

    @staticmethod
    def verify_boat(
        db: Session,
        boat_id: int,
        verification_status: str,
        actor: User,
        notes: Optional[str] = None,
    ) -> Boat:
        """Verify or reject a boat's documents (operator/admin only).

        - RBAC: only ``UserRole.operator`` accounts may call this.
        - Stores: ``verified_by``, ``verified_at``, ``verification_status``.
        - Audit logging: records the verification action.
        """
        correlation_id = str(uuid.uuid4())
        logger.info(
            "verify_boat started | boat_id=%s | status=%s | actor_id=%s | correlation_id=%s",
            boat_id, verification_status, actor.id, correlation_id,
        )

        try:
            # ── 1. RBAC ─────────────────────────────────────────────────────
            if actor.role != UserRole.operator:
                logger.warning(
                    "verify_boat RBAC denied | boat_id=%s | actor_id=%s | "
                    "actor_role=%s | correlation_id=%s",
                    boat_id, actor.id, actor.role.value, correlation_id,
                )
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only operators can verify boats",
                )

            # ── 2. Validate verification_status ─────────────────────────────
            if verification_status not in BoatVerificationStatus.all():
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Unknown verification status '{verification_status}'. "
                        f"Valid values: {sorted(BoatVerificationStatus.all())}"
                    ),
                )

            # ── 3. Fetch boat (operators can see any boat) ──────────────────
            boat = BoatRepository.get_by_id(db, boat_id)
            if boat is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Boat not found",
                )

            # ── 4. Snapshot old values ──────────────────────────────────────
            old_verification = boat.verification_status

            # ── 5. Apply verification ───────────────────────────────────────
            boat.verification_status = verification_status
            boat.verified_by = actor.id
            boat.verified_at = _now()

            db.flush()

            # ── 6. Audit log ────────────────────────────────────────────────
            old_values = json.dumps({"verification_status": old_verification})
            new_values = json.dumps({
                "verification_status": verification_status,
                "verified_by": actor.id,
                "verified_at": boat.verified_at.isoformat(),
            })
            if notes:
                new_values = json.dumps({
                    "verification_status": verification_status,
                    "verified_by": actor.id,
                    "verified_at": boat.verified_at.isoformat(),
                    "notes": notes,
                })

            BoatRepository.append_audit_log(
                db,
                boat_id=boat.id,
                actor_id=actor.id,
                action="verified",
                target_table="boats",
                target_id=boat.id,
                old_values=old_values,
                new_values=new_values,
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(boat)

            logger.info(
                "verify_boat success | boat_id=%s | status=%s | actor_id=%s | "
                "correlation_id=%s",
                boat.id, verification_status, actor.id, correlation_id,
            )
            return boat

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "verify_boat failed | boat_id=%s | actor_id=%s | correlation_id=%s",
                boat_id, actor.id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to verify boat",
            )

    # ── Role-aware retrieval ──────────────────────────────────────────────────

    @staticmethod
    def get_boat_for_user(
        db: Session,
        boat_id: int,
        current_user: User,
    ) -> Boat:
        """Retrieve a boat with role-aware authorization.

        - Operators see any boat.
        - Fishermen see only their own boats.
        - Family members see boats of linked fishermen.
        - Soft-deleted boats return 404 (no data leakage).
        """
        return _check_boat_access(db, boat_id, current_user)

    # ── Listing (role-aware, paginated) ───────────────────────────────────────

    @staticmethod
    def list_boats_for_user(
        db: Session,
        current_user: User,
        status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        page_size: int = _DEFAULT_PAGE_SIZE,
    ) -> tuple[list[Boat], int]:
        """List boats visible to the current user, with pagination.

        - Operators see all boats (optionally filtered by status/search).
        - Fishermen see only their own boats.
        - Family members see boats of linked fishermen.
        """
        page_size = min(max(page_size, 1), _MAX_PAGE_SIZE)

        if current_user.role == UserRole.operator:
            boats, total = BoatRepository.list_all(
                db, status=status, search=search,
                page=page, page_size=page_size,
            )
            return boats, total

        if current_user.role == UserRole.fisherman:
            boats, total = BoatRepository.list_by_owner(
                db, owner_id=current_user.id,
                include_inactive=False,
                page=page, page_size=page_size,
            )
            # Apply status filter client-side (list_by_owner doesn't support it)
            if status:
                boats = [b for b in boats if b.status == status]
                total = len(boats)
            if search:
                pattern = f"%{search}%"
                boats = [
                    b for b in boats
                    if (b.name and search.lower() in b.name.lower())
                    or (b.registration_number and search.lower() in b.registration_number.lower())
                ]
                total = len(boats)
            return boats, total

        # Family — collect boats from linked fishermen
        if current_user.role == UserRole.family:
            from app.models.family_link import FamilyLink
            linked_fishermen = (
                db.query(FamilyLink.fisherman_id)
                .filter(FamilyLink.family_user_id == current_user.id)
                .all()
            )
            fisherman_ids = [f[0] for f in linked_fishermen]
            if not fisherman_ids:
                return [], 0

            boats, total = BoatRepository.list_all(
                db, owner_id=None, status=status, search=search,
                page=page, page_size=page_size,
            )
            # Filter to only boats owned by linked fishermen
            boats = [b for b in boats if b.owner_id in fisherman_ids]
            total = len(boats)
            return boats, total

        # Should never reach here
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorised to list boats",
        )

    # ── Fleet summary (operator dashboard) ────────────────────────────────────

    @staticmethod
    def get_fleet_summary(db: Session) -> dict:
        """Return fleet-wide summary statistics for the operator dashboard.

        Only operators should call this — the router enforces RBAC.
        """
        by_status = BoatRepository.count_by_status(db)
        by_verification = BoatRepository.count_by_verification(db)
        docs_expiring = BoatRepository.count_documents_expiring_within_days(db, 30)
        active_trip_boats = BoatRepository.count_boats_with_active_trips(db)

        # Total non-deleted boats
        total = db.query(Boat).filter(Boat.deleted_at.is_(None)).count()

        return {
            "total_boats": total,
            "by_status": by_status,
            "by_verification": by_verification,
            "documents_expiring_30_days": docs_expiring,
            "boats_with_active_trips": active_trip_boats,
        }
