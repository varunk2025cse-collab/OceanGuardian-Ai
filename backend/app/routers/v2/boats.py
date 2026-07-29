"""
Boat Management V2 API — enterprise boat lifecycle management.

Endpoints:
  POST   /api/v2/boats              — Register a new boat
  GET    /api/v2/boats              — List boats (role-aware, paginated, searchable)
  GET    /api/v2/boats/{id}          — Get boat details
  PATCH  /api/v2/boats/{id}         — Update boat (partial, optimistic locking)
  DELETE /api/v2/boats/{id}         — Decommission (soft delete) a boat
  POST   /api/v2/boats/{id}/status  — Change boat status (FSM)
  POST   /api/v2/boats/{id}/verify  — Verify boat documents (operator)
  GET    /api/v2/boats/{id}/readiness  — Trip readiness evaluation
  GET    /api/v2/boats/{id}/qr      — Get QR code token
  GET    /api/v2/boats/fleet/summary  — Fleet summary (operator)
  POST   /api/v2/boats/{id}/documents     — Add document
  GET    /api/v2/boats/{id}/documents     — List documents
  GET    /api/v2/boats/{id}/documents/{doc_id}  — Get document
  PATCH  /api/v2/boats/{id}/documents/{doc_id}  — Update document
  DELETE /api/v2/boats/{id}/documents/{doc_id}  — Delete document
  POST   /api/v2/boats/{id}/documents/{doc_id}/verify  — Verify document (operator)
  POST   /api/v2/boats/{id}/crew        — Assign crew
  GET    /api/v2/boats/{id}/crew        — List crew
  GET    /api/v2/boats/{id}/crew/{crew_id}  — Get crew member
  DELETE /api/v2/boats/{id}/crew/{crew_id}  — Remove crew
  PATCH  /api/v2/boats/{id}/crew/{crew_id}/role  — Update crew role

Design:
  - RBAC via FastAPI Depends (get_current_user, get_current_operator)
  - JWT authentication (inherit from app.core.deps)
  - Pagination, filtering, sorting via query parameters
  - Consistent response envelope
  - Proper HTTP status codes
  - Meaningful error messages
  - OpenAPI documentation via Pydantic response models
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user, get_current_operator
from app.models.user import User
from app.schemas.boat import (
    BoatV2Create,
    BoatV2Update,
    BoatV2Out,
    BoatStatusUpdate,
    BoatVerifyUpdate,
    BoatDecommission,
    PaginatedBoats,
    FleetSummaryOut,
    DocumentCreate,
    DocumentOut,
    CrewMemberCreate,
    CrewMemberOut,
    CrewMemberRemove,
    StatusHistoryOut,
    AuditLogOut,
)
from app.services.boat_service import BoatService
from app.services.boat_readiness_service import BoatReadinessService
from app.services.boat_document_service import BoatDocumentService
from app.services.boat_crew_service import BoatCrewService
from app.models.boat import BoatStatus, BoatAuditLog, BoatStatusHistory

router = APIRouter(prefix="/api/v2/boats", tags=["boats"])


# =============================================================================
# Helper functions
# =============================================================================

def _boat_to_out(boat) -> BoatV2Out:
    """Convert a Boat ORM instance to a BoatV2Out schema."""
    return BoatV2Out.model_validate(boat)


def _paginate(
    db: Session,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, int]:
    """Validate and return pagination offset/limit."""
    page = max(page, 1)
    page_size = max(min(page_size, 100), 1)
    return page, page_size


# =============================================================================
# Boat CRUD endpoints
# =============================================================================

@router.post(
    "/",
    response_model=BoatV2Out,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new boat",
    description="Register a new fishing boat with full enterprise metadata. "
                "Duplicate detection on registration number and name+owner.",
)
def register_boat(
    payload: BoatV2Create,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Register a new boat (fisherman or operator).

    - Fishermen register boats under their own ownership.
    - Operators can register boats on behalf of fishermen.
    """
    if current_user.role not in ("fisherman", "operator"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only fishermen and operators can register boats",
        )
    boat = BoatService.register_boat(db, payload, current_user)
    return _boat_to_out(boat)


@router.get(
    "/",
    response_model=PaginatedBoats,
    summary="List boats",
    description="List boats visible to the current user with pagination, "
                "filtering by status, and search by name/registration.",
)
def list_boats(
    status: Optional[str] = Query(None, description="Filter by boat status"),
    search: Optional[str] = Query(None, description="Search by name or registration number"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boats, total = BoatService.list_boats_for_user(
        db=db,
        current_user=current_user,
        status=status,
        search=search,
        page=page,
        page_size=page_size,
    )
    return PaginatedBoats(
        data=[_boat_to_out(b) for b in boats],
        meta={
            "page": page,
            "page_size": page_size,
            "total": total,
            "total_pages": (total + page_size - 1) // page_size if total > 0 else 0,
        },
    )


@router.get(
    "/{boat_id}",
    response_model=BoatV2Out,
    summary="Get boat details",
    description="Retrieve a single boat by ID with role-aware access control.",
)
def get_boat(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = BoatService.get_boat_for_user(db, boat_id, current_user)
    return _boat_to_out(boat)


@router.patch(
    "/{boat_id}",
    response_model=BoatV2Out,
    summary="Update boat",
    description="Partially update a boat with optimistic locking. "
                "Echo the current 'version' field to avoid stale overwrites.",
)
def update_boat(
    boat_id: int,
    payload: BoatV2Update,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = BoatService.update_boat(db, boat_id, payload, current_user)
    return _boat_to_out(boat)


@router.delete(
    "/{boat_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Decommission boat",
    description="Soft-delete (decommission) a boat. Requires no active trip.",
)
def delete_boat(
    boat_id: int,
    payload: Optional[BoatDecommission] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    reason = payload.reason if payload else None
    BoatService.decommission_boat(db, boat_id, current_user, reason=reason)
    return None


# =============================================================================
# Boat lifecycle endpoints
# =============================================================================

@router.post(
    "/{boat_id}/status",
    response_model=BoatV2Out,
    summary="Change boat status",
    description="Transition a boat to a new lifecycle status via the FSM. "
                "Only legal transitions are allowed (see LEGAL_TRANSITIONS).",
)
def change_boat_status(
    boat_id: int,
    payload: BoatStatusUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = BoatService.change_status(
        db=db,
        boat_id=boat_id,
        new_status=payload.status,
        actor=current_user,
        reason=payload.reason,
    )
    return _boat_to_out(boat)


@router.post(
    "/{boat_id}/verify",
    response_model=BoatV2Out,
    summary="Verify boat documents",
    description="(Operator only) Set the verification status of a boat's documents.",
)
def verify_boat(
    boat_id: int,
    payload: BoatVerifyUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = BoatService.verify_boat(
        db=db,
        boat_id=boat_id,
        verification_status=payload.verification_status,
        actor=current_user,
        notes=payload.notes,
    )
    return _boat_to_out(boat)


@router.get(
    "/{boat_id}/readiness",
    summary="Get trip readiness evaluation",
    description="Performs a full safety evaluation of a boat for trip readiness. "
                "Returns structured results including safety score, blocking issues, "
                "warnings, and recommendations.",
)
def get_boat_readiness(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a detailed trip readiness evaluation for a boat."""
    evaluation = BoatReadinessService.evaluate_boat_readiness(db, boat_id)
    return evaluation.to_dict()


@router.get(
    "/{boat_id}/qr",
    summary="Get QR code token",
    description="Retrieve the QR code token for a boat.",
)
def get_boat_qr(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = BoatService.get_boat_for_user(db, boat_id, current_user)
    return {
        "boat_id": boat.id,
        "qr_code_token": boat.qr_code_token,
        "qr_url": f"https://oceanguardian.ai/boat/{boat.qr_code_token}",
    }


# =============================================================================
# Fleet endpoint
# =============================================================================

@router.get(
    "/fleet/summary",
    response_model=FleetSummaryOut,
    summary="Get fleet summary",
    description="(Operator only) Get fleet-wide summary statistics for the dashboard.",
)
def get_fleet_summary(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get fleet summary (operator dashboard only)."""
    return BoatService.get_fleet_summary(db)


# =============================================================================
# Boat status history
# =============================================================================

@router.get(
    "/{boat_id}/status-history",
    response_model=list[StatusHistoryOut],
    summary="Get status history",
    description="Get append-only status transition history for a boat.",
)
def get_boat_status_history(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get the status history for a boat."""
    from app.services.boat_service import BoatService
    BoatService.get_boat_for_user(db, boat_id, current_user)
    from app.repositories.boat_repository import BoatRepository
    return BoatRepository.get_status_history(db, boat_id)


# =============================================================================
# Document sub-resource endpoints
# =============================================================================

@router.post(
    "/{boat_id}/documents",
    response_model=DocumentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add boat document",
    description="Upload document metadata for a boat. "
                "Supports duplicate detection on type+number.",
)
def create_document(
    boat_id: int,
    payload: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = BoatDocumentService.create_document(db, boat_id, payload, current_user)
    return DocumentOut.model_validate(doc)


@router.get(
    "/{boat_id}/documents",
    response_model=list[DocumentOut],
    summary="List boat documents",
    description="List documents for a boat with optional type and expiry filtering.",
)
def list_documents(
    boat_id: int,
    document_type: Optional[str] = Query(None, description="Filter by document type"),
    include_expired: bool = Query(True, description="Include expired documents"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    docs = BoatDocumentService.list_documents(
        db, boat_id, current_user,
        document_type=document_type,
        include_expired=include_expired,
    )
    return [DocumentOut.model_validate(d) for d in docs]


@router.get(
    "/{boat_id}/documents/{doc_id}",
    response_model=DocumentOut,
    summary="Get boat document",
    description="Get a single document by ID.",
)
def get_document(
    boat_id: int,
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = BoatDocumentService.get_document(db, boat_id, doc_id, current_user)
    return DocumentOut.model_validate(doc)


@router.patch(
    "/{boat_id}/documents/{doc_id}",
    response_model=DocumentOut,
    summary="Update boat document",
    description="Update document metadata. Resets verification if content hash changes.",
)
def update_document(
    boat_id: int,
    doc_id: int,
    payload: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = BoatDocumentService.update_document(db, boat_id, doc_id, payload, current_user)
    return DocumentOut.model_validate(doc)


@router.delete(
    "/{boat_id}/documents/{doc_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete boat document",
    description="Soft-delete a document (sets deleted_at, does not remove row).",
)
def delete_document(
    boat_id: int,
    doc_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    BoatDocumentService.delete_document(db, boat_id, doc_id, current_user)
    return None


@router.post(
    "/{boat_id}/documents/{doc_id}/verify",
    response_model=DocumentOut,
    summary="Verify boat document",
    description="(Operator only) Verify or reject a boat document.",
)
def verify_document(
    boat_id: int,
    doc_id: int,
    is_verified: bool = Query(True, description="Mark as verified or rejected"),
    notes: Optional[str] = Query(None, description="Verification notes"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    doc = BoatDocumentService.verify_document(
        db, boat_id, doc_id, current_user,
        is_verified=is_verified,
        notes=notes,
    )
    return DocumentOut.model_validate(doc)


@router.get(
    "/{boat_id}/document-stats",
    summary="Get document statistics",
    description="Get document compliance statistics for a boat.",
)
def get_document_stats(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoatDocumentService.get_document_stats(db, boat_id, current_user)


# =============================================================================
# Crew sub-resource endpoints
# =============================================================================

@router.post(
    "/{boat_id}/crew",
    response_model=CrewMemberOut,
    status_code=status.HTTP_201_CREATED,
    summary="Assign crew member",
    description="Assign a crew member to a boat. Enforces one-captain rule.",
)
def assign_crew(
    boat_id: int,
    payload: CrewMemberCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = BoatCrewService.assign_crew(db, boat_id, payload, current_user)
    return CrewMemberOut.model_validate(member)


@router.get(
    "/{boat_id}/crew",
    response_model=list[CrewMemberOut],
    summary="List crew members",
    description="List active (or all) crew members for a boat.",
)
def list_crew(
    boat_id: int,
    include_inactive: bool = Query(False, description="Include removed crew members"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    members = BoatCrewService.list_crew(
        db, boat_id, current_user,
        include_inactive=include_inactive,
    )
    return [CrewMemberOut.model_validate(m) for m in members]


@router.get(
    "/{boat_id}/crew/{crew_id}",
    response_model=CrewMemberOut,
    summary="Get crew member",
    description="Get a single crew member by ID.",
)
def get_crew_member(
    boat_id: int,
    crew_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = BoatCrewService.get_crew_member(db, boat_id, crew_id, current_user)
    return CrewMemberOut.model_validate(member)


@router.delete(
    "/{boat_id}/crew/{crew_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove crew member",
    description="Soft-remove a crew member from a boat. "
                "Cannot remove the last captain.",
)
def remove_crew(
    boat_id: int,
    crew_id: int,
    payload: Optional[CrewMemberRemove] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    BoatCrewService.remove_crew(
        db, boat_id, crew_id,
        payload or CrewMemberRemove(),
        current_user,
    )
    return None


@router.patch(
    "/{boat_id}/crew/{crew_id}/role",
    response_model=CrewMemberOut,
    summary="Update crew role",
    description="Update a crew member's role. Enforces one-captain rule.",
)
def update_crew_role(
    boat_id: int,
    crew_id: int,
    new_role: str = Query(..., description="New crew role"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    member = BoatCrewService.update_crew_role(
        db, boat_id, crew_id, new_role, current_user,
    )
    return CrewMemberOut.model_validate(member)


@router.get(
    "/{boat_id}/crew-stats",
    summary="Get crew statistics",
    description="Get crew composition statistics for a boat.",
)
def get_crew_stats(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoatCrewService.get_crew_stats(db, boat_id, current_user)


# =============================================================================
# Expiring documents endpoint (cross-boat)
# =============================================================================

@router.get(
    "/documents/expiring",
    summary="Get expiring documents",
    description="Get documents expiring within N days across visible boats. "
                "Operators see all; fishermen see their own.",
)
def get_expiring_documents(
    within_days: int = Query(30, ge=1, le=365, description="Days to look ahead"),
    boat_id: Optional[int] = Query(None, description="Optional boat filter"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return BoatDocumentService.get_expiring_documents(
        db, current_user,
        within_days=within_days,
        boat_id=boat_id,
    )
