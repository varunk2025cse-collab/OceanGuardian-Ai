"""
Harbor reference data.

Read-only for all authenticated users. The mobile app uses this to show
"nearest harbor" distance+bearing even offline (it caches the full list).
Operators can add harbors via seed or the admin panel (future feature).
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.deps import get_current_user
from app.models.harbor import Harbor
from app.models.user import User
from app.schemas.harbor import HarborOut, NearestHarborOut
from app.services.geo import haversine_km, bearing_degrees

router = APIRouter(prefix="/api/v1/harbors", tags=["harbors"])


@router.get("/", response_model=list[HarborOut])
def list_harbors(
    region: str | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(Harbor).filter(Harbor.is_active.is_(True))
    if region:
        query = query.filter(Harbor.region.ilike(f"%{region}%"))
    return query.order_by(Harbor.name.asc()).all()


@router.get("/nearest", response_model=NearestHarborOut)
def nearest_harbor(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Returns the single closest active harbor to the supplied GPS position."""
    harbors = db.query(Harbor).filter(Harbor.is_active.is_(True)).all()
    if not harbors:
        from fastapi import HTTPException, status
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No harbors in database")

    nearest = min(harbors, key=lambda h: haversine_km(lat, lon, h.latitude, h.longitude))
    dist = haversine_km(lat, lon, nearest.latitude, nearest.longitude)
    bearing = bearing_degrees(lat, lon, nearest.latitude, nearest.longitude)
    return NearestHarborOut(harbor=nearest, distance_km=round(dist, 2), bearing_degrees=round(bearing, 1))
