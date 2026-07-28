"""
Rescue AI Panel API — v2 (docs/AI_ARCHITECTURE.md Phase 17/18).

A constrained query endpoint, not a free-text chat — see
app.services.ai.dispatcher for why. Every query is answered through
authorized tool calls against real system data (app.services.ai.tools);
nothing here invents operational facts.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_operator, get_current_user
from app.database import get_db
from app.models.user import User
from app.services.ai.dispatcher import AIQueryIntent, run_query

router = APIRouter(prefix="/api/v2/ai", tags=["ai"])


class AIQueryIn(BaseModel):
    intent: str
    fisherman_id: int | None = None
    incident_id: int | None = None


class AIQueryOut(BaseModel):
    answer: str
    data: dict | list | None = None
    provider: str | None = None


@router.get("/intents")
def list_intents(_: User = Depends(get_current_operator)):
    """The fixed set of questions the Rescue AI panel can answer, with the
    exact labels from the governing brief's worked examples — the UI
    renders these as one-tap buttons."""
    return {"intents": [{"id": k, "label": v} for k, v in AIQueryIntent.LABELS.items()]}


@router.post("/query", response_model=AIQueryOut)
def query(
    payload: AIQueryIn,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.intent not in AIQueryIntent.ALL:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Unrecognized intent")
    result = run_query(db, current_user, payload.intent, fisherman_id=payload.fisherman_id, incident_id=payload.incident_id)
    return AIQueryOut(**result)
