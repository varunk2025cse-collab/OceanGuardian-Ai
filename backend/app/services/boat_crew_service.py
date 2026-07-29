"""
Boat Crew Service — manages crew assignments for boats.

Provides:
  - Assign crew members (with role validation)
  - Remove crew members (soft removal with audit)
  - Captain assignment (enforces one-captain rule)
  - Crew role management
  - Crew history tracking
  - Crew validation for readiness
  - Audit logging for all changes

Design principles:
  - All DB access goes through BoatRepository (Repository Pattern).
  - Every write creates an audit-log entry.
  - Every write is wrapped in a transaction — rollback on failure.
  - Enforces one-captain rule per boat (soft-remove previous captain).
  - Consistent with BoatService pattern (static methods, structured logging).
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.boat import BoatCrewMember, BoatAuditLog
from app.models.user import User, UserRole
from app.repositories.boat_repository import BoatRepository
from app.schemas.boat import CrewMemberCreate, CrewMemberRemove, CrewMemberOut

logger = logging.getLogger("app.services.boat_crew_service")


# ── Constants ─────────────────────────────────────────────────────────────────
VALID_CREW_ROLES = frozenset({
    "captain", "navigator", "engineer", "deckhand",
    "lookout", "medic", "owner", "other",
})
MAX_FULL_NAME_LENGTH = 120
MAX_PHONE_LENGTH = 20


# =============================================================================
# Helpers
# =============================================================================

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _generate_correlation_id() -> str:
    return str(uuid.uuid4())


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
# Boat Crew Service
# =============================================================================

class BoatCrewService:
    """Single source of truth for boat crew operations.

    All methods are ``@staticmethod`` consistent with the existing service-layer
    pattern (BoatService, BoatDocumentService, BoatReadinessService).
    """

    # ── Assign crew member ────────────────────────────────────────────────────

    @staticmethod
    def assign_crew(
        db: Session,
        boat_id: int,
        payload: CrewMemberCreate,
        current_user: User,
    ) -> BoatCrewMember:
        """Assign a crew member to a boat.

        - Validates role against known crew roles.
        - Enforces one-captain rule: if assigning a captain and another
          captain already exists, the previous captain is soft-removed.
        - Detects duplicate active crew (same user_id or same phone + name).
        - Creates audit log.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "assign_crew started | boat_id=%s | role=%s | name=%s | "
            "user_id=%s | correlation_id=%s",
            boat_id, payload.role, payload.full_name,
            current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ──────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Validate role ─────────────────────────────────────────────
            if payload.role not in VALID_CREW_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid crew role '{payload.role}'. "
                        f"Valid roles: {sorted(VALID_CREW_ROLES)}"
                    ),
                )

            # ── 3. Duplicate detection ───────────────────────────────────────
            existing_active = BoatRepository.list_active_crew(db, boat_id)

            # Check by user_id (if provided)
            if payload.user_id:
                duplicate = [
                    m for m in existing_active
                    if m.user_id == payload.user_id
                ]
                if duplicate:
                    logger.warning(
                        "assign_crew duplicate user_id | boat_id=%s | "
                        "user_id=%s | existing_id=%s | correlation_id=%s",
                        boat_id, payload.user_id, duplicate[0].id,
                        correlation_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="This crew member is already assigned to the boat",
                    )

            # Check by full_name + phone (for non-user crew)
            if payload.phone_number:
                duplicate = [
                    m for m in existing_active
                    if m.full_name.lower() == payload.full_name.lower()
                    and m.phone_number == payload.phone_number
                ]
                if duplicate:
                    logger.warning(
                        "assign_crew duplicate name+phone | boat_id=%s | "
                        "name=%s | phone=%s | existing_id=%s | "
                        "correlation_id=%s",
                        boat_id, payload.full_name, payload.phone_number,
                        duplicate[0].id, correlation_id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "A crew member with this name and phone number "
                            "is already assigned to the boat"
                        ),
                    )

            # ── 4. One-captain rule ──────────────────────────────────────────
            if payload.role == "captain":
                existing_captains = [
                    m for m in existing_active if m.role == "captain"
                ]
                for captain in existing_captains:
                    logger.info(
                        "assign_crew demoting previous captain | "
                        "captain_id=%s | boat_id=%s | correlation_id=%s",
                        captain.id, boat_id, correlation_id,
                    )
                    captain.is_active = False
                    captain.removed_at = _now()
                    captain.removal_reason = "Replaced by new captain assignment"
                    db.flush()

            # ── 5. Build crew member ─────────────────────────────────────────
            member = BoatCrewMember(
                boat_id=boat_id,
                user_id=payload.user_id,
                full_name=payload.full_name,
                phone_number=payload.phone_number,
                aadhaar_last4=payload.aadhaar_last4,
                role=payload.role,
                is_primary_contact=payload.is_primary_contact,
                is_active=True,
                created_by=current_user.id,
            )
            db.add(member)
            db.flush()

            # ── 6. Audit log ─────────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="crew_assigned",
                target_table="boat_crew_members",
                target_id=member.id,
                new_values=json.dumps({
                    "id": member.id,
                    "full_name": member.full_name,
                    "role": member.role,
                    "user_id": member.user_id,
                    "is_primary_contact": member.is_primary_contact,
                }),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(member)

            logger.info(
                "assign_crew success | crew_id=%s | boat_id=%s | "
                "correlation_id=%s",
                member.id, boat_id, correlation_id,
            )
            return member

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "assign_crew failed | boat_id=%s | correlation_id=%s",
                boat_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to assign crew member",
            )

    # ── Remove crew member ────────────────────────────────────────────────────

    @staticmethod
    def remove_crew(
        db: Session,
        boat_id: int,
        crew_id: int,
        payload: CrewMemberRemove,
        current_user: User,
    ) -> None:
        """Soft-remove a crew member from a boat.

        - Sets is_active=False, removed_at, and removal_reason.
        - Does NOT delete the row (historical record preserved).
        - Creates audit log.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "remove_crew started | crew_id=%s | boat_id=%s | "
            "user_id=%s | correlation_id=%s",
            crew_id, boat_id, current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ──────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Fetch crew member ─────────────────────────────────────────
            member = BoatRepository.get_crew_member(db, boat_id, crew_id)
            if member is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Crew member not found or already removed",
                )

            # ── 3. Prevent removing the last captain ─────────────────────────
            if member.role == "captain":
                active_crew = BoatRepository.list_active_crew(db, boat_id)
                captain_count = sum(1 for m in active_crew if m.role == "captain")
                if captain_count <= 1:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            "Cannot remove the last captain. "
                            "Assign a new captain before removing this one."
                        ),
                    )

            # ── 4. Soft remove ───────────────────────────────────────────────
            old_role = member.role
            member.is_active = False
            member.removed_at = _now()
            member.removal_reason = payload.reason or "Removed by operator"
            db.flush()

            # ── 5. Audit log ─────────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="crew_removed",
                target_table="boat_crew_members",
                target_id=crew_id,
                old_values=json.dumps({
                    "full_name": member.full_name,
                    "role": old_role,
                    "user_id": member.user_id,
                    "is_active": True,
                }),
                new_values=json.dumps({
                    "is_active": False,
                    "removed_at": member.removed_at.isoformat(),
                    "removal_reason": member.removal_reason,
                }),
                correlation_id=correlation_id,
            )

            db.commit()

            logger.info(
                "remove_crew success | crew_id=%s | correlation_id=%s",
                crew_id, correlation_id,
            )

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "remove_crew failed | crew_id=%s | correlation_id=%s",
                crew_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to remove crew member",
            )

    # ── List crew ─────────────────────────────────────────────────────────────

    @staticmethod
    def list_crew(
        db: Session,
        boat_id: int,
        current_user: User,
        include_inactive: bool = False,
    ) -> list[BoatCrewMember]:
        """List crew members for a boat.

        By default, only active crew are returned.
        """
        _check_boat_access(db, boat_id, current_user)

        if include_inactive:
            return (
                db.query(BoatCrewMember)
                .filter(BoatCrewMember.boat_id == boat_id)
                .order_by(BoatCrewMember.assigned_at.desc())
                .all()
            )
        return BoatRepository.list_active_crew(db, boat_id)

    # ── Get single crew member ────────────────────────────────────────────────

    @staticmethod
    def get_crew_member(
        db: Session,
        boat_id: int,
        crew_id: int,
        current_user: User,
    ) -> BoatCrewMember:
        """Get a single crew member with access control."""
        _check_boat_access(db, boat_id, current_user)

        member = (
            db.query(BoatCrewMember)
            .filter(
                BoatCrewMember.id == crew_id,
                BoatCrewMember.boat_id == boat_id,
            )
            .first()
        )
        if member is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Crew member not found",
            )
        return member

    # ── Update crew role ──────────────────────────────────────────────────────

    @staticmethod
    def update_crew_role(
        db: Session,
        boat_id: int,
        crew_id: int,
        new_role: str,
        current_user: User,
    ) -> BoatCrewMember:
        """Update a crew member's role.

        - One-captain rule: if new role is 'captain', existing captain is
          soft-removed.
        - Creates audit log.
        """
        correlation_id = _generate_correlation_id()
        logger.info(
            "update_crew_role started | crew_id=%s | boat_id=%s | "
            "new_role=%s | user_id=%s | correlation_id=%s",
            crew_id, boat_id, new_role, current_user.id, correlation_id,
        )

        try:
            # ── 1. BOAL ──────────────────────────────────────────────────────
            _check_boat_access(db, boat_id, current_user)

            # ── 2. Validate role ─────────────────────────────────────────────
            if new_role not in VALID_CREW_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=(
                        f"Invalid crew role '{new_role}'. "
                        f"Valid roles: {sorted(VALID_CREW_ROLES)}"
                    ),
                )

            # ── 3. Fetch crew member ─────────────────────────────────────────
            member = BoatRepository.get_crew_member(db, boat_id, crew_id)
            if member is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Crew member not found or not active",
                )

            old_role = member.role

            # ── 4. One-captain rule ──────────────────────────────────────────
            if new_role == "captain" and old_role != "captain":
                active_crew = BoatRepository.list_active_crew(db, boat_id)
                existing_captains = [
                    m for m in active_crew if m.role == "captain"
                ]
                for captain in existing_captains:
                    captain.is_active = False
                    captain.removed_at = _now()
                    captain.removal_reason = (
                        f"Replaced by {member.full_name} on role change to captain"
                    )
                    db.flush()

            # ── 5. Apply update ─────────────────────────────────────────────
            member.role = new_role
            db.flush()

            # ── 6. Audit log ─────────────────────────────────────────────────
            BoatRepository.append_audit_log(
                db,
                boat_id=boat_id,
                actor_id=current_user.id,
                action="crew_role_changed",
                target_table="boat_crew_members",
                target_id=crew_id,
                old_values=json.dumps({"role": old_role}),
                new_values=json.dumps({"role": new_role}),
                correlation_id=correlation_id,
            )

            db.commit()
            db.refresh(member)

            logger.info(
                "update_crew_role success | crew_id=%s | role=%s→%s | "
                "correlation_id=%s",
                member.id, old_role, new_role, correlation_id,
            )
            return member

        except HTTPException:
            db.rollback()
            raise
        except Exception:
            db.rollback()
            logger.exception(
                "update_crew_role failed | crew_id=%s | correlation_id=%s",
                crew_id, correlation_id,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update crew role",
            )

    # ── Crew statistics ───────────────────────────────────────────────────────

    @staticmethod
    def get_crew_stats(
        db: Session,
        boat_id: int,
        current_user: User,
    ) -> dict:
        """Get crew statistics for a boat."""
        _check_boat_access(db, boat_id, current_user)

        active_crew = BoatRepository.list_active_crew(db, boat_id)
        total_active = len(active_crew)
        role_counts: dict[str, int] = {}
        for m in active_crew:
            role_counts[m.role] = role_counts.get(m.role, 0) + 1

        has_captain = role_counts.get("captain", 0) > 0
        crew_history_count = (
            db.query(BoatCrewMember)
            .filter(BoatCrewMember.boat_id == boat_id)
            .count()
        )

        return {
            "total_active_crew": total_active,
            "roles": role_counts,
            "has_captain": has_captain,
            "total_crew_ever_assigned": crew_history_count,
            "missing_roles": sorted(
                r for r in ("captain", "navigator", "engineer", "deckhand")
                if r not in role_counts
            ),
        }

    # ── Crew history ──────────────────────────────────────────────────────────

    @staticmethod
    def get_crew_history(
        db: Session,
        boat_id: int,
        current_user: User,
    ) -> list[BoatCrewMember]:
        """Get all crew assignments (including removed) for a boat's history."""
        _check_boat_access(db, boat_id, current_user)

        return (
            db.query(BoatCrewMember)
            .filter(BoatCrewMember.boat_id == boat_id)
            .order_by(BoatCrewMember.assigned_at.desc())
            .all()
        )
