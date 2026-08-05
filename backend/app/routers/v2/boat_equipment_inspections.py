"""
Equipment & Inspection sub-resource API endpoints.

These are added as a separate router (not in boats.py) to keep file sizes
manageable while still nesting under /api/v2/boats/{boat_id}/...

Endpoints:
  POST   /api/v2/boats/{boat_id}/equipment        — Add equipment item
  GET    /api/v2/boats/{boat_id}/equipment        — List equipment
  GET    /api/v2/boats/{boat_id}/equipment/{id}   — Get item
  PATCH  /api/v2/boats/{boat_id}/equipment/{id}   — Update item
  DELETE /api/v2/boats/{boat_id}/equipment/{id}   — Remove item
  GET    /api/v2/boats/{boat_id}/equipment-stats   — Equipment summary

  POST   /api/v2/boats/{boat_id}/inspections       — Record inspection
  GET    /api/v2/boats/{boat_id}/inspections       — List inspections
  GET    /api/v2/boats/{boat_id}/inspections/{id}  — Get inspection
  DELETE /api/v2/boats/{boat_id}/inspections/{id}  — Soft-delete inspection
  GET    /api/v2/boats/{boat_id}/inspection-stats  — Inspection summary
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.boat import Boat, BoatEquipmentItem, BoatInspection
from app.schemas.boat import (
    EquipmentItemCreate,
    EquipmentItemUpdate,
    EquipmentItemOut,
    InspectionCreate,
    InspectionOut,
)
from app.services.boat_service import BoatService

router = APIRouter(prefix="/api/v2/boats", tags=["boat-equipment-inspections"])


# ── Helpers ──────────────────────────────────────────────────────────────────

def _get_boat_for_user(db: Session, boat_id: int, user: User) -> Boat:
    """Load a boat and enforce ownership / operator access."""
    return BoatService.get_boat_for_user(db, boat_id, user)


# =============================================================================
# Equipment CRUD
# =============================================================================

@router.post(
    "/{boat_id}/equipment",
    response_model=EquipmentItemOut,
    status_code=status.HTTP_201_CREATED,
    summary="Add equipment item",
    description="Add a safety or operational equipment item to a boat's inventory.",
)
def add_equipment(
    boat_id: int,
    payload: EquipmentItemCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = _get_boat_for_user(db, boat_id, current_user)
    item = BoatEquipmentItem(
        boat_id=boat.id,
        category=payload.category,
        item_name=payload.item_name,
        quantity=payload.quantity,
        condition=payload.condition,
        last_checked_at=payload.last_checked_at,
        expiry_date=payload.expiry_date,
        notes=payload.notes,
        is_mandatory=payload.is_mandatory,
        created_by=current_user.id,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return EquipmentItemOut.model_validate(item)


@router.get(
    "/{boat_id}/equipment",
    response_model=list[EquipmentItemOut],
    summary="List equipment items",
    description="List equipment for a boat. Optionally filter by category or condition.",
)
def list_equipment(
    boat_id: int,
    category: Optional[str] = Query(None),
    condition: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    q = db.query(BoatEquipmentItem).filter(
        BoatEquipmentItem.boat_id == boat_id,
        BoatEquipmentItem.deleted_at.is_(None),
    )
    if category:
        q = q.filter(BoatEquipmentItem.category == category)
    if condition:
        q = q.filter(BoatEquipmentItem.condition == condition)
    return [EquipmentItemOut.model_validate(i) for i in q.order_by(BoatEquipmentItem.category, BoatEquipmentItem.item_name).all()]


@router.get(
    "/{boat_id}/equipment/{item_id}",
    response_model=EquipmentItemOut,
    summary="Get equipment item",
)
def get_equipment(
    boat_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    item = db.query(BoatEquipmentItem).filter(
        BoatEquipmentItem.id == item_id,
        BoatEquipmentItem.boat_id == boat_id,
        BoatEquipmentItem.deleted_at.is_(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Equipment item not found")
    return EquipmentItemOut.model_validate(item)


@router.patch(
    "/{boat_id}/equipment/{item_id}",
    response_model=EquipmentItemOut,
    summary="Update equipment item",
    description="Partially update an equipment item (condition, quantity, expiry, notes).",
)
def update_equipment(
    boat_id: int,
    item_id: int,
    payload: EquipmentItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    item = db.query(BoatEquipmentItem).filter(
        BoatEquipmentItem.id == item_id,
        BoatEquipmentItem.boat_id == boat_id,
        BoatEquipmentItem.deleted_at.is_(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Equipment item not found")

    update_data = payload.model_dump(exclude_unset=True)
    for k, v in update_data.items():
        setattr(item, k, v)
    db.commit()
    db.refresh(item)
    return EquipmentItemOut.model_validate(item)


@router.delete(
    "/{boat_id}/equipment/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove equipment item",
)
def delete_equipment(
    boat_id: int,
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    item = db.query(BoatEquipmentItem).filter(
        BoatEquipmentItem.id == item_id,
        BoatEquipmentItem.boat_id == boat_id,
        BoatEquipmentItem.deleted_at.is_(None),
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="Equipment item not found")
    item.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return None


@router.get(
    "/{boat_id}/equipment-stats",
    summary="Equipment compliance summary",
    description="Get safety equipment compliance stats for a single boat.",
)
def equipment_stats(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    items = db.query(BoatEquipmentItem).filter(
        BoatEquipmentItem.boat_id == boat_id,
        BoatEquipmentItem.deleted_at.is_(None),
    ).all()

    today = date.today()
    total = len(items)
    mandatory = [i for i in items if i.is_mandatory]
    expired = [i for i in items if i.expiry_date and i.expiry_date < today]
    poor_or_missing = [i for i in items if i.condition in ("poor", "missing")]

    by_category = {}
    by_condition = {}
    for i in items:
        by_category[i.category] = by_category.get(i.category, 0) + 1
        by_condition[i.condition] = by_condition.get(i.condition, 0) + 1

    return {
        "total_items": total,
        "mandatory_items": len(mandatory),
        "mandatory_missing": len([i for i in mandatory if i.condition == "missing"]),
        "expired_items": len(expired),
        "poor_or_missing": len(poor_or_missing),
        "by_category": by_category,
        "by_condition": by_condition,
        "compliance_score": round(
            (1 - (len(poor_or_missing) + len(expired)) / max(total, 1)) * 100
        ) if total else 0,
    }


# =============================================================================
# Inspections CRUD
# =============================================================================

@router.post(
    "/{boat_id}/inspections",
    response_model=InspectionOut,
    status_code=status.HTTP_201_CREATED,
    summary="Record inspection",
    description="Record a safety or regulatory inspection result.",
)
def add_inspection(
    boat_id: int,
    payload: InspectionCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    boat = _get_boat_for_user(db, boat_id, current_user)
    inspection = BoatInspection(
        boat_id=boat.id,
        inspection_type=payload.inspection_type,
        inspector_name=payload.inspector_name,
        inspector_authority=payload.inspector_authority,
        inspection_date=payload.inspection_date,
        next_due_date=payload.next_due_date,
        result=payload.result,
        findings=payload.findings,
        corrective_actions=payload.corrective_actions,
        certificate_number=payload.certificate_number,
        certificate_url=payload.certificate_url,
        created_by=current_user.id,
    )
    db.add(inspection)
    db.commit()
    db.refresh(inspection)
    return InspectionOut.model_validate(inspection)


@router.get(
    "/{boat_id}/inspections",
    response_model=list[InspectionOut],
    summary="List inspections",
    description="List inspections for a boat. Optionally filter by type or result.",
)
def list_inspections(
    boat_id: int,
    inspection_type: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    q = db.query(BoatInspection).filter(
        BoatInspection.boat_id == boat_id,
        BoatInspection.deleted_at.is_(None),
    )
    if inspection_type:
        q = q.filter(BoatInspection.inspection_type == inspection_type)
    if result:
        q = q.filter(BoatInspection.result == result)
    return [InspectionOut.model_validate(i) for i in q.order_by(BoatInspection.inspection_date.desc()).all()]


@router.get(
    "/{boat_id}/inspections/{insp_id}",
    response_model=InspectionOut,
    summary="Get inspection",
)
def get_inspection(
    boat_id: int,
    insp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    insp = db.query(BoatInspection).filter(
        BoatInspection.id == insp_id,
        BoatInspection.boat_id == boat_id,
        BoatInspection.deleted_at.is_(None),
    ).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    return InspectionOut.model_validate(insp)


@router.delete(
    "/{boat_id}/inspections/{insp_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete inspection",
)
def delete_inspection(
    boat_id: int,
    insp_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    insp = db.query(BoatInspection).filter(
        BoatInspection.id == insp_id,
        BoatInspection.boat_id == boat_id,
        BoatInspection.deleted_at.is_(None),
    ).first()
    if not insp:
        raise HTTPException(status_code=404, detail="Inspection not found")
    insp.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return None


@router.get(
    "/{boat_id}/inspection-stats",
    summary="Inspection compliance summary",
    description="Get inspection compliance stats for a single boat.",
)
def inspection_stats(
    boat_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _get_boat_for_user(db, boat_id, current_user)
    inspections = db.query(BoatInspection).filter(
        BoatInspection.boat_id == boat_id,
        BoatInspection.deleted_at.is_(None),
    ).all()

    today = date.today()
    total = len(inspections)
    by_type = {}
    by_result = {}
    overdue = 0
    for i in inspections:
        by_type[i.inspection_type] = by_type.get(i.inspection_type, 0) + 1
        by_result[i.result] = by_result.get(i.result, 0) + 1
        if i.next_due_date and i.next_due_date < today:
            overdue += 1

    passed = by_result.get("passed", 0)
    failed = by_result.get("failed", 0)

    return {
        "total_inspections": total,
        "passed": passed,
        "failed": failed,
        "conditional": by_result.get("conditional", 0),
        "pending": by_result.get("pending", 0),
        "overdue": overdue,
        "by_type": by_type,
        "by_result": by_result,
        "pass_rate": round(passed / max(passed + failed, 1) * 100),
    }
