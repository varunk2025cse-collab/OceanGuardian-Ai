"""Emergency Escalation Engine API routes — Phase 5 Week 3.

Endpoints:
  GET   /api/v2/escalations/active                — Active escalations (operator)
  GET   /api/v2/escalations/{id}                   — Escalation detail (operator)
  POST  /api/v2/escalations/{id}/acknowledge       — Acknowledge escalation (operator)
  POST  /api/v2/escalations/{id}/resolve           — Resolve escalation (operator)
  POST  /api/v2/escalations/auto-escalate          — Auto-escalate unacknowledged SOS (operator)
  POST  /api/v2/escalations/auto-upgrade           — Auto-upgrade priorities (operator)
  GET   /api/v2/escalations/{id}/action-logs       — Operator action logs (operator)
  GET   /api/v2/escalations/operator/logs          — All recent operator logs (operator)
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.core.deps import get_current_operator
from app.models.user import User
from app.services.escalation import EscalationEngine
from app.schemas.escalation import (
    EscalationDetail,
    EscalationListItem,
    EscalationAcknowledge,
    EscalationResolve,
    OperatorActionLogResponse,
)

router = APIRouter(prefix="/api/v2/escalations", tags=["escalations"])


@router.get("/active", response_model=List[EscalationListItem])
async def get_active_escalations(
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get list of active escalations (operator only)."""
    escalations = EscalationEngine.get_active_escalations(db, limit=limit)
    return escalations


@router.get("/{escalation_id}", response_model=EscalationDetail)
async def get_escalation_detail(
    escalation_id: int,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get detailed escalation information (operator only)."""
    detail = EscalationEngine.get_escalation_detail(escalation_id, db)
    if not detail:
        raise HTTPException(status_code=404, detail="Escalation not found")

    return detail


@router.post("/{escalation_id}/acknowledge")
async def acknowledge_escalation(
    escalation_id: int,
    request: EscalationAcknowledge,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Acknowledge an escalation (operator only)."""
    result = EscalationEngine.acknowledge_escalation(
        escalation_id, current_user.id, request.notes, db
    )

    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


@router.post("/{escalation_id}/resolve")
async def resolve_escalation(
    escalation_id: int,
    request: EscalationResolve,
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Resolve an escalation (operator only)."""
    result = EscalationEngine.resolve_escalation(
        escalation_id, current_user.id, request.resolution, request.outcome, db
    )

    if result["status"] == "error":
        raise HTTPException(status_code=404, detail=result["message"])

    return result


@router.get("/{escalation_id}/action-logs", response_model=List[OperatorActionLogResponse])
async def get_escalation_action_logs(
    escalation_id: int,
    limit: int = Query(50, ge=1, le=100),
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Get operator action logs for an escalation (operator only)."""
    logs = EscalationEngine.get_operator_action_log(escalation_id, db, limit=limit)
    return logs


@router.post("/auto-escalate")
async def auto_escalate(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Manually trigger auto-escalation of unacknowledged SOS (operator only)."""
    result = EscalationEngine.auto_escalate_unacknowledged_sos(db)
    return result


@router.post("/auto-upgrade")
async def auto_upgrade_priorities(
    current_user: User = Depends(get_current_operator),
    db: Session = Depends(get_db),
):
    """Manually trigger auto-upgrade of escalation priorities (operator only)."""
    result = EscalationEngine.auto_upgrade_priorities(db)
    return result
