"""Government scheme directory for fishermen."""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.govt_scheme import GovtScheme
from app.schemas.scheme import GovtSchemeOut

router = APIRouter(prefix="/api/v1/schemes", tags=["schemes"])


@router.get("/", response_model=list[GovtSchemeOut])
def list_schemes(
    region: str | None = None,
    category: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(GovtScheme).filter(GovtScheme.is_active.is_(True))
    if region:
        query = query.filter(GovtScheme.region.ilike(f"%{region}%"))
    if category:
        query = query.filter(GovtScheme.category.ilike(f"%{category}%"))
    return query.order_by(GovtScheme.title.asc()).all()
