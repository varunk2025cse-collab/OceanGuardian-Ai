"""Fish market price reference data."""
from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.user import User
from app.models.market_price import MarketPrice
from app.schemas.market import MarketPriceOut

router = APIRouter(prefix="/api/v1/market", tags=["market"])


@router.get("/prices", response_model=list[MarketPriceOut])
def list_prices(
    region: str | None = None,
    species: str | None = None,
    on_date: date | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(MarketPrice)
    if region:
        query = query.filter(MarketPrice.harbor_region.ilike(f"%{region}%"))
    if species:
        query = query.filter(MarketPrice.species.ilike(f"%{species}%"))
    if on_date:
        query = query.filter(MarketPrice.price_date == on_date)
    else:
        # default: most recent date that has any data
        latest = query.order_by(MarketPrice.price_date.desc()).first()
        if latest:
            query = query.filter(MarketPrice.price_date == latest.price_date)

    return query.order_by(MarketPrice.species.asc()).all()
